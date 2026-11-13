"""Reddit scraper for r/algotrading and r/Daytrading.

Access methods, tried in order (config reddit.method_order). The method that actually
returned data is stored on every row as access_method:

  1. praw           needs REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in the environment (read-only OAuth)
  2. public_json    old.reddit.com public .json endpoints with a proper User-Agent
  3. arctic_shift   third-party public archive of Reddit posts/comments (arctic-shift.photon-reddit.com).
                    Off by default (reddit.arctic_shift_enabled). ToS-gray. Used only when enabled
                    and earlier methods fail. Disclosed in every report.

Ticker mention sentiment is a separate source: rq/apewisdom.py (primary, see config apewisdom).

Rules:
  * rate limit about 1 request per 2 seconds, exponential backoff on 429/5xx
  * author and username fields are dropped at ingest, before anything is written
  * all text is untrusted data: it is stored and regex-parsed, never executed or followed
"""
import json
import os
import time
from datetime import datetime, timezone

import requests

from . import ledger
from .config import ROOT

ARCTIC = "https://arctic-shift.photon-reddit.com/api"


class Blocked(Exception):
    pass


def _iso(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


class RateLimitedSession:
    def __init__(self, user_agent, min_interval=2.0):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent
        self.min_interval = min_interval
        self.last = 0.0
        self.n_requests = 0

    def get(self, url, params=None, retries=4, timeout=60):
        delay = 3.0
        for attempt in range(retries + 1):
            wait = self.min_interval - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.n_requests += 1
            try:
                r = self.s.get(url, params=params, timeout=timeout, allow_redirects=True)
            except requests.RequestException as e:
                if attempt == retries:
                    raise
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code in (403, 401):
                raise Blocked(f"HTTP {r.status_code} from {url}")
            if r.status_code == 429 or r.status_code >= 500:
                ra = r.headers.get("Retry-After") or r.headers.get("x-ratelimit-reset")
                try:
                    pause = min(float(ra), 60) if ra else delay
                except ValueError:
                    pause = delay
                time.sleep(pause)
                delay *= 2
                continue
            if r.status_code == 422:
                raise ValueError(f"HTTP 422: {r.text[:200]}")
            r.raise_for_status()
            return r
        raise RuntimeError(f"gave up on {url}")


# ---------- normalisers (drop author fields here) ----------
def norm_post(d, method, retrieved_at):
    pid = d["id"]
    permalink = d.get("permalink") or f"/r/{d.get('subreddit', '')}/comments/{pid}/"
    return {
        "post_id": pid, "subreddit": d.get("subreddit"), "title": d.get("title") or "",
        "selftext": d.get("selftext") or "", "url": "https://www.reddit.com" + permalink,
        "created_utc": int(d.get("created_utc", 0)), "created_date": _iso(d.get("created_utc", 0)),
        "score": int(d.get("score") or 0), "num_comments": int(d.get("num_comments") or 0),
        "flair": d.get("link_flair_text"), "retrieved_at": retrieved_at, "access_method": method,
    }


def norm_comment(d, post_id, post_url, method, retrieved_at):
    cid = d["id"]
    url = d.get("permalink")
    url = ("https://www.reddit.com" + url) if url else f"{post_url}{cid}/"
    return {
        "comment_id": cid, "post_id": post_id, "body": d.get("body") or "", "url": url,
        "created_utc": int(d.get("created_utc", 0)), "created_date": _iso(d.get("created_utc", 0)),
        "score": int(d.get("score") or 0), "retrieved_at": retrieved_at, "access_method": method,
    }


# ---------- method 1: PRAW ----------
def praw_available():
    return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))


def fetch_praw(cfg, sub, keywords, limit=100):
    import praw
    reddit = praw.Reddit(client_id=os.environ["REDDIT_CLIENT_ID"],
                         client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                         user_agent=cfg["reddit"]["user_agent"], check_for_async=False)
    reddit.read_only = True
    out, ts = [], ledger.now()
    for kw in keywords:
        for s in reddit.subreddit(sub).search(kw, sort="top", time_filter="all", limit=limit):
            out.append(norm_post({"id": s.id, "subreddit": sub, "title": s.title, "selftext": s.selftext,
                                  "permalink": s.permalink, "created_utc": s.created_utc, "score": s.score,
                                  "num_comments": s.num_comments, "link_flair_text": s.link_flair_text},
                                 "praw", ts))
        time.sleep(cfg["reddit"]["rate_limit_seconds"])
    return out


def fetch_praw_comments(cfg, post, limit=60):
    import praw
    reddit = praw.Reddit(client_id=os.environ["REDDIT_CLIENT_ID"],
                         client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                         user_agent=cfg["reddit"]["user_agent"], check_for_async=False)
    sub = reddit.submission(id=post["post_id"])
    sub.comment_sort = "top"
    sub.comments.replace_more(limit=0)
    ts = ledger.now()
    out = []
    for c in list(sub.comments.list())[:limit]:
        out.append(norm_comment({"id": c.id, "body": c.body, "created_utc": c.created_utc, "score": c.score,
                                 "permalink": c.permalink}, post["post_id"], post["url"], "praw", ts))
    time.sleep(cfg["reddit"]["rate_limit_seconds"])
    return out


# ---------- method 2: public JSON ----------
def fetch_public_json(cfg, sess, sub, keywords):
    out, ts = [], ledger.now()
    for kw in keywords:
        url = f"https://old.reddit.com/r/{sub}/search.json"
        r = sess.get(url, params={"q": kw, "restrict_sr": 1, "sort": "top", "t": "all", "limit": 100,
                                  "raw_json": 1})
        for ch in r.json()["data"]["children"]:
            out.append(norm_post(ch["data"], "public_json", ts))
    return out


def fetch_public_json_comments(cfg, sess, post, limit=60):
    url = f"https://old.reddit.com/r/{post['subreddit']}/comments/{post['post_id']}.json"
    r = sess.get(url, params={"limit": limit, "sort": "top", "raw_json": 1})
    ts, out = ledger.now(), []

    def walk(children):
        for ch in children:
            if ch.get("kind") != "t1":
                continue
            d = ch["data"]
            out.append(norm_comment(d, post["post_id"], post["url"], "public_json", ts))
            rep = d.get("replies")
            if isinstance(rep, dict):
                walk(rep["data"]["children"])
    walk(r.json()[1]["data"]["children"])
    return out[:limit]


# ---------- method 3: Arctic Shift archive ----------
def fetch_arctic(cfg, sess, sub, keywords):
    out, ts = [], ledger.now()
    rc = cfg["reddit"]
    for kw in keywords:
        for year in range(rc["year_from"], rc["year_to"] + 1):
            params = {"subreddit": sub, "query": kw, "after": f"{year}-01-01", "before": f"{year + 1}-01-01",
                      "limit": 100, "sort": "desc"}
            try:
                r = sess.get(f"{ARCTIC}/posts/search", params=params)
            except ValueError as e:
                print("skip", sub, kw, year, e)
                continue
            for d in (r.json().get("data") or []):
                out.append(norm_post(d, "arctic_shift", ts))
    return out


def fetch_arctic_comments(cfg, sess, post, limit=100):
    r = sess.get(f"{ARCTIC}/comments/search", params={"link_id": f"t3_{post['post_id']}", "limit": limit})
    ts = ledger.now()
    return [norm_comment(d, post["post_id"], post["url"], "arctic_shift", ts) for d in (r.json().get("data") or [])]


# ---------- orchestration ----------
def store(con, posts, comments):
    for p in posts:
        con.execute("INSERT OR IGNORE INTO raw_posts VALUES(:post_id,:subreddit,:title,:selftext,:url,:created_utc,"
                    ":created_date,:score,:num_comments,:flair,:retrieved_at,:access_method)", p)
    for c in comments:
        con.execute("INSERT OR IGNORE INTO raw_comments VALUES(:comment_id,:post_id,:body,:url,:created_utc,"
                    ":created_date,:score,:retrieved_at,:access_method)", c)
    con.commit()


def run_scrape(cfg, con, cycle, out_dir=None):
    rc = cfg["reddit"]
    out_dir = out_dir or ROOT / "data" / "reddit"
    out_dir.mkdir(parents=True, exist_ok=True)
    sess = RateLimitedSession(rc["user_agent"], rc["rate_limit_seconds"])
    method_used, posts = None, []
    for method in rc["method_order"]:
        try:
            if method == "praw":
                if not praw_available():
                    ledger.log_access(con, cycle, "praw", "-", "skipped", "REDDIT_CLIENT_ID/SECRET not set")
                    continue
                for sub in rc["subreddits"]:
                    posts += fetch_praw(cfg, sub, rc["keywords"])
            elif method == "public_json":
                probe = sess.get("https://old.reddit.com/r/algotrading/top.json", params={"t": "week", "limit": 1})
                json.loads(probe.text)
                for sub in rc["subreddits"]:
                    posts += fetch_public_json(cfg, sess, sub, rc["keywords"])
            elif method == "arctic_shift":
                if not rc.get("arctic_shift_enabled", False):
                    ledger.log_access(con, cycle, "arctic_shift", "-", "skipped",
                                      "arctic_shift_enabled is false (ToS-gray, off by default)")
                    continue
                for sub in rc["subreddits"]:
                    posts += fetch_arctic(cfg, sess, sub, rc["keywords"])
            method_used = method
            ledger.log_access(con, cycle, method, "posts", "ok", f"{len(posts)} raw rows")
            break
        except Blocked as e:
            ledger.log_access(con, cycle, method, "posts", "blocked", e)
        except Exception as e:
            ledger.log_access(con, cycle, method, "posts", "error", repr(e))
    if not method_used:
        raise SystemExit("No Reddit access method worked. See access_log.")

    # de-duplicate and filter to posts that look like they might contain rules
    uniq = {}
    for p in posts:
        uniq[p["post_id"]] = p
    cand = [p for p in uniq.values() if p["score"] >= rc["min_score"] and len(p["selftext"]) >= rc["min_selftext_chars"]
            and p["selftext"] not in ("[removed]", "[deleted]")]
    cand.sort(key=lambda p: -p["score"])
    print(f"{len(uniq)} unique posts, {len(cand)} pass filters, method={method_used}")
    top = cand[: rc["max_posts_for_comments"]]
    comments = []
    for p in top:
        try:
            if method_used == "praw":
                comments += fetch_praw_comments(cfg, p)
            elif method_used == "public_json":
                comments += fetch_public_json_comments(cfg, sess, p)
            else:
                comments += fetch_arctic_comments(cfg, sess, p)
        except Exception as e:
            ledger.log_access(con, cycle, method_used, f"comments:{p['post_id']}", "error", repr(e))
    store(con, cand, comments)
    ledger.log_access(con, cycle, method_used, "summary", "ok",
                      f"requests={sess.n_requests} raw_unique={len(uniq)} kept={len(cand)} comments={len(comments)}")
    stamp = time.strftime("%Y%m%d")
    with open(out_dir / f"posts_{stamp}.jsonl", "w") as f:
        for p in cand:
            f.write(json.dumps(p) + "\n")
    with open(out_dir / f"comments_{stamp}.jsonl", "w") as f:
        for c in comments:
            f.write(json.dumps(c) + "\n")
    return {"method": method_used, "unique_posts": len(uniq), "kept_posts": len(cand), "comments": len(comments),
            "requests": sess.n_requests}


if __name__ == "__main__":
    from .config import load_config
    cfg = load_config()
    con = ledger.connect()
    print(run_scrape(cfg, con, cycle=1))
