import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f)
    assert_paper_only(cfg)
    return cfg


def assert_paper_only(cfg):
    if cfg.get("live_trading") is not False:
        raise SystemExit("live_trading must be false. This framework never trades live.")
    if os.environ.get("RQ_LIVE_TRADING"):
        raise SystemExit("RQ_LIVE_TRADING is set. Refusing to run. Live trading is not supported.")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(s):
    return hashlib.sha256(s.encode()).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gates_hash(cfg):
    return sha256_text(canonical_json({
        "gates": cfg["gates"], "splits": cfg["splits"],
        "costs": cfg["costs"], "overfitting": cfg["overfitting"],
        "risk_limits": cfg["risk_limits"],
        "primary_benchmark": cfg.get("primary_benchmark", "SPY"),
        "trading_days": cfg.get("metrics", {}).get("trading_days", 252),
    }))


def trading_days(cfg):
    return int(cfg.get("metrics", {}).get("trading_days", 252))


def primary_benchmark(cfg):
    return cfg.get("primary_benchmark", "SPY")


def _merge(base, overlay):
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_market(cfg, market_id=None):
    """Return a config for one research universe.

    Top-level keys stay as the cycle-1 US ETF defaults. A named market overlays
    universe, splits, costs, data range, trading days and the primary benchmark.
    Gate thresholds are never changed here.
    """
    out = dict(cfg)
    mid = market_id or cfg.get("market_id")
    markets = cfg.get("markets") or {}
    if mid and mid in markets:
        out = _merge(out, markets[mid])
        out["market_id"] = mid
    else:
        if mid and mid not in ("us_etf", None) and mid not in markets:
            raise SystemExit(f"unknown market {mid}")
        out["market_id"] = mid or "us_etf"
    out.setdefault("primary_benchmark", "SPY")
    out.setdefault("align_calendars", True)
    return out
