"""ApeWisdom Reddit mention sentiment source.

Primary ticker-sentiment feed for reddit-quant. Free, no API key.
Docs: https://apewisdom.io/api

This module does not place orders and does not talk to a broker.
ApeWisdom refreshes about every 30 minutes.
"""
import argparse
import html
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import ROOT, load_config
from .reddit_scraper import RateLimitedSession

DEFAULT_BASE = "https://apewisdom.io/api/v1.0"
DEFAULT_FILTERS = ["all-stocks", "wallstreetbets", "stocks", "pennystocks"]
DEFAULT_UA = (
    "reddit-quant-research/0.1 "
    "(ApeWisdom sentiment pull; +https://github.com/zigley/reddit-quant)"
)
FIELDNAMES = [
    "ticker", "name", "mentions", "upvotes", "rank",
    "rank_24h_ago", "mentions_24h_ago", "mention_delta",
    "filter", "fetched_at",
]


def _num(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default


def filter_url(base, filter_name, page=None):
    base = base.rstrip("/")
    if page is None or page == 1:
        # page 1 is also valid as /filter/{filter}/page/1
        return f"{base}/filter/{filter_name}"
    return f"{base}/filter/{filter_name}/page/{page}"


def page_url(base, filter_name, page):
    return f"{base.rstrip('/')}/filter/{filter_name}/page/{int(page)}"


def normalize_row(item, filter_name, fetched_at):
    mentions = _num(item.get("mentions"), 0)
    mentions_24h = _num(item.get("mentions_24h_ago"))
    delta = None
    if mentions is not None and mentions_24h is not None:
        delta = mentions - mentions_24h
    return {
        "ticker": (item.get("ticker") or "").strip().upper(),
        "name": html.unescape(item.get("name") or ""),
        "mentions": mentions,
        "upvotes": _num(item.get("upvotes"), 0),
        "rank": _num(item.get("rank")),
        "rank_24h_ago": _num(item.get("rank_24h_ago")),
        "mentions_24h_ago": mentions_24h,
        "mention_delta": delta,
        "filter": filter_name,
        "fetched_at": fetched_at,
    }


def apewisdom_config(cfg):
    aw = dict(cfg.get("apewisdom") or {})
    reddit = cfg.get("reddit") or {}
    aw.setdefault("enabled", True)
    aw.setdefault("base_url", DEFAULT_BASE)
    aw.setdefault("filters", list(DEFAULT_FILTERS))
    aw.setdefault("rate_limit_seconds", reddit.get("rate_limit_seconds", 2.0))
    aw.setdefault("timeout_seconds", 30)
    aw.setdefault("max_pages", None)
    aw.setdefault("user_agent", reddit.get("user_agent") or DEFAULT_UA)
    aw.setdefault("cache_dir", "data/cache")
    if aw["rate_limit_seconds"] < 2.0:
        aw["rate_limit_seconds"] = 2.0
    return aw


def fetch_filter(sess, base, filter_name, max_pages=None, timeout=30):
    """Fetch every page for one filter. Returns (rows, raw_pages).

    Unknown or unsupported filters raise FilterUnavailable after the first request
    if the API returns 404 or an empty/invalid body.
    """
    raw_pages = []
    rows = []
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    page = 1
    total_pages = 1
    while True:
        url = page_url(base, filter_name, page)
        try:
            r = sess.get(url, timeout=timeout)
        except requests.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404 and page == 1:
                raise FilterUnavailable(f"filter {filter_name!r} returned HTTP 404") from e
            raise
        try:
            payload = r.json()
        except ValueError as e:
            if page == 1:
                raise FilterUnavailable(f"filter {filter_name!r} returned non-JSON") from e
            raise
        if not isinstance(payload, dict):
            raise FilterUnavailable(f"filter {filter_name!r} returned unexpected payload")
        raw_pages.append(payload)
        results = payload.get("results") or []
        for item in results:
            rows.append(normalize_row(item, filter_name, fetched_at))
        total_pages = int(payload.get("pages") or page)
        current = int(payload.get("current_page") or page)
        if max_pages is not None and current >= int(max_pages):
            break
        if current >= total_pages or not results:
            break
        page = current + 1
    return rows, raw_pages


class FilterUnavailable(Exception):
    pass


def cache_paths(cache_dir, when=None):
    when = when or datetime.now()
    stamp = when.strftime("%Y%m%d_%H%M")
    cache_dir = Path(cache_dir)
    return cache_dir / f"apewisdom_{stamp}.json", cache_dir / f"apewisdom_{stamp}.csv"


def write_cache(raw_path, csv_path, raw_obj, rows):
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w") as f:
        json.dump(raw_obj, f, indent=2)
        f.write("\n")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return raw_path, csv_path


def pull(cfg, sess=None):
    """Fetch configured filters, cache raw JSON and a normalized CSV, return rows."""
    aw = apewisdom_config(cfg)
    if not aw.get("enabled", True):
        raise SystemExit("apewisdom.enabled is false")
    cache_dir = aw["cache_dir"]
    if not Path(cache_dir).is_absolute():
        cache_dir = ROOT / cache_dir
    sess = sess or RateLimitedSession(aw["user_agent"], aw["rate_limit_seconds"])
    all_rows = []
    raw = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": aw["base_url"],
        "filters": {},
        "errors": [],
    }
    for name in aw["filters"]:
        try:
            rows, pages = fetch_filter(
                sess, aw["base_url"], name,
                max_pages=aw.get("max_pages"),
                timeout=aw.get("timeout_seconds", 30),
            )
        except FilterUnavailable as e:
            raw["errors"].append({"filter": name, "error": str(e)})
            print(f"skip {name}: {e}", file=sys.stderr)
            continue
        raw["filters"][name] = {
            "count": pages[-1].get("count") if pages else 0,
            "pages": pages[-1].get("pages") if pages else 0,
            "pages_fetched": len(pages),
            "responses": pages,
        }
        all_rows.extend(rows)
        print(f"{name}: {len(rows)} rows across {len(pages)} page(s)")
    raw_path, csv_path = cache_paths(cache_dir)
    write_cache(raw_path, csv_path, raw, all_rows)
    return {
        "rows": all_rows,
        "raw_path": raw_path,
        "csv_path": csv_path,
        "errors": raw["errors"],
        "fetched_at": raw["fetched_at"],
        "requests": getattr(sess, "n_requests", None),
    }


def rows_for_filter(rows, filter_name):
    return [r for r in rows if r["filter"] == filter_name]


def top_by_mentions(rows, n=15):
    return sorted(rows, key=lambda r: (r["mentions"] or 0, -(r["rank"] or 10**9)), reverse=True)[:n]


def biggest_jumps(rows, n=15):
    scored = [r for r in rows if r.get("mention_delta") is not None]
    return sorted(scored, key=lambda r: r["mention_delta"], reverse=True)[:n]


def format_summary(rows):
    lines = []
    stocks = rows_for_filter(rows, "all-stocks")
    wsb = rows_for_filter(rows, "wallstreetbets")
    pennies = rows_for_filter(rows, "pennystocks")
    lines.append("ApeWisdom pull summary")
    if rows:
        lines.append(f"fetched_at (UTC): {rows[0]['fetched_at']}")
    lines.append("")
    lines.append("Top 15 by mentions, all-stocks")
    lines.extend(_table(top_by_mentions(stocks, 15)))
    lines.append("")
    lines.append("Top 15 by mentions, wallstreetbets")
    lines.extend(_table(top_by_mentions(wsb, 15)))
    lines.append("")
    lines.append("Biggest 24h mention jumps, all-stocks")
    lines.extend(_table(biggest_jumps(stocks, 15), show_delta=True))
    lines.append("")
    lines.append("Top 10 by mentions, pennystocks")
    lines.extend(_table(top_by_mentions(pennies, 10)))
    return "\n".join(lines) + "\n"


def _table(rows, show_delta=False):
    if not rows:
        return ["  (no rows)"]
    out = []
    for i, r in enumerate(rows, 1):
        delta = r.get("mention_delta")
        prior = r.get("mentions_24h_ago")
        extra = ""
        if show_delta:
            sign = "+" if (delta or 0) >= 0 else ""
            extra = f"  delta {sign}{delta}  (was {prior})"
        out.append(
            f"  {i:2d}. {r['ticker']:<8} mentions {r['mentions']:<6} "
            f"upvotes {r['upvotes']:<7} rank {r['rank']} "
            f"({r.get('name') or ''}){extra}"
        )
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Pull ApeWisdom Reddit ticker sentiment (research only).")
    p.add_argument("--config", default=None, help="path to config.yaml")
    p.add_argument("--max-pages", type=int, default=None, help="cap pages per filter")
    p.add_argument("--filters", default=None, help="comma-separated filter names")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    if args.max_pages is not None:
        cfg.setdefault("apewisdom", {})
        cfg["apewisdom"]["max_pages"] = args.max_pages
    if args.filters:
        cfg.setdefault("apewisdom", {})
        cfg["apewisdom"]["filters"] = [s.strip() for s in args.filters.split(",") if s.strip()]
    result = pull(cfg)
    print(format_summary(result["rows"]))
    print(f"raw cache: {result['raw_path']}")
    print(f"table:     {result['csv_path']}")
    if result["errors"]:
        print(f"errors:    {result['errors']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
