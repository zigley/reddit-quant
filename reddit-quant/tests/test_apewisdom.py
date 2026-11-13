"""Tests for the ApeWisdom sentiment source. HTTP is mocked. Run: python tests/test_apewisdom.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from rq import apewisdom
from rq.config import load_config


class FakeResponse:
    def __init__(self, payload, status=200, url=""):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload
        self.headers = {}
        self.url = url

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


class FakeSession:
    def __init__(self, routes):
        # routes: exact URL -> FakeResponse or list of FakeResponse (for retries)
        self.routes = routes
        self.calls = []
        self.n_requests = 0

    def get(self, url, params=None, retries=4, timeout=60):
        self.n_requests += 1
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if url not in self.routes:
            r = FakeResponse({"error": "missing"}, status=404, url=url)
            r.raise_for_status()
        resp = self.routes[url]
        if isinstance(resp, list):
            if not resp:
                raise RuntimeError(f"no responses left for {url}")
            r = resp.pop(0)
        else:
            r = resp
        r.raise_for_status()
        return r


def _page(filter_name, page, pages, results, count=None):
    return {
        "count": count if count is not None else len(results),
        "pages": pages,
        "current_page": page,
        "results": results,
    }


def _item(rank, ticker, name, mentions, upvotes, rank_ago, mentions_ago):
    return {
        "rank": rank,
        "ticker": ticker,
        "name": name,
        "mentions": str(mentions),
        "upvotes": str(upvotes),
        "rank_24h_ago": str(rank_ago) if rank_ago is not None else None,
        "mentions_24h_ago": str(mentions_ago) if mentions_ago is not None else None,
    }


def test_filter_and_page_urls():
    base = "https://apewisdom.io/api/v1.0"
    assert apewisdom.filter_url(base, "all-stocks") == f"{base}/filter/all-stocks"
    assert apewisdom.page_url(base, "wallstreetbets", 1) == f"{base}/filter/wallstreetbets/page/1"
    assert apewisdom.page_url(base + "/", "stocks", 4) == f"{base}/filter/stocks/page/4"
    print("ok urls")


def test_normalize_and_delta():
    row = apewisdom.normalize_row(
        _item(3, "aapl", "Apple Inc.", "40", "100", "8", "15"),
        "all-stocks",
        "2026-11-13T07:00:00Z",
    )
    assert row["ticker"] == "AAPL"
    assert row["name"] == "Apple Inc."
    assert row["mentions"] == 40
    assert row["upvotes"] == 100
    assert row["rank"] == 3
    assert row["rank_24h_ago"] == 8
    assert row["mentions_24h_ago"] == 15
    assert row["mention_delta"] == 25
    assert row["filter"] == "all-stocks"
    assert row["fetched_at"] == "2026-11-13T07:00:00Z"
    amp = apewisdom.normalize_row(
        {"ticker": "SPY", "name": "SPDR S&amp;P 500 ETF Trust", "mentions": "1", "upvotes": "1", "rank": 4},
        "all-stocks",
        "2026-11-13T07:00:00Z",
    )
    assert amp["name"] == "SPDR S&P 500 ETF Trust"
    missing = apewisdom.normalize_row(
        {"ticker": "XYZ", "mentions": "2", "upvotes": "1", "rank": 9},
        "stocks",
        "2026-11-13T07:00:00Z",
    )
    assert missing["mentions_24h_ago"] is None
    assert missing["mention_delta"] is None
    print("ok normalize")


def test_pagination_and_404(tmp_path=None):
    base = "https://apewisdom.io/api/v1.0"
    p1 = _page("all-stocks", 1, 2, [_item(1, "NVDA", "NVIDIA", 100, 500, 2, 80)], count=2)
    p2 = _page("all-stocks", 2, 2, [_item(2, "TSLA", "Tesla", 50, 200, 1, 90)], count=2)
    sess = FakeSession({
        f"{base}/filter/all-stocks/page/1": FakeResponse(p1),
        f"{base}/filter/all-stocks/page/2": FakeResponse(p2),
        f"{base}/filter/wallstreetbets/page/1": FakeResponse(
            _page("wallstreetbets", 1, 1, [_item(1, "NVDA", "NVIDIA", 70, 300, 3, 20)], count=1)
        ),
        f"{base}/filter/stocks/page/1": FakeResponse(
            _page("stocks", 1, 1, [_item(1, "MSFT", "Microsoft", 10, 15, 2, 8)], count=1)
        ),
    })
    rows, pages = apewisdom.fetch_filter(sess, base, "all-stocks")
    assert len(pages) == 2
    assert [r["ticker"] for r in rows] == ["NVDA", "TSLA"]
    assert rows[0]["mention_delta"] == 20
    assert rows[1]["mention_delta"] == -40
    assert sess.calls[0]["timeout"] == 30

    try:
        apewisdom.fetch_filter(sess, base, "not-a-real-filter")
        raise AssertionError("expected FilterUnavailable")
    except apewisdom.FilterUnavailable as e:
        assert "404" in str(e)
    print("ok pagination and 404")


def test_pull_writes_cache_and_skips_missing_filter():
    base = "https://apewisdom.io/api/v1.0"
    sess = FakeSession({
        f"{base}/filter/all-stocks/page/1": FakeResponse(
            _page("all-stocks", 1, 1, [_item(1, "GME", "GameStop", 12, 40, 5, 4)], count=1)
        ),
        f"{base}/filter/wallstreetbets/page/1": FakeResponse(
            _page("wallstreetbets", 1, 1, [_item(1, "GME", "GameStop", 9, 30, 4, 3)], count=1)
        ),
    })
    with tempfile.TemporaryDirectory() as td:
        cfg = {
            "live_trading": False,
            "apewisdom": {
                "base_url": base,
                "filters": ["all-stocks", "wallstreetbets", "pennystocks"],
                "cache_dir": td,
                "rate_limit_seconds": 2.0,
                "timeout_seconds": 30,
                "user_agent": "reddit-quant-test/0.1",
            },
        }
        result = apewisdom.pull(cfg, sess=sess)
        assert result["errors"] and result["errors"][0]["filter"] == "pennystocks"
        assert Path(result["raw_path"]).is_file()
        assert Path(result["csv_path"]).is_file()
        assert result["raw_path"].name.startswith("apewisdom_")
        assert result["raw_path"].suffix == ".json"
        assert result["csv_path"].suffix == ".csv"
        tickers = [r["ticker"] for r in result["rows"]]
        assert tickers == ["GME", "GME"]
        assert {r["filter"] for r in result["rows"]} == {"all-stocks", "wallstreetbets"}
        raw = json.loads(Path(result["raw_path"]).read_text())
        assert "all-stocks" in raw["filters"]
        assert raw["filters"]["all-stocks"]["pages_fetched"] == 1
        text = Path(result["csv_path"]).read_text()
        assert "ticker,name,mentions,upvotes,rank,rank_24h_ago,mentions_24h_ago,mention_delta,filter,fetched_at" in text
        assert "GME" in text
        summary = apewisdom.format_summary(result["rows"])
        assert "Top 15 by mentions, all-stocks" in summary
        assert "GME" in summary
        assert "Top 10 by mentions, pennystocks" in summary
        assert "(no rows)" in summary
        jumps = apewisdom.biggest_jumps(apewisdom.rows_for_filter(result["rows"], "all-stocks"), 5)
        assert jumps[0]["mention_delta"] == 8
    print("ok pull cache and skip")


def test_rate_floor_and_config_defaults():
    cfg = load_config()
    assert cfg["live_trading"] is False
    assert cfg["reddit"]["sentiment"]["primary"] == "apewisdom"
    assert cfg["reddit"]["arctic_shift_enabled"] is False
    assert "arctic_shift" not in cfg["reddit"]["method_order"]
    assert cfg["apewisdom"]["enabled"] is True
    assert cfg["apewisdom"]["filters"] == ["all-stocks", "wallstreetbets", "stocks", "pennystocks"]
    aw = apewisdom.apewisdom_config({"live_trading": False, "apewisdom": {"rate_limit_seconds": 0.1}})
    assert aw["rate_limit_seconds"] == 2.0
    print("ok config defaults and rate floor")


def test_max_pages_stops_early():
    base = "https://apewisdom.io/api/v1.0"
    sess = FakeSession({
        f"{base}/filter/all-stocks/page/1": FakeResponse(
            _page("all-stocks", 1, 5, [_item(1, "A", "A Inc.", 1, 1, 1, 1)], count=5)
        ),
        f"{base}/filter/all-stocks/page/2": FakeResponse(
            _page("all-stocks", 2, 5, [_item(2, "B", "B Inc.", 1, 1, 1, 1)], count=5)
        ),
    })
    rows, pages = apewisdom.fetch_filter(sess, base, "all-stocks", max_pages=1)
    assert len(pages) == 1
    assert [r["ticker"] for r in rows] == ["A"]
    assert all("page/2" not in c["url"] for c in sess.calls)
    print("ok max_pages")


if __name__ == "__main__":
    test_filter_and_page_urls()
    test_normalize_and_delta()
    test_pagination_and_404()
    test_pull_writes_cache_and_skips_missing_filter()
    test_rate_floor_and_config_defaults()
    test_max_pages_stops_early()
    print("all apewisdom tests passed")
