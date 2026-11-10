"""Scorecard (CSV + markdown) and the section-13 cycle report. Every number comes from the ledger/artifacts."""
import csv
import json
from pathlib import Path

from .config import ROOT, primary_benchmark, trading_days


def _pct(x):
    return f"{x * 100:.1f}%"


def _row(con, q, *a):
    return con.execute(q, a).fetchall()


def _bench_name(d):
    if not d:
        return "SPY"
    if "primary_benchmark" in d:
        return d["primary_benchmark"]
    block = d.get("bench_validation") or d.get("bench_train") or d.get("bench") or {}
    keys = [k for k in block if k != "EW"]
    return keys[0] if keys else "SPY"


def _spec_market(con, family_id):
    row = con.execute("SELECT content_json FROM specs WHERE family_id=? AND kind='family' ORDER BY frozen_at DESC LIMIT 1",
                      (family_id,)).fetchone()
    if not row:
        return family_id.split(".", 1)[0] if "." in family_id else "us_etf"
    c = json.loads(row["content_json"])
    return c.get("market_id") or (family_id.split(".", 1)[0] if "." in family_id else "us_etf")


def family_records(con, cycle):
    recs = []
    for r in _row(con, "SELECT DISTINCT family_id FROM trials WHERE cycle=? AND segment='dev'", cycle):
        fam = r["family_id"]
        spec = con.execute("SELECT * FROM specs WHERE family_id=? AND kind='family' ORDER BY frozen_at DESC LIMIT 1", (fam,)).fetchone()
        dev = con.execute("SELECT * FROM evaluations WHERE cycle=? AND family_id=? AND kind='dev_evaluation'", (cycle, fam)).fetchone()
        fin = con.execute("SELECT * FROM evaluations WHERE cycle=? AND family_id=? AND kind='final_test'", (cycle, fam)).fetchone()
        gates = [dict(g) for g in _row(con, "SELECT * FROM gate_results WHERE cycle=? AND family_id=? ORDER BY id", cycle, fam)]
        st = con.execute("SELECT * FROM status_events WHERE cycle=? AND family_id=? ORDER BY id DESC LIMIT 1", (cycle, fam)).fetchone()
        content = json.loads(spec["content_json"]) if spec else {}
        recs.append({"family": fam, "spec_hash": spec["spec_hash"] if spec else "", "dev": json.loads(dev["result_json"]) if dev else None,
                     "final": json.loads(fin["result_json"]) if fin else None, "gates": gates,
                     "status": dict(st) if st else None,
                     "market": content.get("market_id") or _spec_market(con, fam),
                     "splits": content.get("splits"),
                     "costs": content.get("costs"),
                     "primary_benchmark": content.get("primary_benchmark"),
                     "n_trials": con.execute("SELECT COUNT(*) c FROM trials WHERE cycle=? AND family_id=?", (cycle, fam)).fetchone()["c"]})
    return recs


def _cost_label(costs):
    if not costs:
        return "stated costs"
    c = int(round(costs.get("commission_perc", 0) * 10000))
    s = int(round(costs.get("slippage_perc", 0) * 10000))
    return f"{c} bp commission + {s} bps slippage per side"


def _split_label(splits, name, fallback):
    if not splits or name not in splits:
        return fallback
    a, b = splits[name]
    return f"{name} {a[:7]} to {b[:7]}" if name != "final_test" else f"final test {a[:7]} to {b[:7]}"


def write_scorecard(con, cycle):
    recs = family_records(con, cycle)
    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for r in recs:
        d, f = r["dev"], r["final"]
        sel = d["selected_trial_metrics"] if d else {}
        row = {"market": r.get("market") or "",
               "family": r["family"], "selected_params": json.dumps(d["selected_params"]) if d else "",
               "status": r["status"]["status"] if r["status"] else "",
               "train_sharpe": sel.get("train", {}).get("sharpe"), "val_sharpe": sel.get("validation", {}).get("sharpe"),
               "val_cagr": sel.get("validation", {}).get("cagr"), "val_max_dd": sel.get("validation", {}).get("max_dd"),
               "dsr": d["dsr"]["dsr"] if d else None, "pbo": d["pbo"]["pbo"] if d else None,
               "gates_passed": sum(g["passed"] for g in r["gates"]), "gates_total": len(r["gates"]),
               "final_sharpe": f["base"]["sharpe"] if f else None, "final_cagr": f["base"]["cagr"] if f else None,
               "final_max_dd": f["base"]["max_dd"] if f else None}
        rows.append(row)
    p = out_dir / f"scorecard_cycle_{cycle:03d}.csv"
    fields = ["market", "family", "selected_params", "train_sharpe", "val_sharpe", "val_cagr", "val_max_dd",
              "dsr", "pbo", "gates_passed", "gates_total", "final_sharpe", "final_cagr", "final_max_dd", "status"]
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields if rows else ["family"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    md = ["| Market | Family | Selected params | Train Sharpe | Val Sharpe | DSR | PBO | Gates | Final Sharpe | Status |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"
    for r in rows:
        md.append(f"| {r['market']} | {r['family']} | {r['selected_params']} | {fmt(r['train_sharpe'])} | {fmt(r['val_sharpe'])} | {fmt(r['dsr'])} | "
                  f"{fmt(r['pbo'])} | {r['gates_passed']}/{r['gates_total']} | {fmt(r['final_sharpe'])} | {r['status']} |")
    (out_dir / f"scorecard_cycle_{cycle:03d}.md").write_text("\n".join(md) + "\n")
    return p


def _append_results_rows(A, recs):
    A("| Version | Evaluation period | Net return | Sharpe | Max drawdown | Trades | Costs | Benchmark comparison | Main limitation |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in recs:
        d = r["dev"]
        if not d:
            continue
        sel = d["selected_trial_metrics"]
        ver = f"{r['family']} {r['spec_hash'][:8]} {json.dumps(d['selected_params'])}"
        failed = [g["gate"] for g in r["gates"] if not g["passed"]]
        lim = ("failed " + ", ".join(failed)) if failed else "none flagged by gates"
        bench = _bench_name(d)
        splits = r.get("splits") or {}
        for name, key, b in ((_split_label(splits, "train", "train"), "train", d["bench_train"]),
                             (_split_label(splits, "validation", "validation"), "validation", d["bench_validation"])):
            m = sel[key]
            A(f"| {ver} | {name} | {_pct(m['total_return'])} | {m['sharpe']:.2f} | {_pct(m['max_dd'])} | {m['trades']} | base | "
              f"{bench} Sharpe {b[bench]['sharpe']:.2f} / return {_pct(b[bench]['total_return'])}; EW Sharpe {b['EW']['sharpe']:.2f} | {lim if key == 'validation' else ''} |")
        if r["final"]:
            f = r["final"]
            m = f["base"]
            fb = f["bench"]
            fbench = _bench_name(f)
            ffail = [g["gate"] for g in r["gates"] if g["gate"].startswith("F") and not g["passed"]]
            A(f"| {ver} | {_split_label(splits, 'final_test', 'final test')} | {_pct(m['total_return'])} | {m['sharpe']:.2f} | {_pct(m['max_dd'])} | {m['trades']} | base | "
              f"{fbench} Sharpe {fb[fbench]['sharpe']:.2f} / return {_pct(fb[fbench]['total_return'])}; EW Sharpe {fb['EW']['sharpe']:.2f} | {('failed ' + ', '.join(ffail)) if ffail else 'passed final gates'} |")
            for k, lab in (("cost_2x", "2x costs"), ("cost_3x", "3x costs"), ("delay_1", "1-bar delay")):
                m2 = f[k]
                A(f"| {ver} | final test, {lab} | {_pct(m2['total_return'])} | {m2['sharpe']:.2f} | {_pct(m2['max_dd'])} | {m2['trades']} | {lab} | stress run | |")
    A("")


def _append_gates(A, recs):
    A("| Family | Gate | Result | Detail |")
    A("|---|---|---|---|")
    for r in recs:
        for g in r["gates"]:
            A(f"| {r['family']} | {g['gate']} | {'pass' if g['passed'] else 'FAIL'} | {g['detail']} |")
    A("")


def build_report(cfg, con, cycle, ctx):
    recs = family_records(con, cycle)
    L = []
    A = L.append
    ideas = [dict(r) for r in con.execute("SELECT * FROM ideas ORDER BY testability_score DESC")]
    uniq = [i for i in ideas if not i["duplicate_of"]]
    tested = [r for r in recs]
    n_trials = sum(r["n_trials"] for r in recs)
    survivors = [r for r in recs if r["final"]]
    champs = [r for r in recs if r["status"] and r["status"]["status"] == "CHAMPION"]
    rejected = [r for r in recs if r["status"] and r["status"]["status"] == "REJECTED"]
    markets_ctx = ctx.get("markets") or {}
    market_names = list(markets_ctx) or sorted({r["market"] for r in recs}) or [cfg.get("market_id", "us_etf")]

    A(f"# Cycle {cycle:03d} report")
    A("")
    A("Research and paper only. Live trading is disabled. All config values are PROVISIONAL pending confirmation. "
      "All splits are retrospective (the full history was already known when the specs were written).")
    A("")
    A("## Summary")
    if ctx.get("scrape"):
        A(f"- Researched: {ctx['scrape']['kept_posts']} Reddit posts from r/algotrading and r/Daytrading "
          f"({ctx['scrape']['comments']} comments) retrieved via {ctx['scrape']['method']}; {ctx['parse']['ideas']} strategy-like posts "
          f"parsed into ideas ({ctx['parse']['duplicates']} near-duplicates), across {len({i['family_id'] for i in ideas})} families.")
    if markets_ctx:
        A(f"- Markets this cycle (each is its own universe, with its own 25-trial budget and DSR N=25 / pooled N=75): "
          + ", ".join(market_names) + ".")
        bits = []
        for mid, mc in markets_ctx.items():
            n_s = sum(1 for r in recs if r["market"] == mid and r["final"])
            n_t = sum(1 for r in recs if r["market"] == mid)
            bits.append(f"{mid}: {n_t} families, {n_s} reached the locked final test")
        A("- Tested: " + "; ".join(bits) + f". Total parameter trials: {n_trials}.")
    else:
        splits = cfg.get("splits", {})
        A(f"- Tested: {len(tested)} families, {n_trials} parameter trials on train and validation "
          f"({splits.get('train', ['?', '?'])[0]} to {splits.get('validation', ['?', '?'])[1]}), "
          f"then {len(survivors)} family candidate(s) on the locked final test "
          f"({splits.get('final_test', ['?', '?'])[0]} to {splits.get('final_test', ['?', '?'])[1]}).")
    passed_final = [r for r in survivors if all(g["passed"] for g in r["gates"])]
    A(f"- Survived dev gates (and so reached the final test): {len(survivors)} of {len(tested)}. Passed every dev and final gate: {len(passed_final)}.")
    A(f"- Failed: {len(rejected)} candidate(s) rejected (details in D).")
    if champs:
        A(f"- Ready for paper trading: yes, {', '.join(c['family'] for c in champs)}, subject to the operator confirming the provisional config.")
    else:
        A("- Ready for paper trading: no. No qualifying champion.")
    A("- Uncertain: Reddit rules are mostly incomplete, so each family test is our interpretation of a textbook version, "
      "not a replication of one author's exact rule. Reddit access was through a third-party archive (see F). "
      "Split choice, costs and all risk limits are provisional.")
    A("")

    A("## A. Discovery table")
    A("")
    A("| Strategy ID | Idea | Source | Testability | Main concern | Status |")
    A("|---|---|---|---|---|---|")
    fam_status = {r["family"]: (r["status"]["status"] if r["status"] else "") for r in recs}
    # also map bare family names to namespaced status for display
    bare_status = {}
    for r in recs:
        bare = r["family"].split(".", 1)[-1]
        bare_status.setdefault(bare, []).append(f"{r['family']}: {r['status']['status'] if r['status'] else ''}")
    shown = 0
    for i in uniq:
        if shown >= 20:
            break
        st = fam_status.get(i["family_id"])
        if not st:
            mapped = bare_status.get(i["family_id"])
            if mapped:
                st = "cycle tests: " + "; ".join(mapped)
            else:
                tpl = con.execute("SELECT template FROM families WHERE family_id=?", (i["family_id"],)).fetchone()
                tpl = tpl["template"] if tpl else None
                st = "ledger only (no template in v1)" if not tpl else "ledger only (not tested this cycle)"
        else:
            st = f"family {i['family_id']}: {st}"
        concern = (i["missing_or_ambiguous"] or "").split("; ")
        A(f"| {i['idea_id']} | {i['summary'][:90].replace('|', '/')} ({i['family_id']}) | {i['source_url']} | "
          f"{i['testability_score']:.2f} | {'; '.join(concern[:2]).replace('|', '/')} | {st} |")
        shown += 1
    A("")
    A(f"Showing top {shown} unique ideas by testability. Full ledger: ledger/ledger.sqlite (table ideas), {len(ideas)} rows. "
      "Post votes are recorded but not used as evidence.")
    A("")

    if not markets_ctx:
        A("Family ranking (testability score, eligible = has a v1 template):")
        A("")
        A("| Family | Ideas | Unique | Best idea score | Family score | Eligible |")
        A("|---|---|---|---|---|---|")
        for r in ctx.get("ranking") or []:
            A(f"| {r['family_id']} | {r['n_ideas']} | {r['n_unique']} | {r['best_idea_score']:.2f} | {r['family_score']:.2f} | {r['eligible']} |")
        A("")
    else:
        A("Family ranking is computed separately per market from cached ideas (same score formula as cycle 1). See each market section.")
        A("")

    if markets_ctx:
        for mid, mc in markets_ctx.items():
            mrecs = [r for r in recs if r["market"] == mid]
            A(f"## Market: {mid}")
            A("")
            A(mc.get("intro") or "")
            A("")
            A("### A. Market family ranking")
            A("")
            A("| Family | Ideas | Unique | Best idea score | Family score | Eligible | Chosen |")
            A("|---|---|---|---|---|---|---|")
            chosen_ids = {c["template"] if "template" in c else c["family_id"] for c in mc.get("chosen") or []}
            # chosen list uses template names in config; ranking uses bare family_id
            chosen_bare = set()
            for c in mc.get("chosen") or []:
                chosen_bare.add(c.get("template") or c.get("family_id", "").split(".")[-1])
            for r in mc.get("ranking") or []:
                ch = "yes" if (r["eligible"] and r["family_id"] in chosen_bare) else ""
                A(f"| {r['family_id']} | {r['n_ideas']} | {r['n_unique']} | {r['best_idea_score']:.2f} | {r['family_score']:.2f} | {r['eligible']} | {ch} |")
            A("")
            A(f"Pre-registered families for this market: {', '.join(mc.get('families') or [])}.")
            A("")
            A("### B. Results table")
            A("")
            costs = (mrecs[0]["costs"] if mrecs else None) or mc.get("costs")
            A(f"Net of costs ({_cost_label(costs)}). Sharpe uses rf = 0, annualised with "
              f"{mc.get('trading_days', 252)} periods per year. Benchmarks are zero-cost passive series.")
            A("")
            _append_results_rows(A, mrecs)
            A(f"Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle{cycle:03d}/ and the trials table.")
            A("")
            A("### C. Current champion")
            A("")
            mchamps = [r for r in mrecs if r["status"] and r["status"]["status"] == "CHAMPION"]
            if mchamps:
                for c in mchamps:
                    spec = con.execute("SELECT content_json FROM specs WHERE family_id=? AND kind='candidate' ORDER BY frozen_at DESC LIMIT 1", (c["family"],)).fetchone()
                    sj = json.loads(spec["content_json"])
                    A(f"- Family: {c['family']}, version {sj['version']}, spec hash {sj['spec_hash']}")
                    A(f"- Rules: {sj['rules']}; params {json.dumps(sj['selected_params'])}; fixed {json.dumps(sj['fixed_params'])}")
                    A(f"- Risk limits: {json.dumps(cfg['risk_limits'])}")
                    A("- Evidence: see gate table below and artifacts. Paper trading only, clock starts when the operator confirms the config.")
            else:
                A("No qualifying champion in this market.")
            A("")
            A("Gate results (pre-registered thresholds in config.yaml, committed before these trials):")
            A("")
            _append_gates(A, mrecs)
            A("### D. Rejected candidates")
            A("")
            mrej = [r for r in mrecs if r["status"] and r["status"]["status"] == "REJECTED"]
            if not mrej:
                A("None.")
            for r in mrej:
                failed = [g for g in r["gates"] if not g["passed"]]
                A(f"- {r['family']} ({r['spec_hash'][:8]}): " + "; ".join(f"{g['gate']} ({g['detail']})" for g in failed))
                A("  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), "
                  "pre-registered before testing. The locked final segment cannot be reused for this spec.")
            A("")
    else:
        A("## B. Results table")
        A("")
        A(f"Net of costs ({_cost_label(cfg.get('costs'))}). Sharpe uses rf = 0. Benchmarks are zero-cost passive series.")
        A("")
        _append_results_rows(A, recs)
        A("Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle%03d/<family>/ and the trials table." % cycle)
        A("")
        A("## C. Current champion")
        A("")
        if champs:
            for c in champs:
                spec = con.execute("SELECT content_json FROM specs WHERE family_id=? AND kind='candidate' ORDER BY frozen_at DESC LIMIT 1", (c["family"],)).fetchone()
                sj = json.loads(spec["content_json"])
                A(f"- Family: {c['family']}, version {sj['version']}, spec hash {sj['spec_hash']}")
                A(f"- Rules: {sj['rules']}; params {json.dumps(sj['selected_params'])}; fixed {json.dumps(sj['fixed_params'])}")
                A(f"- Risk limits: {json.dumps(cfg['risk_limits'])}")
                A("- Evidence: see gate table below and artifacts. Paper trading only, clock starts when the operator confirms the config.")
        else:
            A("No qualifying champion.")
        A("")
        A("Gate results per family (pre-registered thresholds in config.yaml, committed before trial 1):")
        A("")
        _append_gates(A, recs)
        A("## D. Rejected candidates")
        A("")
        for r in rejected:
            failed = [g for g in r["gates"] if not g["passed"]]
            A(f"- {r['family']} ({r['spec_hash'][:8]}): " + "; ".join(f"{g['gate']} ({g['detail']})" for g in failed))
            A("  Reconsider with: a new spec version and fresh data not used here (post-2026-11-09 bars, or a different universe), "
              "pre-registered before testing. The locked final segment cannot be reused for this spec.")
        non_tested = [r for r in (ctx.get("ranking") or []) if r["family_id"] not in {x["family"] for x in recs}]
        if non_tested:
            A("")
            A("Ledger-only families (not tested this cycle): " + ", ".join(
                f"{r['family_id']} ({'not in top 3' if r['eligible'] else 'no v1 template'})" for r in non_tested))
        A("")

    A("## E. Next experiments")
    A("")
    for e in ctx.get("next_experiments") or []:
        A(f"- {e}")
    A("")

    A("## F. Audit summary")
    A("")
    for k, v in (ctx.get("audit") or {}).items():
        A(f"- {k}: {v}")
    A("")
    p = ROOT / "reports" / f"cycle_{cycle:03d}.md"
    p.write_text("\n".join(L) + "\n")
    return p
