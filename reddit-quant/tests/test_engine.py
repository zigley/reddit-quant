"""Sanity tests for the engine. Run: python tests/test_engine.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backtrader as bt
import numpy as np
import pandas as pd

from rq import engine, metrics, overfit
from rq.config import load_config


def synthetic_prices(cfg, start="2005-01-01", end="2012-12-31"):
    """In-memory OHLCV for the configured universe. Used so engine tests do not
    need downloaded price CSVs.

    The path is a piecewise trend (down, up, down, up) plus a small regular
    dip, so SMA crosses stay stable under a 1-bar delay and RSI still fires.
    """
    idx = pd.bdate_range(start, end)
    n = len(idx)
    t = np.arange(n, dtype=float)
    base = np.full(n, 90.0)
    base = np.where(t < 250, 90.0, base)
    base = np.where((t >= 250) & (t < 700), 90.0 + 0.15 * (t - 250), base)
    peak = 90.0 + 0.15 * (700 - 250)
    base = np.where((t >= 700) & (t < 1100), peak - 0.15 * (t - 700), base)
    trough = peak - 0.15 * (1100 - 700)
    base = np.where(t >= 1100, trough + 0.12 * (t - 1100), base)
    # modest 20-day dip so RSI mean-reversion can enter
    base = base + 2.5 * np.sin(2 * np.pi * t / 20)
    out = {}
    for i, sym in enumerate(cfg["universe"]):
        close = base + i * 2.0
        open_ = close
        high = close + 0.5
        low = close - 0.5
        out[sym] = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": 1e6},
            index=idx,
        )
    return out


class Scripted(bt.Strategy):
    def __init__(self):
        self.n = 0
        self.log = []

    def next(self):
        self.n += 1
        if self.n == 5:
            self.buy(size=10)
            self.log.append(("signal_close", self.data.datetime.date(0), self.data.close[0]))
        if self.n == 8:
            self.close()

    def notify_order(self, o):
        if o.status == o.Completed:
            self.log.append(("fill", bt.num2date(o.executed.dt).date(), o.executed.price, o.executed.comm,
                             float(self.data.open[0])))


def test_next_open_and_costs():
    cfg = load_config()
    idx = pd.bdate_range("2020-01-01", periods=20)
    px = 100 + np.arange(20, dtype=float)
    df = pd.DataFrame({"Open": px, "High": px + 1, "Low": px - 1, "Close": px + 0.5, "Volume": 1e6}, index=idx)
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.set_coc(False)
    cerebro.broker.setcash(10000)
    cerebro.broker.setcommission(commission=cfg["costs"]["commission_perc"])
    cerebro.broker.set_slippage_perc(cfg["costs"]["slippage_perc"], slip_open=True, slip_limit=True,
                                     slip_match=True, slip_out=False)
    cerebro.adddata(bt.feeds.PandasData(dataname=df, openinterest=None, open="Open", high="High", low="Low",
                                        close="Close", volume="Volume"))
    cerebro.addstrategy(Scripted)
    s = cerebro.run()[0]
    sig = [x for x in s.log if x[0] == "signal_close"][0]
    fills = [x for x in s.log if x[0] == "fill"]
    buy = fills[0]
    assert buy[1] > sig[1], "fill must be after the signal bar"
    assert buy[1] == idx[5].date(), (buy[1], idx[5].date())
    exp_price = df["Open"].iloc[5] * (1 + cfg["costs"]["slippage_perc"])
    assert abs(buy[2] - exp_price) < 1e-6, (buy[2], exp_price)
    assert abs(buy[3] - 10 * exp_price * cfg["costs"]["commission_perc"]) < 1e-6, buy[3]
    sell = fills[1]
    exp_sell = df["Open"].iloc[8] * (1 - cfg["costs"]["slippage_perc"])
    assert abs(sell[2] - exp_sell) < 1e-6, (sell[2], exp_sell)
    print("ok next-open fill, 5 bps slippage and 1 bp commission verified")


def test_delay_changes_fill():
    cfg = load_config()
    pr = synthetic_prices(cfg, end="2012-12-31")
    a = engine.run_backtest(cfg, pr, "sma_cross", engine.TEMPLATES["sma_cross"]["default"], end="2012-12-31")
    b = engine.run_backtest(cfg, pr, "sma_cross", engine.TEMPLATES["sma_cross"]["default"], end="2012-12-31",
                            delay_bars=1)
    da = {(o["data"], o["side"]): o["date"] for o in a["orders"][:6]}
    db = {(o["data"], o["side"]): o["date"] for o in b["orders"][:6]}
    shared = [k for k in da if k in db]
    assert shared and all(db[k] > da[k] for k in shared), (da, db)
    print("ok 1-bar delay pushes fills later")


def test_risk_caps():
    cfg = load_config()
    pr = synthetic_prices(cfg, end="2012-12-31")
    r = engine.run_backtest(cfg, pr, "rsi_meanrev", engine.TEMPLATES["rsi_meanrev"]["default"], end="2012-12-31")
    assert r["gross"].max() <= 1.0 + 0.05, r["gross"].max()   # small allowance for next-open gaps
    conc = {}
    for o in r["orders"]:
        pass
    print("ok max gross exposure", round(float(r["gross"].max()), 3))


def test_overfit_math():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0004, 0.01, 2000)
    sr = metrics.sharpe(r)
    lo, hi = overfit.stationary_bootstrap_sharpe_ci(r, 10, 500, 1, 0.95)
    assert lo < sr < hi
    d = overfit.deflated_sharpe(r, n_trials=25, trial_sharpes_daily=rng.normal(0, 0.03, 25))
    assert 0 <= d["dsr"] <= 1
    noise = rng.normal(0, 0.01, (1600, 20))
    res = overfit.pbo_cscv(noise, 8)
    assert 0.2 < res["pbo"] < 0.8, res    # pure noise should give PBO near 0.5
    print("ok DSR/bootstrap/PBO sanity, pbo on noise =", round(res["pbo"], 2))


if __name__ == "__main__":
    test_next_open_and_costs()
    test_delay_changes_fill()
    test_risk_caps()
    test_overfit_math()
