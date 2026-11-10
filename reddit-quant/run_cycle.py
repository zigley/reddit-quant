#!/usr/bin/env python
r"""Run one research cycle end to end. Paper and research only.

Usage:  python run_cycle.py --cycle 1 [--skip-scrape] [--procs 3]
        python run_cycle.py --cycle 2 --skip-scrape --markets crypto,cbi,futures
Cron (NOT installed by this project, example only, weekly Sunday 06:00 local):
  0 6 * * 0 cd /path/to/reddit-quant && .venv/bin/python run_cycle.py --cycle $(date +\%G\%V) >> logs/cron.log 2>&1
Cycle numbers must be unique: a family spec version can only reach the final test once.
"""
import argparse
import json
import subprocess
import time

from rq import champion, data as datamod, ledger, reddit_scraper, research, rule_parser, scorecard, specs
from rq.config import ROOT, load_config, resolve_market, trading_days, primary_benchmark
from rq import engine


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True)


def _access_summary(acc):
    from collections import Counter
    c = Counter((x["method"], "comments" if x["target"].startswith("comments:") else x["target"], x["status"]) for x in acc)
    parts = [f"{m}/{t}: {st} x{n}" for (m, t, st), n in c.items()]
    first = next((x for x in acc if x["method"] == "public_json"), None)
    return "; ".join(parts) + (f" (public_json detail: {first['detail']})" if first else "")


def _coverage(cfg):
    log = ROOT / "artifacts" / "scrape_cycle1.log"
    skipped = sum(1 for l in log.read_text().splitlines() if l.startswith("skip")) if log.exists() else None
    rc = cfg["reddit"]
    total = len(rc["subreddits"]) * len(rc["keywords"]) * (rc["year_to"] - rc["year_from"] + 1)
    if skipped is None:
        return "unknown"
    return (f"{total - skipped} of {total} subreddit x keyword x year query windows returned data; {skipped} windows hit "
            "server-side timeouts (HTTP 422 Timeout) and were skipped, so coverage is partial and biased toward windows the archive could serve")


def _reuse_scrape(con):
    n_posts = con.execute("SELECT COUNT(*) c FROM raw_posts").fetchone()["c"]
    c_ = con.execute("SELECT COUNT(*) c FROM raw_comments").fetchone()["c"]
    row = con.execute("SELECT access_method m FROM raw_posts LIMIT 1").fetchone()
    method = row["m"] if row else "none"
    return {"method": method, "unique_posts": n_posts, "kept_posts": n_posts, "comments": c_, "requests": 0}


def _parse_counts(con):
    ideas = con.execute("SELECT COUNT(*) c, SUM(duplicate_of IS NOT NULL) d FROM ideas").fetchone()
    return {"ideas": ideas["c"], "duplicates": ideas["d"] or 0}


def ensure_prices(cfg_m):
    path = datamod.manifest_path(cfg_m)
    if not path.exists():
        datamod.download(cfg_m)
    manifest = datamod.verify_manifest(cfg_m)
    prices = datamod.load_prices(cfg_m)
    issues = datamod.sanity_checks(prices)
    return manifest, prices, issues


def freeze_chosen(cfg_m, con, mid, chosen, manifest):
    frozen = []
    for c in chosen:
        template = c["template"]
        family_id = f"{mid}.{template}" if mid and mid != "us_etf" else c["family_id"]
        ids = [dict(i) for i in con.execute("SELECT idea_id, source_url, publication_date, source_says_json FROM ideas "
                                            "WHERE family_id=? AND duplicate_of IS NULL ORDER BY testability_score DESC LIMIT 10",
                                            (template if mid and mid != "us_etf" else c["family_id"],))]
        refs = [{"idea_id": i["idea_id"], "url": i["source_url"], "published": i["publication_date"],
                 "author_params_as_extracted": json.loads(i["source_says_json"]).get("params")} for i in ids]
        # freeze_family_spec uses family_id as the spec id
        spec = specs.freeze_family_spec(cfg_m, con, family_id, template, engine.TEMPLATES, refs, manifest)
        frozen.append(spec)
    return frozen


def run_dev_and_final(cfg_m, con, cycle, frozen, prices, procs):
    all_trials = {s["family_id"]: research.load_trials(con, cycle, s["family_id"], s["spec_hash"]) for s in frozen}
    pooled = []
    for fam, tr in all_trials.items():
        pooled += [__import__("rq.metrics", fromlist=["x"]).sharpe(research.dev_returns(t["path"]).loc[
            cfg_m["splits"]["train"][0]: cfg_m["splits"]["validation"][1]], 1) for t in tr]
    survivors = []
    for s in frozen:
        fam = s["family_id"]
        res, sel = research.evaluate_dev(cfg_m, con, cycle, s, all_trials[fam], pooled, prices)
        gates = research.dev_gates(cfg_m, res)
        for g, ok, det in gates:
            ledger.add_gate(con, cycle, fam, s["spec_hash"], "dev", g, ok, det)
        failed = [f"{g} ({det})" for g, ok, det in gates if not ok]
        ev = f"artifacts/cycle{cycle:03d}/{fam}/robustness/dev_evaluation.json"
        if failed:
            champion.reject(con, cycle, fam, s["spec_hash"], failed, ev)
        else:
            survivors.append((s, res, sel))
    return survivors


def run_finals(cfg_m, con, cycle, survivors):
    for s, res, sel in survivors:
        cand = specs.freeze_candidate_spec(cfg_m, con, s, res["selected_params"],
                                           {"selection": "highest train net Sharpe", "train_sharpe": sel["metrics"]["train"]["sharpe"]})
        git("add", "-A")
        git("commit", "-m", f"Cycle {cycle}: freeze candidate {s['family_id']} before final test")
        out = research.final_test(cfg_m, con, cycle, cand)
        gates = research.final_gates(cfg_m, out)
        for g, ok, det in gates:
            ledger.add_gate(con, cycle, s["family_id"], cand["spec_hash"], "final", g, ok, det)
        failed = [f"{g} ({det})" for g, ok, det in gates if not ok]
        ev = f"artifacts/cycle{cycle:03d}/{s['family_id']}/final/final_evaluation.json"
        if failed:
            champion.reject(con, cycle, s["family_id"], cand["spec_hash"], failed, ev)
        else:
            champion.consider_for_champion(con, cycle, s["family_id"], cand["spec_hash"], out["base"]["sharpe"], ev)


def finalize(cfg, con, cycle, ctx, n_families, t_start):
    n_trials = con.execute("SELECT COUNT(*) c FROM trials WHERE cycle=?", (cycle,)).fetchone()["c"]
    n_eval = con.execute("SELECT COUNT(*) c FROM evaluations WHERE cycle=? AND kind IN ('cost_2x','cost_3x','delay_1')", (cycle,)).fetchone()["c"]
    wall_trials = con.execute("SELECT COALESCE(SUM(wall_seconds),0) s FROM trials WHERE cycle=?", (cycle,)).fetchone()["s"]
    acc = [dict(r) for r in con.execute("SELECT method,target,status,detail FROM access_log WHERE cycle=? ORDER BY id", (cycle,))]
    inj = con.execute("SELECT COUNT(*) c FROM ideas WHERE flags_json LIKE '%\"injection_like\": [\"%'").fetchone()["c"]
    final_n = con.execute("SELECT COUNT(*) c FROM final_test_access WHERE cycle=?", (cycle,)).fetchone()["c"]
    markets_ctx = ctx.get("markets") or {}
    data_lines = []
    issue_lines = []
    for mid, mc in markets_ctx.items():
        man = mc["manifest"]
        data_lines.append(
            f"{mid}: yfinance adjusted daily, {mc['n_symbols']} symbols, {mc['n_bars']} aligned bars, "
            f"{mc['first']} to {mc['last']}, retrieved {man['retrieved_at']}, manifest hash {man['manifest_hash'][:16]}, "
            f"calendar alignment {man.get('alignment', {})}"
        )
        issue_lines.append(f"{mid}: " + ("; ".join(mc["data_issues"]) if mc["data_issues"]
                                         else "sanity checks found no calendar, OHLC, duplicate or non-positive issues "
                                              "(moves >25% and zero-volume bars are listed in the market intro if present)"))
    if not data_lines:
        man, prices, issues = ctx.get("legacy_data") or ({}, {}, [])
        data_lines.append(f"yfinance adjusted daily, retrieved {man.get('retrieved_at')}, manifest hash {man.get('manifest_hash', '')[:16]}")
        issue_lines.append("; ".join(issues) if issues else "none flagged")
    ctx.setdefault("next_experiments", [
        "Get Reddit API credentials (REDDIT_CLIENT_ID/SECRET) so posts and comments can be read from reddit.com directly and the archive-derived permalinks verified. Falsifiable: every cited URL resolves and its text matches the archive.",
        "Replicate the strongest single Reddit rule exactly as written (author numbers, not the grid centre) as one pre-registered spec, 1 trial, on fresh post-cycle bars only. Falsifiable: Sharpe above 0 and above the market's primary buy-and-hold after 2x costs.",
        "Add a second, independent daily dataset (for example a different vendor) and re-run the already-frozen specs for data-source sensitivity. Falsifiable: Sharpe within 0.15 of the yfinance result.",
        "Weekly cycle: only bars after the recorded data end are new; wait for enough fresh data (at least 6 months) before any re-evaluation of a rejected family, with a new spec version.",
    ])
    wall_min = (time.time() - t_start) / 60.0
    ctx["audit"] = {
        "Tools actually used": "Python 3.13 venv (backtrader, yfinance, pandas, numpy, scipy, pyyaml), SQLite, git; cached Reddit posts from cycle 1 (no new scrape this cycle)",
        "Reddit access attempts": _access_summary(acc) if acc else "none this cycle (reuse of cycle 1 cached posts and comments, --skip-scrape)",
        "Reddit coverage": _coverage(cfg),
        "Parser quality": "keyword/regex assignment, precision not measured; titles show noise. Families are used for ranking only; each family test is our textbook-style template, not a replication of any post. Cycle 2 did not re-parse or overwrite idea rows.",
        "Reddit access caveat": "reddit.com returned HTTP 403 in cycle 1. Posts and comments came from a third-party archive (Arctic Shift), permalinks are built from archive records and were not live-verified. Authors dropped at ingest. Cycle 2 reused that cache.",
        "Data": " | ".join(data_lines),
        "Data issues": " | ".join(issue_lines),
        "Total parameter trials this cycle": f"{n_trials} (budget: {cfg['research_budget']['max_trials_per_family']} per family, 3 families per market, separate trial counters and DSR N per market)",
        "Robustness evaluation runs (not trials)": f"{n_eval} dev stress runs plus final-test runs for survivors",
        "Final-test accesses this cycle": f"{final_n} (each spec hash can be accessed once; enforced by a UNIQUE constraint in the ledger)",
        "Compute": f"{wall_trials:.0f} s summed wall time over the {n_trials} trials, plus stress runs and report building, about {wall_min:.1f} minutes end to end. Inside the 120 minute cycle budget." if wall_min < 120 else f"{wall_trials:.0f} s summed wall time over the {n_trials} trials; wall clock {wall_min:.1f} minutes (over the documented 120 minute budget, run was allowed to finish).",
        "Posts flagged as injection-like": f"{inj} (kept as data, never followed)",
        "Constraints": "Single dataset vendor; Sharpe rf=0; fractional shares assumed; stops are close-based and exit at next open; the risk-per-position sizing rule is our interpretation; the delay test applies 1 extra bar to all orders; PBO via CSCV is biased above 0.5 on pure noise, so the 0.50 gate is strict. Futures use yfinance continuous contracts with roll artifacts. Crypto uses 365-day annualisation and 7-day bars.",
        "Monitoring": "None configured. No scheduler is running; cron line is documented only.",
    }
    p = scorecard.build_report(cfg, con, cycle, ctx)
    con.execute("UPDATE cycles SET finished_at=?, notes=? WHERE cycle=?", (ledger.now(), json.dumps({"report": str(p)}), cycle))
    con.commit()
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: report and scorecard")
    print("report:", p)
    return p


def report_only(cfg, con, cycle, ctx, t_start):
    ctx.setdefault("scrape", _reuse_scrape(con))
    ctx.setdefault("parse", _parse_counts(con))
    if "ranking" not in ctx:
        ctx["ranking"] = rule_parser.rank_families(con, cfg["research_budget"]["max_families_per_cycle"])[0]
    n_fam = con.execute("SELECT COUNT(DISTINCT family_id) c FROM trials WHERE cycle=?", (cycle,)).fetchone()["c"]
    return finalize(cfg, con, cycle, ctx, n_fam, t_start)


def _chosen_from_config(cfg_m, con):
    """Use pre-registered families. Recompute ranking for the audit and refuse if it disagrees."""
    mid = cfg_m["market_id"]
    declared = list(cfg_m["families"])
    match = cfg_m.get("idea_match") or {}
    ranking, auto, hits = rule_parser.rank_families_for_market(con, match, cfg_m["research_budget"]["max_families_per_cycle"])
    auto_names = [x["family_id"] for x in auto]
    if auto_names != declared:
        raise SystemExit(f"{mid}: pre-registered families {declared} do not match current ranking {auto_names}. "
                         "Refusing to change the list after registration.")
    chosen = [x for x in ranking if x["family_id"] in declared]
    # preserve declared order
    chosen = sorted(chosen, key=lambda x: declared.index(x["family_id"]))
    return ranking, chosen, hits


def run_multi_market(cfg, con, cycle, markets, procs, t_start):
    ctx = {"scrape": _reuse_scrape(con), "parse": _parse_counts(con), "markets": {}}
    if not ctx["scrape"]["unique_posts"]:
        raise SystemExit("No cached Reddit posts in the ledger. Cycle 2 must reuse data/reddit/ and ledger posts, not scrape.")
    # 1. prices and family lists, no trials yet
    prepared = []
    for mid in markets:
        cfg_m = resolve_market(cfg, mid)
        manifest, prices, issues = ensure_prices(cfg_m)
        ranking, chosen, hits = _chosen_from_config(cfg_m, con)
        first = next(iter(prices.values())).index
        intro = (
            f"Universe: {', '.join(cfg_m['universe'])}. "
            f"Splits (pre-registered): train {cfg_m['splits']['train'][0]} to {cfg_m['splits']['train'][1]}, "
            f"validation {cfg_m['splits']['validation'][0]} to {cfg_m['splits']['validation'][1]}, "
            f"locked final test {cfg_m['splits']['final_test'][0]} to {cfg_m['splits']['final_test'][1]}. "
            f"Primary benchmark: {primary_benchmark(cfg_m)} buy-and-hold (zero cost), plus equal-weight of the universe. "
            f"Costs: {int(round(cfg_m['costs']['commission_perc']*10000))} bp commission and "
            f"{int(round(cfg_m['costs']['slippage_perc']*10000))} bps slippage per side. "
            f"Annualisation uses {trading_days(cfg_m)} periods per year. "
            f"Aligned bars: {len(first)} from {first.min().date()} to {first.max().date()}."
        )
        if issues:
            intro += " Data flags: " + "; ".join(issues) + "."
        ctx["markets"][mid] = {
            "manifest": manifest, "data_issues": issues, "ranking": ranking, "chosen": chosen,
            "families": list(cfg_m["families"]), "costs": cfg_m["costs"], "splits": cfg_m["splits"],
            "trading_days": trading_days(cfg_m), "n_symbols": len(prices), "n_bars": len(first),
            "first": str(first.min().date()), "last": str(first.max().date()), "intro": intro,
            "n_matching_ideas": len(hits),
        }
        prepared.append((cfg_m, manifest, prices, chosen))
        art = ROOT / "artifacts" / f"cycle{cycle:03d}" / mid
        art.mkdir(parents=True, exist_ok=True)
        json.dump({"ranking": ranking, "chosen": chosen}, open(art / "family_ranking.json", "w"), indent=2, default=str)

    # 2. freeze all specs, then commit before any trial
    all_frozen = []  # (cfg_m, prices, spec)
    for cfg_m, manifest, prices, chosen in prepared:
        for s in freeze_chosen(cfg_m, con, cfg_m["market_id"], chosen, manifest):
            all_frozen.append((cfg_m, prices, s))
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: freeze family specs before trials")

    # 3. trials, train+validation only, one market at a time so workers see the right cfg
    for cfg_m, prices, s in all_frozen:
        research.run_trials(cfg_m, con, cycle, s, procs=procs)
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: trial batch results (train+validation)")

    # 4. dev evaluation with per-market pooled DSR
    survivors_by_market = []
    for cfg_m, manifest, prices, chosen in prepared:
        frozen = [s for c, p, s in all_frozen if s["market_id"] == cfg_m["market_id"]]
        survivors = run_dev_and_final(cfg_m, con, cycle, frozen, prices, procs)
        survivors_by_market.append((cfg_m, survivors))
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: dev evaluation and gates")

    # 5. final test only for families that passed every dev gate
    for cfg_m, survivors in survivors_by_market:
        run_finals(cfg_m, con, cycle, survivors)

    scorecard.write_scorecard(con, cycle)
    return finalize(cfg, con, cycle, ctx, len(all_frozen), t_start)


def run_legacy(cfg, con, cycle, skip_scrape, procs, t_start):
    """Cycle-1 style single-universe run. Kept so --report-only and a us_etf rerun still work."""
    ctx = {}
    manifest, prices, data_issues = ensure_prices(cfg)
    ctx["legacy_data"] = (manifest, prices, data_issues)
    n_posts = con.execute("SELECT COUNT(*) c FROM raw_posts").fetchone()["c"]
    if skip_scrape and n_posts:
        ctx["scrape"] = _reuse_scrape(con)
    else:
        ctx["scrape"] = reddit_scraper.run_scrape(cfg, con, cycle)
    # Do not call build_ideas when ideas already exist: that path uses INSERT OR REPLACE and would
    # overwrite cycle-1 idea rows including test_results_json.
    if con.execute("SELECT COUNT(*) c FROM ideas").fetchone()["c"]:
        ctx["parse"] = _parse_counts(con)
    else:
        ctx["parse"] = rule_parser.build_ideas(con, cycle)
    ranking, chosen = rule_parser.rank_families(con, cfg["research_budget"]["max_families_per_cycle"])
    ctx["ranking"] = ranking
    art_root = ROOT / "artifacts" / f"cycle{cycle:03d}"
    json.dump({"ranking": ranking, "chosen": chosen}, open(art_root / "family_ranking.json", "w"), indent=2)
    frozen = freeze_chosen(cfg, con, cfg.get("market_id", "us_etf"), chosen, manifest)
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: freeze family specs before trials", "--allow-empty")
    for s in frozen:
        research.run_trials(cfg, con, cycle, s, procs=procs)
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: trial batch results (train+validation)")
    survivors = run_dev_and_final(cfg, con, cycle, frozen, prices, procs)
    git("add", "-A")
    git("commit", "-m", f"Cycle {cycle}: dev evaluation and gates")
    run_finals(cfg, con, cycle, survivors)
    scorecard.write_scorecard(con, cycle)
    return finalize(cfg, con, cycle, ctx, len(frozen), t_start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", type=int, required=True)
    ap.add_argument("--skip-scrape", action="store_true")
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--report-only", action="store_true", help="rebuild scorecard and report from the ledger, no trials")
    ap.add_argument("--markets", type=str, default="",
                    help="comma-separated market ids from config.yaml (each is its own universe)")
    a = ap.parse_args()
    t_start = time.time()
    cfg = load_config()
    cycle = a.cycle
    con = ledger.connect()
    con.execute("INSERT OR IGNORE INTO cycles(cycle,started_at) VALUES(?,?)", (cycle, ledger.now()))
    con.commit()
    art_root = ROOT / "artifacts" / f"cycle{cycle:03d}"
    art_root.mkdir(parents=True, exist_ok=True)
    markets = [m.strip() for m in a.markets.split(",") if m.strip()]

    if a.report_only:
        ctx = {}
        if markets:
            ctx["markets"] = {}
            for mid in markets:
                cfg_m = resolve_market(cfg, mid)
                manifest, prices, issues = ensure_prices(cfg_m)
                first = next(iter(prices.values())).index
                ranking, chosen, hits = _chosen_from_config(cfg_m, con)
                ctx["markets"][mid] = {
                    "manifest": manifest, "data_issues": issues, "ranking": ranking, "chosen": chosen,
                    "families": list(cfg_m["families"]), "costs": cfg_m["costs"], "splits": cfg_m["splits"],
                    "trading_days": trading_days(cfg_m), "n_symbols": len(prices), "n_bars": len(first),
                    "first": str(first.min().date()), "last": str(first.max().date()),
                    "intro": "", "n_matching_ideas": len(hits),
                }
        else:
            manifest = datamod.verify_manifest(cfg)
            prices = datamod.load_prices(cfg)
            issues = datamod.sanity_checks(prices)
            ctx["legacy_data"] = (manifest, prices, issues)
        return report_only(cfg, con, cycle, ctx, t_start)

    if markets:
        # Cycle 2+ multi-market path: never scrape, never rebuild ideas.
        return run_multi_market(cfg, con, cycle, markets, a.procs, t_start)
    return run_legacy(cfg, con, cycle, a.skip_scrape, a.procs, t_start)


if __name__ == "__main__":
    main()
