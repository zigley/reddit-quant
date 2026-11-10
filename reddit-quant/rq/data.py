"""Price data: yfinance adjusted daily bars, saved as CSV with a manifest (retrieval date, sha256)."""
import json
import time

import pandas as pd

from .config import ROOT, sha256_file, sha256_text, canonical_json

PRICE_DIR = ROOT / "data" / "prices"
MANIFEST = ROOT / "data" / "manifest.json"
MANIFEST_DIR = ROOT / "data" / "manifests"


def price_path(sym):
    return PRICE_DIR / f"{sym}.csv"


def manifest_path(cfg):
    mid = cfg.get("market_id", "us_etf")
    if mid and mid != "us_etf":
        return MANIFEST_DIR / f"{mid}.json"
    return MANIFEST


def download(cfg):
    import yfinance as yf
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    d = cfg["data"]
    end_excl = (pd.Timestamp(d["end"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    files = {}
    for sym in cfg["universe"]:
        df = yf.download(sym, start=d["start"], end=end_excl, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df is None or df.empty:
            raise SystemExit(f"yfinance returned no rows for {sym}")
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "Date"
        path = price_path(sym)
        df.to_csv(path, float_format="%.6f")
        files[sym] = {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "rows": len(df),
                      "first": str(df.index.min().date()), "last": str(df.index.max().date())}
    alignment = _alignment_note({s: pd.read_csv(price_path(s), index_col=0, parse_dates=True)
                                 for s in cfg["universe"]}, cfg)
    manifest = {"source": "yfinance", "yfinance_version": yf.__version__, "adjust": "auto_adjust=True",
                "market_id": cfg.get("market_id", "us_etf"),
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "requested_start": d["start"],
                "requested_end_inclusive": d["end"],
                "note": "Adjusted prices can change retroactively when new dividends or splits occur. "
                        "Re-downloading later may give different checksums; compare to this manifest.",
                "alignment": alignment,
                "files": files}
    manifest["manifest_hash"] = sha256_text(canonical_json({k: v["sha256"] for k, v in files.items()}))
    path = manifest_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _alignment_note(prices, cfg):
    start = cfg.get("data", {}).get("start")
    idxs = {}
    for s, df in prices.items():
        if start is not None:
            df = df.loc[pd.Timestamp(start):]
        idxs[s] = df.index
    if not idxs:
        return {"method": "intersection", "common_bars": 0, "dropped": {}}
    common = None
    for idx in idxs.values():
        common = idx if common is None else common.intersection(idx)
    dropped = {s: int(len(idx) - len(common)) for s, idx in idxs.items()}
    first = last = None
    if len(common):
        first, last = str(common.min().date()), str(common.max().date())
    return {"method": "intersection", "common_bars": int(len(common)), "first": first, "last": last,
            "dropped_vs_own_calendar": dropped}


def load_manifest(cfg=None):
    path = manifest_path(cfg) if cfg is not None else MANIFEST
    with open(path) as f:
        return json.load(f)


def verify_manifest(cfg=None):
    m = load_manifest(cfg)
    bad = [s for s, v in m["files"].items() if sha256_file(ROOT / v["path"]) != v["sha256"]]
    if bad:
        raise SystemExit(f"Price files changed since manifest: {bad}")
    return m


def load_prices(cfg, end=None):
    """Return dict sym -> DataFrame (OHLCV), truncated at `end` inclusive when given.

    When align_calendars is true (the default), the intersection of dates across
    the universe is kept so Backtrader sees a shared calendar. Dropped bar counts
    belong in the market manifest.
    """
    out = {}
    start = cfg.get("data", {}).get("start")
    for sym in cfg["universe"]:
        df = pd.read_csv(price_path(sym), index_col=0, parse_dates=True)
        if start is not None:
            df = df.loc[pd.Timestamp(start):]
        if end is not None:
            df = df.loc[: pd.Timestamp(end)]
        out[sym] = df
    if cfg.get("align_calendars", True) and out:
        idx = None
        for df in out.values():
            idx = df.index if idx is None else idx.intersection(df.index)
        out = {s: df.loc[idx] for s, df in out.items()}
    return out


def sanity_checks(prices):
    issues = []
    idx0 = None
    first = None
    for sym, df in prices.items():
        if first is None:
            first, idx0 = sym, df.index
        if not df.index.equals(idx0):
            issues.append(f"{sym}: calendar differs from {first} ({len(df)} vs {len(idx0)} rows)")
        if (df[["Open", "High", "Low", "Close"]] <= 0).any().any():
            issues.append(f"{sym}: non-positive prices")
        if (df["High"] < df[["Open", "Close", "Low"]].max(axis=1) - 1e-6).any():
            issues.append(f"{sym}: High below Open/Close/Low on some bars")
        r = df["Close"].pct_change().abs()
        if (r > 0.25).any():
            issues.append(f"{sym}: {int((r > 0.25).sum())} daily moves > 25% (check adjustment)")
        if df.index.duplicated().any():
            issues.append(f"{sym}: duplicate dates")
        zero_vol = int((df["Volume"] == 0).sum())
        if zero_vol:
            issues.append(f"{sym}: {zero_vol} zero-volume bars")
    return issues
