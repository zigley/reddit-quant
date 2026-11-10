"""Trials, robustness evaluations, gates, and the once-only final test."""
import json
import sqlite3
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from . import data as datamod
from . import engine, ledger, metrics, overfit, specs
from .config import ROOT, load_config, primary_benchmark, trading_days

SEGMENTS = ("train", "validation")


def seg(cfg, name):
    a, b = cfg["splits"][name]
    return a, b


def dev_end(cfg):
    return cfg["splits"]["validation"][1]


def _run_one(args):
    cfg, template, params, tag, art_dir, cost_mult, delay = args
    t0 = time.time()
    prices = datamod.load_prices(cfg, end=dev_end(cfg))   # code-level guard: dev runs never see final-test bars
    td = trading_days(cfg)
    for sym, df in prices.items():
        if len(df) and df.index.max() > pd.Timestamp(dev_end(cfg)):
            raise SystemExit(f"{sym} extends past validation end {dev_end(cfg)}")
    r = engine.run_backtest(cfg, prices, template, params, end=dev_end(cfg), cost_mult=cost_mult, delay_bars=delay)
    out = {}
    for name in SEGMENTS:
        a, b = seg(cfg, name)
        out[name] = metrics.segment_metrics(r["equity"], r["trades"], r["orders"], r["gross"], a, b, td=td)
    out["dev"] = metrics.segment_metrics(r["equity"], r["trades"], r["orders"], r["gross"],
                                         cfg["splits"]["train"][0], dev_end(cfg), td=td)
    out["n_rejected_orders"] = r["n_rejected"]
    Path(art_dir).mkdir(parents=True, exist_ok=True)
    path = Path(art_dir) / f"{tag}.csv"
    pd.DataFrame({"equity": r["equity"], "gross": r["gross"]}).to_csv(path)
    with open(Path(art_dir) / f"{tag}_trades.json", "w") as f:
        json.dump(r["trades"], f)
    return params, out, str(path), time.time() - t0, r["trades"]


def ptag(params):
    return "_".join(f"{k}-{v}" for k, v in sorted(params.items()))


def run_trials(cfg, con, cycle, spec, procs=3):
    """Run the full config grid for a frozen family spec on train+validation only."""
    spec = specs.load_verified_spec(ROOT / "specs" / f"{spec['family_id']}_{spec['version']}.yaml")
    fam = spec["family_id"]
    grid = engine.grid_configs(spec["template"])
    already = ledger.trial_count(con, fam)
    if already + len(grid) > cfg["research_budget"]["max_trials_per_family"] and already > 0:
        raise SystemExit(f"Trial budget exceeded for {fam}: {already} used + {len(grid)} new")
    if len(grid) > cfg["research_budget"]["max_trials_per_family"]:
        raise SystemExit("grid exceeds trial budget")
    art = ROOT / "artifacts" / f"cycle{cycle:03d}" / fam / "trials"
    jobs = [(cfg, spec["template"], p, ptag(p), str(art), 1.0, 0) for p in grid]
    with Pool(procs, maxtasksperchild=5) as pool:
        for params, out, path, wall, _ in pool.imap_unordered(_run_one, jobs):
            ledger.add_trial(con, cycle, fam, spec["spec_hash"], params, "dev", out, str(Path(path).relative_to(ROOT)), wall)
    return len(grid)


def load_trials(con, cycle, fam, spec_hash):
    rows = con.execute("SELECT * FROM trials WHERE cycle=? AND family_id=? AND spec_hash=? AND segment='dev'",
                       (cycle, fam, spec_hash)).fetchall()
    return [{"params": json.loads(r["params_json"]), "metrics": json.loads(r["metrics_json"]),
             "path": r["artifact_path"], "wall": r["wall_seconds"]} for r in rows]


def select_best(trials):
    """Highest TRAIN Sharpe. Ties broken by params string for determinism."""
    return sorted(trials, key=lambda t: (-t["metrics"]["train"]["sharpe"], ptag(t["params"])))[0]


def dev_returns(path):
    df = pd.read_csv(ROOT / path, index_col=0, parse_dates=True)
    return df["equity"].pct_change().dropna()


def evaluate_dev(cfg, con, cycle, spec, trials, all_family_trial_sharpes, prices):
    """Robustness evaluation of the already-selected config. These are evaluations, not new trials."""
    fam = spec["family_id"]
    sel = select_best(trials)
    params = sel["params"]
    ov = cfg["overfitting"]
    art = ROOT / "artifacts" / f"cycle{cycle:03d}" / fam / "robustness"
    res = {"selected_params": params, "selected_trial_metrics": sel["metrics"]}

    # stress runs (cost 2x, 3x, delay 1)
    stress = {}
    for name, cm, dl in [("cost_2x", 2.0, 0), ("cost_3x", 3.0, 0), ("delay_1", 1.0, ov["delay_bars"])]:
        p, out, path, wall, trades = _run_one((cfg, spec["template"], params, f"{ptag(params)}_{name}", str(art), cm, dl))
        stress[name] = out
        ledger.add_evaluation(con, cycle, fam, spec["spec_hash"], name, params, out,
                              str(Path(path).relative_to(ROOT)))
    res["stress"] = stress

    # DSR, bootstrap on train+validation returns of the selected config
    r_sel = dev_returns(sel["path"])
    r_dev = r_sel.loc[cfg["splits"]["train"][0]: dev_end(cfg)]
    trial_sr_daily = [metrics.sharpe(dev_returns(t["path"]).loc[cfg["splits"]["train"][0]: dev_end(cfg)], 1)
                      for t in trials]
    n = len(trials)
    td = trading_days(cfg)
    res["dsr"] = overfit.deflated_sharpe(r_dev.values, n, trial_sr_daily, td=td)
    pooled = all_family_trial_sharpes
    res["dsr_conservative"] = overfit.deflated_sharpe(r_dev.values, len(pooled), pooled, td=td)
    lo, hi = overfit.stationary_bootstrap_sharpe_ci(r_dev.values, ov["bootstrap"]["mean_block_len"],
                                                   ov["bootstrap"]["n_resamples"], ov["bootstrap"]["seed"],
                                                   ov["bootstrap"]["ci"], td=td)
    res["bootstrap_ci"] = {"lo": lo, "hi": hi, "sharpe": metrics.sharpe(r_dev.values)}

    # PBO over the whole grid
    mat = pd.concat([dev_returns(t["path"]).loc[cfg["splits"]["train"][0]: dev_end(cfg)].rename(ptag(t["params"]))
                     for t in trials], axis=1).dropna()
    res["pbo"] = overfit.pbo_cscv(mat.values, ov["pbo_partitions"])

    # neighbourhood
    grid = spec["grid"]
    nb = overfit.grid_neighbours(params, grid)
    by = {ptag(t["params"]): t for t in trials}
    nb_sh = [by[ptag(p)]["metrics"]["train"]["sharpe"] for p in nb if ptag(p) in by]
    res["neighbours"] = {"n": len(nb_sh), "train_sharpes": nb_sh,
                         "median": float(np.median(nb_sh)) if nb_sh else 0.0,
                         "selected_train_sharpe": sel["metrics"]["train"]["sharpe"]}

    # top trades removal on dev trades
    trades = json.load(open(ROOT / sel["path"].replace(".csv", "_trades.json")))
    dev_tr = [t for t in trades if cfg["splits"]["train"][0] <= t["exit_date"] <= dev_end(cfg)]
    res["top_trades"] = {"n_trades": len(dev_tr), "pnl": float(sum(t["pnl"] for t in dev_tr)),
                         "pnl_after_removing_top": overfit.pnl_after_removing_top(dev_tr, ov["top_trades_removed"]),
                         "k": ov["top_trades_removed"]}

    # passive benchmarks (primary is pre-registered per market; EW is equal-weight of that universe)
    bench = primary_benchmark(cfg)
    td = trading_days(cfg)
    va, vb = seg(cfg, "validation")
    res["primary_benchmark"] = bench
    res["bench_validation"] = {bench: metrics.passive_metrics(prices, bench, va, vb, td=td),
                               "EW": metrics.passive_metrics(prices, "EW", va, vb, td=td)}
    ta, tb = seg(cfg, "train")
    res["bench_train"] = {bench: metrics.passive_metrics(prices, bench, ta, tb, td=td),
                          "EW": metrics.passive_metrics(prices, "EW", ta, tb, td=td)}
    default = by.get(ptag(spec["textbook_default_baseline"]))
    res["family_baseline"] = {"params": spec["textbook_default_baseline"],
                              "validation": default["metrics"]["validation"] if default else None,
                              "train": default["metrics"]["train"] if default else None}
    path = art / "dev_evaluation.json"
    art.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(res, f, indent=2, default=str)
    ledger.add_evaluation(con, cycle, fam, spec["spec_hash"], "dev_evaluation", params, res,
                          str(path.relative_to(ROOT)))
    return res, sel


def dev_gates(cfg, res):
    g = cfg["risk_limits"]["max_drawdown"]
    sel = res["selected_trial_metrics"]
    st = res["stress"]
    out = []
    out.append(("D1_val_sharpe_positive", sel["validation"]["sharpe"] > 0, f"val Sharpe {sel['validation']['sharpe']:.3f}"))
    out.append(("D2_dsr", res["dsr"]["dsr"] >= 0.95,
                f"DSR {res['dsr']['dsr']:.3f} (N={res['dsr']['n_trials']}, SR0 ann {res['dsr']['sr0_annual']:.2f}, "
                f"SR ann {res['dsr']['sr_annual']:.2f}); conservative N={res['dsr_conservative']['n_trials']}: "
                f"{res['dsr_conservative']['dsr']:.3f}"))
    out.append(("D3_pbo", res["pbo"]["pbo"] <= 0.5, f"PBO {res['pbo']['pbo']:.3f}"))
    out.append(("D4_bootstrap_ci", res["bootstrap_ci"]["lo"] > 0,
                f"95% CI [{res['bootstrap_ci']['lo']:.2f}, {res['bootstrap_ci']['hi']:.2f}], Sharpe {res['bootstrap_ci']['sharpe']:.2f}"))
    out.append(("D5_max_dd", abs(sel["train"]["max_dd"]) <= g and abs(sel["validation"]["max_dd"]) <= g,
                f"train {sel['train']['max_dd']:.3f}, val {sel['validation']['max_dd']:.3f}"))
    out.append(("D6_cost_2x", st["cost_2x"]["validation"]["sharpe"] > 0, f"val Sharpe at 2x {st['cost_2x']['validation']['sharpe']:.3f}"))
    out.append(("D7_delay", st["delay_1"]["validation"]["sharpe"] > 0, f"val Sharpe with delay {st['delay_1']['validation']['sharpe']:.3f}"))
    tt = res["top_trades"]
    out.append(("D8_top_trades", tt["pnl_after_removing_top"] > 0,
                f"PnL {tt['pnl']:.0f} -> {tt['pnl_after_removing_top']:.0f} after removing top {tt['k']} ({tt['n_trades']} trades)"))
    nb = res["neighbours"]
    out.append(("D9_neighbours", nb["median"] > 0 and nb["median"] >= 0.5 * nb["selected_train_sharpe"],
                f"median neighbour train Sharpe {nb['median']:.3f} vs selected {nb['selected_train_sharpe']:.3f} (n={nb['n']})"))
    bv = res["bench_validation"]
    bench = res.get("primary_benchmark") or [k for k in bv if k != "EW"][0]
    out.append(("D10_beats_passive", sel["validation"]["sharpe"] > max(bv[bench]["sharpe"], bv["EW"]["sharpe"]),
                f"val Sharpe {sel['validation']['sharpe']:.3f} vs {bench} {bv[bench]['sharpe']:.3f}, EW {bv['EW']['sharpe']:.3f}"))
    return out


def final_test(cfg, con, cycle, cand_spec):
    """Evaluate a frozen candidate spec on the locked final segment. Once per spec hash, enforced by the ledger."""
    cand_spec = specs.load_verified_spec(ROOT / "specs" / f"{cand_spec['family_id']}_{cand_spec['version']}.yaml")
    h = cand_spec["spec_hash"]
    try:
        con.execute("INSERT INTO final_test_access(spec_hash,family_id,accessed_at,cycle,note) VALUES(?,?,?,?,?)",
                    (h, cand_spec["family_id"], ledger.now(), cycle, "final test accessed"))
        con.commit()
    except sqlite3.IntegrityError:
        raise SystemExit(f"Final test already accessed for spec {h[:12]}. Refusing to evaluate again.")
    params = cand_spec["selected_params"]
    prices = datamod.load_prices(cfg)
    fa, fb = cfg["splits"]["final_test"]
    ov = cfg["overfitting"]
    td = trading_days(cfg)
    bench = primary_benchmark(cfg)
    art = ROOT / "artifacts" / f"cycle{cycle:03d}" / cand_spec["family_id"] / "final"
    art.mkdir(parents=True, exist_ok=True)
    out = {"params": params, "spec_hash": h, "primary_benchmark": bench}
    for name, cm, dl in [("base", 1.0, 0), ("cost_2x", 2.0, 0), ("cost_3x", 3.0, 0), ("delay_1", 1.0, ov["delay_bars"])]:
        r = engine.run_backtest(cfg, prices, cand_spec["template"], params, cost_mult=cm, delay_bars=dl)
        m = metrics.segment_metrics(r["equity"], r["trades"], r["orders"], r["gross"], fa, fb, td=td)
        out[name] = m
        pd.DataFrame({"equity": r["equity"], "gross": r["gross"]}).to_csv(art / f"{name}.csv")
        with open(art / f"{name}_trades.json", "w") as f:
            json.dump(r["trades"], f)
        if name == "base":
            rf = r["equity"].pct_change().dropna().loc[fa:fb]
            lo, hi = overfit.stationary_bootstrap_sharpe_ci(rf.values, ov["bootstrap"]["mean_block_len"],
                                                           ov["bootstrap"]["n_resamples"], ov["bootstrap"]["seed"],
                                                           ov["bootstrap"]["ci"], td=td)
            out["bootstrap_ci_info"] = {"lo": lo, "hi": hi, "note": "informational, not a gate"}
    out["bench"] = {bench: metrics.passive_metrics(prices, bench, fa, fb, td=td),
                    "EW": metrics.passive_metrics(prices, "EW", fa, fb, td=td)}
    path = art / "final_evaluation.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    ledger.add_evaluation(con, cycle, cand_spec["family_id"], h, "final_test", params, out, str(path.relative_to(ROOT)))
    return out


def final_gates(cfg, out):
    g = cfg["risk_limits"]["max_drawdown"]
    b = out["base"]
    r = []
    r.append(("F1_sharpe", b["sharpe"] >= 0.3, f"final Sharpe {b['sharpe']:.3f}"))
    r.append(("F2_max_dd", abs(b["max_dd"]) <= g, f"final max DD {b['max_dd']:.3f}"))
    r.append(("F3_cost_2x", out["cost_2x"]["sharpe"] > 0, f"final Sharpe at 2x {out['cost_2x']['sharpe']:.3f}"))
    r.append(("F4_delay", out["delay_1"]["sharpe"] > 0, f"final Sharpe with delay {out['delay_1']['sharpe']:.3f}"))
    bench = out.get("primary_benchmark") or [k for k in out["bench"] if k != "EW"][0]
    r.append(("F5_beats_spy", b["sharpe"] > out["bench"][bench]["sharpe"],
              f"final Sharpe {b['sharpe']:.3f} vs {bench} {out['bench'][bench]['sharpe']:.3f}"))
    r.append(("F6_min_trades", b["trades"] >= 20, f"final trades {b['trades']}"))
    return r
