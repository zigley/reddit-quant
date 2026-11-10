"""Performance metrics from a daily equity curve and a trade list. Sharpe uses rf = 0 (disclosed)."""
import numpy as np
import pandas as pd

TD = 252


def trading_days(cfg_or_td=None):
    if cfg_or_td is None:
        return TD
    if isinstance(cfg_or_td, dict):
        return int(cfg_or_td.get("metrics", {}).get("trading_days", TD))
    return int(cfg_or_td)


def returns_from_equity(eq):
    return eq.pct_change().dropna()


def sharpe(r, td=TD):
    r = np.asarray(r, dtype=float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(td))


def max_drawdown(r):
    eq = (1 + pd.Series(r)).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    mdd = float(dd.min()) if len(dd) else 0.0
    # longest time under water, in trading days
    under = (dd < 0).astype(int)
    longest = cur = 0
    for v in under.values:
        cur = cur + 1 if v else 0
        longest = max(longest, cur)
    return mdd, int(longest)


def segment_metrics(equity, trades, orders, gross, start, end, td=TD):
    """equity: pd.Series (date index). trades/orders: lists of dicts. gross: pd.Series gross exposure ratio."""
    r_all = equity.pct_change()
    r = r_all.loc[start:end].dropna()
    n = len(r)
    if n < 5:
        return {"n_days": n}
    years = n / td
    total = float((1 + r).prod() - 1)
    cagr = float((1 + total) ** (1 / years) - 1) if total > -1 else -1.0
    vol = float(r.std(ddof=1) * np.sqrt(td))
    sh = sharpe(r, td)
    dn = np.sqrt(np.mean(np.minimum(r.values, 0.0) ** 2)) * np.sqrt(td)
    sortino = float(r.mean() * td / dn) if dn > 0 else 0.0
    mdd, mdd_days = max_drawdown(r)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    tr = [t for t in trades if s <= pd.Timestamp(t["exit_date"]) <= e]
    pnl = np.array([t["pnl"] for t in tr], dtype=float)
    rets = np.array([t["ret"] for t in tr], dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if losses.sum() < 0 else (float("inf") if wins.sum() > 0 else 0.0)
    g = gross.loc[start:end]
    eq_seg = equity.loc[start:end]
    traded = sum(o["value"] for o in orders if s <= pd.Timestamp(o["date"]) <= e)
    return {
        "n_days": n, "total_return": total, "cagr": cagr, "vol": vol, "sharpe": sh, "sortino": sortino,
        "max_dd": mdd, "max_dd_duration_days": mdd_days, "calmar": calmar,
        "trades": int(len(tr)),
        "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
        "avg_win_pct": float(rets[pnl > 0].mean()) if (pnl > 0).any() else 0.0,
        "avg_loss_pct": float(rets[pnl <= 0].mean()) if (pnl <= 0).any() else 0.0,
        "profit_factor": pf if np.isfinite(pf) else 999.0,
        "net_pnl": float(pnl.sum()),
        "exposure_days_invested": float((g > 1e-9).mean()) if len(g) else 0.0,
        "avg_gross_exposure": float(g.mean()) if len(g) else 0.0,
        "annual_turnover": float(traded / eq_seg.mean() / years) if len(eq_seg) else 0.0,
        "trading_days": td,
    }


def passive_returns(prices, kind, start, end):
    """Zero-cost passive benchmarks as daily return series.

    kind is 'EW' (equal-weight, daily rebalanced) or a ticker present in prices.
    """
    close = pd.DataFrame({s: df["Close"] for s, df in prices.items()})
    rets = close.pct_change()
    if kind == "EW":
        r = rets.mean(axis=1)
    elif kind in rets.columns:
        r = rets[kind]
    else:
        raise ValueError(f"unknown benchmark {kind}")
    return r.loc[start:end].dropna()


def passive_metrics(prices, kind, start, end, td=TD):
    r = passive_returns(prices, kind, start, end)
    mdd, dur = max_drawdown(r)
    total = float((1 + r).prod() - 1)
    years = len(r) / td
    return {"n_days": len(r), "total_return": total, "cagr": float((1 + total) ** (1 / years) - 1) if years else 0.0,
            "vol": float(r.std(ddof=1) * np.sqrt(td)), "sharpe": sharpe(r, td), "max_dd": mdd,
            "max_dd_duration_days": dur, "trading_days": td}
