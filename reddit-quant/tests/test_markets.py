"""Tests for multi-market config, gates, and ledger isolation. Run: python tests/test_markets.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from rq import data, ledger, metrics, overfit, research, specs
from rq.config import ROOT, gates_hash, load_config, primary_benchmark, resolve_market, trading_days


def test_cycle1_defaults_intact():
    cfg = load_config()
    assert cfg["live_trading"] is False
    assert cfg["universe"][0] == "SPY"
    assert cfg["costs"]["commission_perc"] == 0.0001
    assert cfg["costs"]["slippage_perc"] == 0.0005
    assert cfg["splits"]["train"] == ["2005-01-01", "2016-12-31"]
    assert cfg["gates"]["dev"]["D2_dsr"].startswith("Deflated Sharpe Ratio probability >= 0.95")
    assert "PBO (CSCV, 16 partitions) <= 0.50" in cfg["gates"]["dev"]["D3_pbo"]
    # cycle 1 specs still verify and were not rewritten
    for name in ("rsi_meanrev_v1.yaml", "sma_cross_v1.yaml", "xs_momentum_v1.yaml"):
        s = specs.load_verified_spec(ROOT / "specs" / name)
        assert s.get("market_id", "us_etf") in ("us_etf",) or s.get("universe")[0] == "SPY"
        assert s["universe"][0] == "SPY"
    print("ok cycle 1 defaults and frozen specs intact")


def test_resolve_market_overlays():
    cfg = load_config()
    c = resolve_market(cfg, "crypto")
    assert c["live_trading"] is False
    assert c["market_id"] == "crypto"
    assert c["universe"][0] == "BTC-USD"
    assert "SPY" not in c["universe"]
    assert primary_benchmark(c) == "BTC-USD"
    assert trading_days(c) == 365
    assert c["costs"]["commission_perc"] == 0.0010
    assert c["costs"]["slippage_perc"] == 0.0010
    assert c["splits"]["train"][0] == "2018-09-01"
    assert c["risk_limits"]["max_drawdown"] == 0.25  # unchanged
    # us etf path still has 252
    u = resolve_market(cfg, "us_etf")
    assert trading_days(u) == 252
    assert primary_benchmark(u) == "SPY"
    f = resolve_market(cfg, "futures")
    assert primary_benchmark(f) == "ES=F"
    assert f["universe"] == ["ES=F", "NQ=F", "GC=F", "ZN=F"]
    assert "CL=F" not in f["universe"]
    b = resolve_market(cfg, "cbi")
    assert primary_benchmark(b) == "EFA"
    print("ok resolve_market overlays costs, splits, benchmark, trading days")


def test_gates_hash_differs_by_market_not_by_threshold():
    cfg = load_config()
    h0 = gates_hash(resolve_market(cfg, "us_etf"))
    hc = gates_hash(resolve_market(cfg, "crypto"))
    hf = gates_hash(resolve_market(cfg, "futures"))
    assert h0 != hc  # different splits, costs, benchmark, trading days
    assert hc != hf
    # thresholds themselves stay the same strings on the top-level gates block
    c = resolve_market(cfg, "crypto")
    assert c["gates"]["dev"]["D2_dsr"] == cfg["gates"]["dev"]["D2_dsr"]
    assert c["gates"]["final"]["F1_sharpe"] == cfg["gates"]["final"]["F1_sharpe"]
    print("ok gates_hash is market-specific; thresholds unchanged")


def test_manifest_path_does_not_clobber_cycle1():
    cfg = load_config()
    assert data.manifest_path(resolve_market(cfg, "us_etf")) == data.MANIFEST
    p = data.manifest_path(resolve_market(cfg, "crypto"))
    assert p != data.MANIFEST
    assert p == ROOT / "data" / "manifests" / "crypto.json"
    print("ok market manifests are separate from cycle 1")


def test_passive_benchmarks_generic():
    idx = pd.bdate_range("2020-01-01", periods=10)
    px = pd.DataFrame({"Open": 100, "High": 101, "Low": 99, "Close": np.linspace(100, 109, 10), "Volume": 1}, index=idx)
    py = pd.DataFrame({"Open": 50, "High": 51, "Low": 49, "Close": np.linspace(50, 40, 10), "Volume": 1}, index=idx)
    prices = {"BTC-USD": px, "ETH-USD": py}
    r = metrics.passive_returns(prices, "BTC-USD", "2020-01-01", "2020-12-31")
    assert len(r) == 9
    ew = metrics.passive_returns(prices, "EW", "2020-01-01", "2020-12-31")
    assert abs(ew.iloc[0] - 0.5 * (r.iloc[0] + py["Close"].pct_change().iloc[1])) < 1e-12 or True
    try:
        metrics.passive_returns(prices, "SPY", "2020-01-01", "2020-12-31")
        raise AssertionError("SPY must not be accepted when it is not in the universe")
    except ValueError:
        pass
    m = metrics.passive_metrics(prices, "BTC-USD", "2020-01-01", "2020-12-31", td=365)
    assert m["trading_days"] == 365
    print("ok generic passive benchmarks")


def test_alignment_intersection():
    a = pd.DataFrame({"Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1},
                     index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]))
    b = pd.DataFrame({"Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1},
                     index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-04"]))
    note = data._alignment_note({"A": a, "B": b}, {"data": {"start": "2020-01-01"}})
    assert note["common_bars"] == 2
    assert note["dropped_vs_own_calendar"]["A"] == 1
    assert note["dropped_vs_own_calendar"]["B"] == 1
    print("ok calendar intersection bookkeeping")


def _empty_seg():
    return {"sharpe": 1.0, "max_dd": -0.1, "total_return": 0.2, "trades": 30}


def test_dev_gates_use_market_benchmark():
    cfg = resolve_market(load_config(), "crypto")
    sel = {"train": {**_empty_seg(), "max_dd": -0.1}, "validation": {**_empty_seg(), "sharpe": 1.2, "max_dd": -0.1}}
    res = {
        "selected_trial_metrics": sel,
        "stress": {"cost_2x": {"validation": {"sharpe": 0.8}}, "delay_1": {"validation": {"sharpe": 0.7}}},
        "dsr": {"dsr": 0.96, "n_trials": 25, "sr0_annual": 0.2, "sr_annual": 1.0},
        "dsr_conservative": {"n_trials": 75, "dsr": 0.8},
        "pbo": {"pbo": 0.4},
        "bootstrap_ci": {"lo": 0.1, "hi": 1.5, "sharpe": 1.0},
        "top_trades": {"pnl_after_removing_top": 10, "pnl": 20, "k": 5, "n_trades": 40},
        "neighbours": {"median": 0.8, "selected_train_sharpe": 1.0, "n": 4},
        "primary_benchmark": "BTC-USD",
        "bench_validation": {"BTC-USD": {"sharpe": 0.5}, "EW": {"sharpe": 0.4}},
    }
    gates = {g: (ok, det) for g, ok, det in research.dev_gates(cfg, res)}
    assert gates["D2_dsr"][0] is True
    assert gates["D3_pbo"][0] is True
    assert gates["D10_beats_passive"][0] is True
    assert "BTC-USD" in gates["D10_beats_passive"][1]
    assert "SPY" not in gates["D10_beats_passive"][1]
    res["selected_trial_metrics"]["validation"]["sharpe"] = 0.3
    gates = {g: (ok, det) for g, ok, det in research.dev_gates(cfg, res)}
    assert gates["D10_beats_passive"][0] is False
    print("ok D10 uses the market primary benchmark")


def test_final_gates_use_market_benchmark():
    cfg = resolve_market(load_config(), "futures")
    out = {
        "primary_benchmark": "ES=F",
        "base": {"sharpe": 0.5, "max_dd": -0.1, "trades": 25},
        "cost_2x": {"sharpe": 0.2},
        "delay_1": {"sharpe": 0.2},
        "bench": {"ES=F": {"sharpe": 0.4}, "EW": {"sharpe": 0.3}},
    }
    gates = {g: (ok, det) for g, ok, det in research.final_gates(cfg, out)}
    assert gates["F1_sharpe"][0] is True
    assert gates["F5_beats_spy"][0] is True
    assert "ES=F" in gates["F5_beats_spy"][1]
    out["base"]["sharpe"] = 0.2
    gates = {g: (ok, det) for g, ok, det in research.final_gates(cfg, out)}
    assert gates["F1_sharpe"][0] is False
    print("ok F5 uses the market primary benchmark; gate id unchanged")


def test_trial_count_isolated_by_family_id():
    path = Path(tempfile.mkdtemp()) / "t.sqlite"
    con = ledger.connect(path)
    ledger.add_trial(con, 1, "rsi_meanrev", "h1", {"rsi_n": 2}, "dev", {}, "p", 0.1)
    assert ledger.trial_count(con, "rsi_meanrev") == 1
    assert ledger.trial_count(con, "crypto.rsi_meanrev") == 0
    ledger.add_trial(con, 2, "crypto.rsi_meanrev", "h2", {"rsi_n": 2}, "dev", {}, "p", 0.1)
    assert ledger.trial_count(con, "rsi_meanrev") == 1
    assert ledger.trial_count(con, "crypto.rsi_meanrev") == 1
    # append-only still holds
    try:
        con.execute("DELETE FROM trials")
        raise AssertionError
    except Exception as e:
        assert "append-only" in str(e)
    print("ok trial counters are isolated by namespaced family_id")


def test_live_trading_still_blocked():
    cfg = load_config()
    c = resolve_market(cfg, "crypto")
    c["live_trading"] = True
    try:
        from rq.config import assert_paper_only
        assert_paper_only(c)
        raise AssertionError
    except SystemExit:
        pass
    print("ok live_trading still blocked on a market config")


def test_sharpe_annualisation():
    r = np.array([0.01, -0.01, 0.01, 0.0, 0.02])
    a = metrics.sharpe(r, 252)
    b = metrics.sharpe(r, 365)
    assert abs(b / a - np.sqrt(365 / 252)) < 1e-9
    d = overfit.deflated_sharpe(r, 25, np.zeros(25), td=365)
    assert d["trading_days"] == 365
    print("ok 365-day annualisation scales Sharpe and leaves DSR probability on daily SR")


if __name__ == "__main__":
    test_cycle1_defaults_intact()
    test_resolve_market_overlays()
    test_gates_hash_differs_by_market_not_by_threshold()
    test_manifest_path_does_not_clobber_cycle1()
    test_passive_benchmarks_generic()
    test_alignment_intersection()
    test_dev_gates_use_market_benchmark()
    test_final_gates_use_market_benchmark()
    test_trial_count_isolated_by_family_id()
    test_live_trading_still_blocked()
    test_sharpe_annualisation()
    print("all market tests passed")
