"""Heuristic rule extraction from Reddit posts into structured idea records.

Pure regex and keyword matching. Reddit text is untrusted data: it is never executed,
never used as an instruction, and posts containing instruction-like text are flagged.
Everything is labelled by who said it:
  A source_says   what the post text states (extracted, quoted, truncated)
  B interpretation  the parser's reading (family assignment, rationale)
  C proposed_modifications  what we change to make it testable
"""
import json
import math
import re

from . import ledger
from .config import ROOT

FAMILY_INFO = {
    # family: (template or None, plausibility prior 0-1, rationale, decay reasons)
    "ibs_meanrev": ("ibs_meanrev", 0.70,
                    "Short-term reversal after weak closes; liquidity provision and overreaction.",
                    "Crowding, lower volatility regimes, microstructure change, edge concentrated in a few years."),
    "rsi_meanrev": ("rsi_meanrev", 0.75,
                    "Short-term oversold bounces in uptrending index ETFs (reversal, liquidity provision).",
                    "Crowding, regime shifts in index behaviour, edge shrinks after costs at high turnover."),
    "bollinger_meanrev": ("bollinger_meanrev", 0.60,
                          "Price stretched below its recent band tends to revert (overreaction).",
                          "Band breaks in trending markets, parameter sensitivity, costs."),
    "sma_cross": ("sma_cross", 0.85,
                  "Time-series momentum and trend persistence (behavioural underreaction, risk-premium timing).",
                  "Whipsaw in range markets, long flat stretches, drawdown-reduction benefit may be the only edge."),
    "donchian_breakout": ("donchian_breakout", 0.70,
                          "Breakouts proxy trend initiation (herding, underreaction).",
                          "False breakouts, high turnover costs, regime dependence."),
    "xs_momentum": ("xs_momentum", 0.90,
                    "Cross-sectional momentum: documented across asset classes (Jegadeesh-Titman, Moskowitz et al.).",
                    "Momentum crashes, crowding, small cross-section of 13 ETFs limits dispersion."),
    "gap_fade": (None, 0.40, "Overnight gaps overreact and partially fill.",
                 "Needs same-bar or open fills that this framework forbids; slippage dominates."),
    "opening_range_breakout": (None, 0.40, "Early range breakouts as intraday momentum.",
                               "Intraday data and costs; crowded; not daily-testable."),
    "pairs_stat_arb": (None, 0.60, "Relative-value convergence between related instruments.",
                       "Cointegration breaks, shorting disabled in v1, data and borrow needs."),
    "vwap_intraday": (None, 0.35, "Reversion to or trend away from VWAP intraday.", "Intraday data required."),
    "macd_cross": (None, 0.45, "Momentum oscillator crossover.", "Lagging, overlaps with MA cross."),
    "ml_model": (None, 0.35, "Learned predictive model on features.",
                 "Leakage, overfitting, unreported evaluation, non-stationarity."),
    "options_strategy": (None, 0.30, "Premium selling or directional options structures.",
                         "Derivatives disabled in v1."),
    "volume_signal": (None, 0.40, "Volume expansion confirms moves.", "Weak standalone evidence, ambiguous rules."),
    "other": (None, 0.20, "Unclear.", "Unclear."),
}

RE = {
    "ibs": re.compile(r"\bibs\b|internal bar strength", re.I),
    "rsi": re.compile(r"\brsi\b|relative strength index", re.I),
    "boll": re.compile(r"bollinger|\bbbands?\b", re.I),
    "cross": re.compile(r"(sma|ema|moving average|\bma\b|\bmas\b).{0,50}(cross|crossover|golden cross|death cross)|"
                        r"golden cross|death cross|\b(50|100)[- /]*(day)?[- /]*(and|/|x|vs)[- /]*200", re.I | re.S),
    "above_ma": re.compile(r"(above|below|over|under)\s+(the\s+)?(\d{2,3})[- ]?(day|d)?\s*(sma|ema|moving average|ma)", re.I),
    "breakout": re.compile(r"breakout|break out|donchian|\d+[- ]?(day|bar|period|week)s?\s*(high|low)|new highs?", re.I),
    "momentum": re.compile(r"momentum|relative strength(?! index)|sector rotation|dual momentum|top[- ]?\d+ (etf|sector)",
                           re.I),
    "gap": re.compile(r"\bgaps?\b|gapped|gap[- ](up|down|fade|fill)", re.I),
    "orb": re.compile(r"opening range|\borb\b", re.I),
    "pairs": re.compile(r"pairs? trad|cointegrat|stat(istical)?[- ]?arb|spread trad|market neutral", re.I),
    "vwap": re.compile(r"\bvwap\b", re.I),
    "macd": re.compile(r"\bmacd\b", re.I),
    "ml": re.compile(r"\blstm\b|reinforcement learning|\bppo\b|random forest|xgboost|neural net|machine learning|"
                     r"deep learning|transformer", re.I),
    "options": re.compile(r"\boptions?\b|iron condor|theta|0dte|calls?\b|puts?\b", re.I),
    "volume": re.compile(r"volume (spike|surge|breakout|expansion)|relative volume|rvol", re.I),
    "strategy_word": re.compile(r"strateg|backtest|back-test|signal|entry|exit|system|edge|rules?\b", re.I),
}
INTRADAY = re.compile(r"\b\d+\s*-?\s*(min|minute|m)\b|\b[1-9]\s?h\b|hourly|intraday|scalp|tick|0dte|5m\b|15m\b|1m\b", re.I)
DAILY = re.compile(r"\bdaily\b|\bd1\b|end of day|\beod\b|swing|day moving average|\d+[- ]?day\b|weekly|monthly", re.I)
MARKETS = [("crypto", re.compile(r"\bbtc\b|bitcoin|\beth\b|crypto|altcoin", re.I)),
           ("futures", re.compile(r"\bes\b|\bnq\b|\bmes\b|\bmnq\b|futures|\bcl\b", re.I)),
           ("forex", re.compile(r"forex|\bfx\b|eurusd|gbpusd", re.I)),
           ("options", re.compile(r"\boptions?\b|iron condor|0dte", re.I)),
           ("ETFs", re.compile(r"\betfs?\b|\bspy\b|\bqqq\b|\bsectors?\b", re.I)),
           ("stocks", re.compile(r"\bstocks?\b|equities|s&p|sp500|nasdaq", re.I))]
CLAIM = {"sharpe": re.compile(r"sharpe[^0-9\-]{0,15}(-?\d+(?:\.\d+)?)", re.I),
         "cagr": re.compile(r"(cagr|annual(?:ized|ised)?\s*return|apr)[^0-9\-]{0,15}(-?\d+(?:\.\d+)?)\s*%?", re.I),
         "win_rate": re.compile(r"win\s*rate[^0-9]{0,15}(\d+(?:\.\d+)?)\s*%", re.I),
         "profit_factor": re.compile(r"profit factor[^0-9]{0,15}(\d+(?:\.\d+)?)", re.I),
         "max_dd": re.compile(r"(max(?:imum)?\s*)?drawdown[^0-9\-]{0,15}(-?\d+(?:\.\d+)?)\s*%?", re.I)}
EVID = {"oos": re.compile(r"out[- ]of[- ]sample|\boos\b|walk[- ]forward|forward[- ]test|paper trad|live trad", re.I),
        "costs": re.compile(r"commission|slippage|spread cost|fees|transaction cost", re.I),
        "code": re.compile(r"github\.com|gist\.|pastebin|```|colab", re.I),
        "image": re.compile(r"i\.redd\.it|imgur\.com|preview\.redd\.it|\.png|\.jpe?g", re.I)}
OBJECTION = re.compile(r"overfit|over-fit|curve[- ]?fit|look[- ]?ahead|survivorship|slippage|data[- ]?snoop|"
                       r"too good|biased|sample size|p-?hack|doesn'?t work|does not work|not robust|commissions?|"
                       r"out[- ]of[- ]sample|fees", re.I)
INJECTION = re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|rules)|system prompt|api[_ -]?key|"
                       r"private key|seed phrase|connect (your )?wallet|run this (command|script)|curl [^\n]*\|\s*(ba)?sh|"
                       r"pip install|<script|you are (now )?an? (ai|assistant)|as an ai", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+")
ENTRY_RE = re.compile(r"\b(buy|enter|entry|go long|long when|long if|open a long|get in)\b", re.I)
EXIT_RE = re.compile(r"\b(sell|exit|close (the )?position|take profit|stop[- ]?loss|stop out|get out|trailing stop)\b", re.I)


def _clip(s, n=300):
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("..." if len(s) > n else "")


def classify_family(text):
    hits = {k: len(RE[k].findall(text)) for k in
            ("ibs", "rsi", "boll", "cross", "breakout", "momentum", "gap", "orb", "pairs", "vwap", "macd", "ml",
             "options", "volume")}
    if hits["ibs"]:
        fam = "ibs_meanrev"
    elif hits["rsi"] and hits["rsi"] >= max(hits["momentum"], hits["breakout"], hits["cross"], 1) - 0:
        fam = "rsi_meanrev"
    elif hits["boll"]:
        fam = "bollinger_meanrev"
    elif hits["cross"] or (hits["above_ma"] if "above_ma" in hits else 0):
        fam = "sma_cross"
    elif hits["momentum"] >= 2 or (hits["momentum"] and re.search(r"sector|etf|rotation", text, re.I)):
        fam = "xs_momentum"
    elif hits["breakout"]:
        fam = "donchian_breakout"
    elif hits["pairs"]:
        fam = "pairs_stat_arb"
    elif hits["orb"]:
        fam = "opening_range_breakout"
    elif hits["gap"] >= 2:
        fam = "gap_fade"
    elif hits["macd"]:
        fam = "macd_cross"
    elif hits["vwap"]:
        fam = "vwap_intraday"
    elif hits["ml"]:
        fam = "ml_model"
    elif hits["options"] >= 3:
        fam = "options_strategy"
    elif hits["volume"]:
        fam = "volume_signal"
    else:
        fam = "other"
    return fam, hits


def extract_params(text, fam):
    p = {}
    if fam == "rsi_meanrev":
        m = re.search(r"rsi\s*[\(\[]?\s*(\d{1,2})\s*[\)\]]?", text, re.I)
        if m:
            p["rsi_period"] = int(m.group(1))
        m = re.search(r"rsi[^.\n]{0,60}?(?:<|below|under|less than|drops? (?:below|under))\s*(\d{1,2})", text, re.I)
        if m:
            p["rsi_entry"] = int(m.group(1))
    if fam in ("sma_cross", "rsi_meanrev", "ibs_meanrev", "bollinger_meanrev"):
        mas = re.findall(r"(\d{2,3})[- ]?(?:day|d)?\s*(?:sma|ema|moving average|ma)\b", text, re.I)
        if mas:
            p["ma_lengths"] = sorted({int(x) for x in mas})[:4]
    if fam == "ibs_meanrev":
        m = re.search(r"ibs[^.\n]{0,40}?(?:<|below|under|less than)\s*(0?\.\d+|\d{1,2})", text, re.I)
        if m:
            p["ibs_entry"] = float(m.group(1))
    if fam == "donchian_breakout":
        m = re.findall(r"(\d{2,3})[- ]?(?:day|bar|period|week)s?\s*(?:high|breakout)", text, re.I)
        if m:
            p["breakout_n"] = sorted({int(x) for x in m})[:3]
    if fam == "bollinger_meanrev":
        m = re.search(r"(\d(?:\.\d)?)\s*(?:std|standard deviations?|sd|sigma)", text, re.I)
        if m:
            p["bb_std"] = float(m.group(1))
    if fam == "xs_momentum":
        m = re.findall(r"(\d{1,2})[- ]?(month|day|week)s?\s*(?:momentum|return|lookback|performance)", text, re.I)
        if m:
            p["lookbacks"] = [f"{a} {b}" for a, b in m][:3]
        m = re.search(r"top[- ]?(\d)", text, re.I)
        if m:
            p["top_n"] = int(m.group(1))
    return p


def parse_post(post, comments):
    text = f"{post['title']}\n{post['selftext']}"
    fam, hits = classify_family(text)
    sentences = [s for s in SENT_SPLIT.split(post["selftext"]) if s.strip()]
    entries = [_clip(s) for s in sentences if ENTRY_RE.search(s)][:3]
    exits = [_clip(s) for s in sentences if EXIT_RE.search(s)][:3]
    params = extract_params(text, fam)
    tf = "intraday" if INTRADAY.search(text) else ("daily/swing" if DAILY.search(text) else "unspecified")
    mkt = next((n for n, rx in MARKETS if rx.search(text)), "unspecified")
    claims = {}
    for k, rx in CLAIM.items():
        m = rx.search(text)
        if m:
            claims[k] = m.group(m.lastindex)
    ev = {k: bool(rx.search(text)) for k, rx in EVID.items()}
    objections = []
    for c in sorted(comments, key=lambda c: -c["score"]):
        if OBJECTION.search(c["body"]) and len(objections) < 3:
            objections.append({"url": c["url"], "excerpt": _clip(c["body"], 240)})
    inj = sorted({m.group(0).lower() for m in INJECTION.finditer(text)} |
                 {m.group(0).lower() for c in comments for m in INJECTION.finditer(c["body"])})
    missing = []
    if not entries:
        missing.append("explicit entry rule")
    if not exits:
        missing.append("explicit exit rule")
    if not params:
        missing.append("numeric parameters")
    if tf == "unspecified":
        missing.append("timeframe")
    if tf == "intraday":
        missing.append("intraday data (not available in v1)")
    if mkt == "unspecified":
        missing.append("market and universe")
    if not ev["costs"]:
        missing.append("transaction costs not mentioned")
    if not ev["oos"]:
        missing.append("no out-of-sample or forward evidence in text")
    missing.append("position sizing not specified" if not re.search(r"position siz|risk \d|% of (equity|account)", text, re.I) else "")
    missing = [m for m in missing if m]
    is_strategy = bool(RE["strategy_word"].search(text)) and (fam != "other" or bool(entries or exits))
    return {"family": fam, "hits": hits, "entries": entries, "exits": exits, "params": params, "timeframe": tf,
            "market": mkt, "claims": claims, "evidence": ev, "objections": objections, "injection": inj,
            "missing": missing, "is_strategy": is_strategy}


def testability(rec, fam):
    template, prior, _, _ = FAMILY_INFO[fam]
    daily_ok = rec["timeframe"] in ("daily/swing", "unspecified")
    market_ok = rec["market"] in ("ETFs", "stocks", "unspecified")
    completeness = (bool(rec["entries"]) + bool(rec["exits"]) + bool(rec["params"])) / 3.0
    data_av = 1.0 if (daily_ok and market_ok) else (0.3 if daily_ok else 0.0)
    exec_real = 1.0 if (daily_ok and fam not in ("gap_fade", "opening_range_breakout", "vwap_intraday")) else 0.0
    parts = {"template_available": 1.0 if template else 0.0, "rule_completeness": completeness,
             "data_availability": data_av, "mechanism_prior": prior, "execution_realism": exec_real}
    w = {"template_available": 0.30, "rule_completeness": 0.20, "data_availability": 0.20,
         "mechanism_prior": 0.15, "execution_realism": 0.15}
    return sum(parts[k] * w[k] for k in parts), {"parts": parts, "weights": w}


def _tokens(s):
    return set(re.findall(r"[a-z0-9]{3,}", s.lower()))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def build_ideas(con, cycle, dup_threshold=0.6):
    posts = [dict(r) for r in con.execute("SELECT * FROM raw_posts ORDER BY score DESC")]
    comments = {}
    for r in con.execute("SELECT * FROM raw_comments"):
        comments.setdefault(r["post_id"], []).append(dict(r))
    stats = {"posts": len(posts), "not_strategy": 0, "ideas": 0, "duplicates": 0, "injection_flagged": 0}
    recs = []
    for p in posts:
        rec = parse_post(p, comments.get(p["post_id"], []))
        if not rec["is_strategy"]:
            stats["not_strategy"] += 1
            continue
        sc, br = testability(rec, rec["family"])
        recs.append((p, rec, sc, br))
        if rec["injection"]:
            stats["injection_flagged"] += 1
    recs.sort(key=lambda x: -x[2])
    seen_tokens, fam_first = [], {}
    for fam, (tpl, prior, _, _) in FAMILY_INFO.items():
        con.execute("INSERT OR IGNORE INTO families VALUES(?,?,?,?,?)",
                    (fam, fam, tpl, FAMILY_INFO[fam][2], ledger.now()))
    for p, rec, sc, br in recs:
        fam = rec["family"]
        tok = _tokens(p["title"] + " " + p["selftext"])
        dup = next((iid for iid, t in seen_tokens if jaccard(tok, t) >= dup_threshold), None)
        idea_id = "RQ-" + p["post_id"]
        seen_tokens.append((idea_id, tok))
        dup_family = fam in fam_first
        fam_first.setdefault(fam, idea_id)
        stats["duplicates"] += bool(dup)
        tpl, prior, why, decay = FAMILY_INFO[fam]
        says = {"entries": rec["entries"], "exits": rec["exits"], "params": rec["params"],
                "timeframe": rec["timeframe"], "market": rec["market"]}
        interp = (f"Assigned to family '{fam}' by keyword match ({', '.join(k for k, v in rec['hits'].items() if v)}). "
                  f"Template available: {bool(tpl)}.")
        mods = ("Test on daily ETF universe with next-open fills, long only, ATR-stop sizing, fixed 25-config grid "
                "centred on textbook defaults; adopt author numbers only as notes where present."
                if tpl else "No template in v1; would need new data or capabilities.")
        claimed = "; ".join(f"{k}={v}" for k, v in rec["claims"].items()) or "none stated"
        evid = ("code/link present" if rec["evidence"]["code"] else "no code") + "; " + \
               ("screenshot/image link present, not verifiable" if rec["evidence"]["image"] else "no screenshots") + \
               "; " + ("mentions out-of-sample/forward" if rec["evidence"]["oos"] else "no OOS evidence in text")
        infra = "daily OHLCV from yfinance" if rec["timeframe"] != "intraday" else "intraday bars (unavailable)"
        cx = "low" if tpl else "high or not feasible in v1"
        con.execute("""INSERT OR REPLACE INTO ideas VALUES(:idea_id,:family_id,:source_url,:source_post_id,:pub,:disc,
            :summary,:market,:tf,:says,:interp,:mods,:tests,:missing,:claimed,:evid,:obj,:infra,:cx,:why,:decay,
            :dup,:dupfam,:score,:breakdown,:flags)""",
                    {"idea_id": idea_id, "family_id": fam, "source_url": p["url"], "source_post_id": p["post_id"],
                     "pub": p["created_date"], "disc": ledger.now()[:10],
                     "summary": _clip(p["title"], 200), "market": rec["market"], "tf": rec["timeframe"],
                     "says": json.dumps(says), "interp": interp, "mods": mods, "tests": json.dumps({}),
                     "missing": "; ".join(rec["missing"]), "claimed": claimed, "evid": evid,
                     "obj": json.dumps(rec["objections"]), "infra": infra, "cx": cx, "why": why, "decay": decay,
                     "dup": dup, "dupfam": int(dup_family), "score": sc, "breakdown": json.dumps(br),
                     "flags": json.dumps({"injection_like": rec["injection"], "score_votes": p["score"],
                                          "note": "votes recorded for context only, not used as evidence"})})
        stats["ideas"] += 1
    con.commit()
    return stats


def rank_families(con, top_k=3):
    rows = con.execute("""SELECT i.family_id, f.template, COUNT(*) AS n, MAX(i.testability_score) AS best,
                          SUM(CASE WHEN i.duplicate_of IS NULL THEN 1 ELSE 0 END) AS n_unique
                          FROM ideas i JOIN families f ON f.family_id=i.family_id GROUP BY i.family_id""").fetchall()
    ranked = []
    for r in rows:
        score = r["best"] + 0.02 * math.log(1 + r["n_unique"])
        ranked.append({"family_id": r["family_id"], "template": r["template"], "n_ideas": r["n"],
                       "n_unique": r["n_unique"], "best_idea_score": r["best"], "family_score": score,
                       "eligible": bool(r["template"])})
    ranked.sort(key=lambda x: -x["family_score"])
    chosen = [x for x in ranked if x["eligible"]][:top_k]
    return ranked, chosen


def idea_matches_market(post_title, post_selftext, claimed_market, match):
    """True if a cached idea counts as evidence for a pre-registered market.

    match is a dict with optional claimed_markets (list) and text_regex (str).
    Reddit text is untrusted data and is only used as a keyword filter.
    """
    claimed = (claimed_market or "").strip()
    if claimed and claimed in (match.get("claimed_markets") or []):
        return True
    rx = match.get("text_regex")
    if rx:
        text = (post_title or "") + "\n" + (post_selftext or "")
        if re.search(rx, text, re.I):
            return True
    return False


def rank_families_for_market(con, match, top_k=3):
    """Same family_score formula as rank_families, restricted to ideas matching `match`."""
    posts = {r["post_id"]: dict(r) for r in con.execute("SELECT post_id, title, selftext FROM raw_posts")}
    rows = [dict(r) for r in con.execute(
        "SELECT i.idea_id, i.family_id, i.claimed_market, i.testability_score, i.duplicate_of, i.summary, f.template "
        "FROM ideas i JOIN families f ON f.family_id = i.family_id")]
    hits = []
    for r in rows:
        if r["duplicate_of"]:
            continue
        p = posts.get(r["idea_id"].replace("RQ-", ""), {})
        if idea_matches_market(p.get("title", ""), p.get("selftext", ""), r["claimed_market"], match):
            hits.append(r)
    by = {}
    for r in hits:
        by.setdefault(r["family_id"], []).append(r)
    ranked = []
    for fam, rs in by.items():
        best = max(x["testability_score"] for x in rs)
        n_unique = len(rs)
        score = best + 0.02 * math.log(1 + n_unique)
        tpl = rs[0]["template"]
        ranked.append({"family_id": fam, "template": tpl, "n_ideas": n_unique, "n_unique": n_unique,
                       "best_idea_score": best, "family_score": score, "eligible": bool(tpl),
                       "example": rs[0]["summary"]})
    ranked.sort(key=lambda x: -x["family_score"])
    chosen = [x for x in ranked if x["eligible"]][:top_k]
    return ranked, chosen, hits


if __name__ == "__main__":
    con = ledger.connect()
    print(build_ideas(con, 1))
    for r in rank_families(con)[0]:
        print(r)
