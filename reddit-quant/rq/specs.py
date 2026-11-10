"""Versioned strategy specs. A spec is frozen (hashed, written read-only, recorded in the ledger)
BEFORE any evaluation. The runner re-verifies the hash from the file before it runs anything."""
import json
import os
import stat
from pathlib import Path

import yaml

from . import ledger
from .config import ROOT, canonical_json, sha256_text, gates_hash

RULES_TEXT = {
    "rsi_meanrev": "Long when RSI(rsi_n) < rsi_entry and close > SMA(trend_n=200). Exit when RSI > rsi_exit=60, "
                   "after max_hold=10 bars, or on a close below entry - 3 ATR(14). Fills at next open.",
    "ibs_meanrev": "Long when IBS=(close-low)/(high-low) < ibs_entry and close > SMA(trend_n). Exit when close > "
                   "prior day high, after max_hold=5 bars, or on a close below entry - 3 ATR(14). Next-open fills.",
    "sma_cross": "Long on a fresh cross of SMA(fast_n) above SMA(slow_n). Exit when fast < slow or on a close below "
                 "entry - 3 ATR(14). Next-open fills.",
    "donchian_breakout": "Long when close exceeds the prior entry_n-day high. Exit when close is below the prior "
                         "exit_n-day low or on a close below entry - 3 ATR(14). Next-open fills.",
    "bollinger_meanrev": "Long when close < lower Bollinger band(bb_n, bb_std) and close > SMA(200). Exit when close > "
                         "middle band, after max_hold=10 bars, or on a close below entry - 3 ATR(14).",
    "xs_momentum": "Every 21 bars rank the universe by lookback-bar return; hold the top_n names with positive return. "
                   "Exit names that drop out at a rebalance or on a close below entry - 3 ATR(14). Next-open fills.",
}


def _write_readonly(path, text):
    path = Path(path)
    if path.exists():
        os.chmod(path, 0o644)
    path.write_text(text)
    os.chmod(path, 0o444)


def spec_hash_of(content):
    c = {k: v for k, v in content.items() if k != "spec_hash"}
    return sha256_text(canonical_json(c))


def freeze_family_spec(cfg, con, family_id, template_name, templates, ideas, manifest, version="v1"):
    t = templates[template_name]
    content = {
        "kind": "family", "family_id": family_id, "version": version, "template": template_name,
        "rules": RULES_TEXT[template_name],
        "grid": t["grid"], "fixed_params": t["fixed"], "textbook_default_baseline": t["default"],
        "n_configs": len(t["grid"][list(t["grid"])[0]]) * len(t["grid"][list(t["grid"])[1]]),
        "universe": cfg["universe"], "timeframe": cfg["timeframe"], "risk_limits": cfg["risk_limits"],
        "costs": cfg["costs"], "execution": cfg["execution"], "splits": cfg["splits"],
        "selection_rule": cfg["selection_rule"],
        "market_id": cfg.get("market_id", "us_etf"),
        "primary_benchmark": cfg.get("primary_benchmark", "SPY"),
        "trading_days": cfg.get("metrics", {}).get("trading_days", 252),
        "source_ideas": ideas, "config_version": cfg["config_version"],
        "gates_hash": gates_hash(cfg), "data_manifest_hash": manifest["manifest_hash"],
        "labels": "retrospective, PROVISIONAL config",
    }
    return _freeze(con, content)


def freeze_candidate_spec(cfg, con, family_spec, params, selection_evidence, version="v1-selected"):
    content = {k: v for k, v in family_spec.items() if k != "spec_hash"}
    content.update({"kind": "candidate", "version": version, "parent_spec_hash": family_spec["spec_hash"],
                    "selected_params": params, "selection_evidence": selection_evidence})
    return _freeze(con, content)


def _freeze(con, content):
    h = spec_hash_of(content)
    content["spec_hash"] = h
    d = ROOT / "specs"
    d.mkdir(exist_ok=True)
    path = d / f"{content['family_id']}_{content['version']}.yaml"
    _write_readonly(path, yaml.safe_dump(content, sort_keys=False))
    con.execute("INSERT OR IGNORE INTO specs VALUES(?,?,?,?,?,?,?,?,?)",
                (h, content["family_id"], content["version"], content["kind"], str(path.relative_to(ROOT)),
                 ledger.now(), content["gates_hash"], content["data_manifest_hash"], canonical_json(content)))
    con.commit()
    return content


def load_verified_spec(path):
    spec = yaml.safe_load(Path(path).read_text())
    if spec_hash_of(spec) != spec["spec_hash"]:
        raise SystemExit(f"Spec {path} does not match its frozen hash. Refusing to run.")
    return spec
