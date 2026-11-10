"""Overfitting safety checks.

  * Deflated Sharpe Ratio (Bailey and Lopez de Prado, 2014)
  * Probability of Backtest Overfitting via CSCV (Bailey, Borwein, Lopez de Prado, Zhu, 2015)
  * stationary block bootstrap CI on Sharpe (Politis and Romano, 1994)
  * parameter-neighbourhood stability, top-trades removal
"""
import itertools
import math

import numpy as np
from scipy import stats

TD = 252
EULER = 0.5772156649015329


def _sr_daily(r):
    r = np.asarray(r, float)
    s = r.std(ddof=1)
    return r.mean() / s if s > 0 else 0.0


def expected_max_sr(var_sr, n):
    """Expected maximum of n iid Sharpe estimates with variance var_sr (per-period units)."""
    if n <= 1:
        return 0.0
    return math.sqrt(var_sr) * ((1 - EULER) * stats.norm.ppf(1 - 1.0 / n) +
                                EULER * stats.norm.ppf(1 - 1.0 / (n * math.e)))


def deflated_sharpe(r, n_trials, trial_sharpes_daily, td=TD):
    """DSR for return series r (daily). trial_sharpes_daily: per-period Sharpe of every trial
    (used for the cross-trial variance). Returns dict with dsr probability and components.
    td only scales the reported annual Sharpe figures; the DSR probability is computed on daily SR."""
    r = np.asarray(r, float)
    T = len(r)
    sr = _sr_daily(r)
    g3 = float(stats.skew(r))
    g4 = float(stats.kurtosis(r, fisher=False))
    var_sr = float(np.var(np.asarray(trial_sharpes_daily, float), ddof=1)) if len(trial_sharpes_daily) > 1 else 0.0
    sr0 = expected_max_sr(var_sr, n_trials)
    denom = 1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2
    denom = max(denom, 1e-12)
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom)
    return {"dsr": float(stats.norm.cdf(z)), "sr_daily": float(sr), "sr_annual": float(sr * math.sqrt(td)),
            "sr0_daily": float(sr0), "sr0_annual": float(sr0 * math.sqrt(td)), "n_trials": int(n_trials),
            "var_trial_sr": var_sr, "skew": g3, "kurtosis": g4, "T": T, "trading_days": td}


def pbo_cscv(returns_matrix, n_partitions=16):
    """returns_matrix: T x N array of daily returns, one column per configuration.
    CSCV with S partitions; metric = Sharpe. Returns PBO and the logit distribution summary."""
    M = np.asarray(returns_matrix, float)
    T, N = M.shape
    S = n_partitions
    L = T // S
    M = M[: L * S]
    blocks = M.reshape(S, L, N)
    bsum = blocks.sum(axis=1)               # S x N
    bsq = (blocks ** 2).sum(axis=1)         # S x N
    combos = list(itertools.combinations(range(S), S // 2))
    logits = []
    n_in = S // 2 * L

    def sharpe_from(idx):
        s = bsum[list(idx)].sum(axis=0)
        q = bsq[list(idx)].sum(axis=0)
        mean = s / n_in
        var = (q - n_in * mean ** 2) / (n_in - 1)
        sd = np.sqrt(np.maximum(var, 1e-18))
        return mean / sd

    allidx = set(range(S))
    for c in combos:
        oos = tuple(sorted(allidx - set(c)))
        sr_is = sharpe_from(c)
        sr_os = sharpe_from(oos)
        best = int(np.argmax(sr_is))
        rank = (stats.rankdata(sr_os)[best]) / (N + 1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()), "n_combinations": len(combos), "n_configs": N,
            "partitions": S, "logit_median": float(np.median(logits))}


def stationary_bootstrap_indices(n, mean_block, rng):
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    restart = rng.random(n) < p
    starts = rng.integers(n, size=n)
    for i in range(1, n):
        idx[i] = starts[i] if restart[i] else (idx[i - 1] + 1) % n
    return idx


def stationary_bootstrap_sharpe_ci(r, mean_block, n_resamples, seed, ci=0.95, td=TD):
    r = np.asarray(r, float)
    rng = np.random.default_rng(seed)
    n = len(r)
    out = np.empty(n_resamples)
    for b in range(n_resamples):
        rs = r[stationary_bootstrap_indices(n, mean_block, rng)]
        s = rs.std(ddof=1)
        out[b] = rs.mean() / s * math.sqrt(td) if s > 0 else 0.0
    a = (1 - ci) / 2
    return float(np.quantile(out, a)), float(np.quantile(out, 1 - a))


def grid_neighbours(params, grid):
    """Adjacent configs (one grid step in each of the two axes, including diagonals)."""
    keys = list(grid.keys())
    ia = grid[keys[0]].index(params[keys[0]])
    ib = grid[keys[1]].index(params[keys[1]])
    out = []
    for da in (-1, 0, 1):
        for db in (-1, 0, 1):
            if da == 0 and db == 0:
                continue
            a, b = ia + da, ib + db
            if 0 <= a < len(grid[keys[0]]) and 0 <= b < len(grid[keys[1]]):
                out.append({keys[0]: grid[keys[0]][a], keys[1]: grid[keys[1]][b]})
    return out


def pnl_after_removing_top(trades, k):
    pnl = sorted([t["pnl"] for t in trades], reverse=True)
    return float(sum(pnl[k:])) if len(pnl) > k else float(sum(pnl[len(pnl):]))
