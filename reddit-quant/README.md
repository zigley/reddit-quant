# reddit-quant

Reddit-driven research framework for daily-bar strategies. Research and paper trading only.
Cycle 1 tested US equity ETFs. Cycle 2 adds three more universes (crypto, commodity/bond/international ETFs, and continuous futures), each with its own splits, costs, trial counter and primary benchmark.
Live trading is disabled in code (`live_trading: false` in `config.yaml`; the loader exits otherwise) and no
module can place an order. Every value in `config.yaml` is PROVISIONAL until Zach confirms it.

Nothing here claims ongoing monitoring. No scheduler is installed. The cron line below is documentation only.

## Layout

```
config.yaml            provisional config plus pre-registered gates (committed before any trial)
run_cycle.py           one full cycle: data check, scrape, parse, rank, freeze, trials, gates, final test, report
rq/reddit_scraper.py   idea scrape: PRAW -> public JSON (Arctic Shift off by default, ToS-gray)
rq/apewisdom.py        primary Reddit ticker-sentiment source (ApeWisdom, free, no key)
rq/rule_parser.py      regex rule extraction, dedupe into families, testability ranking
rq/ledger.py           SQLite ledger (append-only for trials, evaluations, gates, status, specs, final-test log)
rq/specs.py            versioned YAML specs with sha256, written read-only, verified before every run
rq/engine.py           Backtrader strategies, cost model, next-open fills, sizing caps
rq/metrics.py          CAGR, vol, Sharpe, Sortino, max DD and duration, Calmar, win rate, PF, exposure, turnover
rq/overfit.py          Deflated Sharpe, PBO (CSCV), stationary bootstrap, neighbours, top-trade removal
rq/research.py         trials, robustness evaluation, dev and final gates, once-only final test
rq/champion.py         champion, challenger, rejected status; no path to live
rq/scorecard.py        scorecard CSV and markdown, section 13 cycle report
rq/broker_alpaca.py    disabled Alpaca paper stub (no keys requested, no network calls)
tests/                 engine, ledger lock, multi-market, and ApeWisdom tests
data/                  prices (CSV), cycle-1 manifest.json, per-market manifests under data/manifests/, raw Reddit JSONL, ApeWisdom cache under data/cache/
specs/                 frozen specs
artifacts/             per-cycle trial equity curves, trade logs, evaluation JSON
reports/               cycle reports and scorecards
```

## Set up the backtest engine

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install backtrader yfinance pandas numpy scipy praw pyyaml requests matplotlib
python tests/test_engine.py          # verifies next-open fills, 5 bps slippage, 1 bp commission, delay, DSR/PBO math
python tests/test_ledger_locks.py    # verifies append-only tables and the one-shot final test lock
python tests/test_markets.py         # market overlays, isolated trial counts, D10/F5 use the market benchmark
```

Download prices (adjusted daily bars, manifest with retrieval time and SHA256 per file):

```bash
python - <<'PY'
from rq.config import load_config
from rq import data
print(data.download(load_config())["manifest_hash"])
PY
```

Adjusted prices can change retroactively when dividends or splits post. Compare new downloads to the manifest.

### Engine rules worth knowing

- Signals use bar t close. Backtrader market orders fill at the open of bar t+1. `cheat_on_open` is never on.
- Costs per side are pre-registered per market. Cycle 1 US ETFs, and the cycle 2 commodity/bond and futures markets, use
  1 bp commission and 5 bps slippage. Crypto uses 10 bps commission and 10 bps slippage. `slip_open=True` so open fills
  are slipped. Stress runs use 2x and 3x.
- Long only, 1x gross cap (98% of equity maximum after a new position), fractional shares, max 5 positions.
- Sizing: risk 2% of equity to a close-based stop at entry minus 3 ATR(14), capped at 25% of equity per position.
  This stop-based reading of "2% risk per position" is our interpretation, not a Reddit rule. The stop is checked on
  the close and exits at the next open, so a gap can lose more than 2%.
- Sharpe uses a risk-free rate of 0.

## Run a cycle

```bash
source .venv/bin/activate
python run_cycle.py --cycle 1            # scrape, parse, rank, freeze, trial, gate, report
python run_cycle.py --cycle 2 --skip-scrape --markets crypto,cbi,futures
```

Cycle numbers must not repeat: a frozen spec can reach the locked final test once, and the ledger enforces it.

Example cron (not installed; Zach handles scheduling):

```
0 6 * * 0 cd /workspace/reddit-quant && .venv/bin/python run_cycle.py --cycle $(date +\%G\%V) >> logs/cron.log 2>&1
```

## Reddit sentiment (ApeWisdom)

Ticker mention sentiment comes from ApeWisdom (`https://apewisdom.io/api`), which is free and needs no API key.
It is the primary Reddit sentiment source in `config.yaml`. Official Reddit (PRAW) stays optional for the
separate idea-scrape path if keys ever arrive. Arctic Shift stays off by default because of a ToS-gray area.

Pull current mention ranks (writes raw JSON and a normalized CSV under `data/cache/`):

```bash
source .venv/bin/activate
python -m rq.apewisdom
python tests/test_apewisdom.py
```

ApeWisdom refreshes about every 30 minutes. A pull every 30-60 minutes during market hours is enough.
No scheduler is installed. Zach handles scheduling if he wants one.

Filters used: `all-stocks`, `wallstreetbets`, `stocks`, `pennystocks`. Requests are at most one every 2 seconds,
with retries, backoff, a 30-second timeout, and a clear User-Agent. `pennystocks` is tracked on the methodology
page but is not on the short official filter list, so a missing filter is skipped and reported rather than failing the pull.

## Reddit idea scrape and credentials

`reddit_scraper.py` is the idea-scrape path (raw posts and comments for rule extraction). It tries, in order:

1. PRAW, if `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are set.
2. Public JSON on old.reddit.com with a proper User-Agent, about 1 request per 2 seconds, exponential backoff.
3. Arctic Shift, only if `reddit.arctic_shift_enabled` is true (off by default, ToS-gray).

To add Reddit API credentials: create a "script" app at https://www.reddit.com/prefs/apps, then

```bash
export REDDIT_CLIENT_ID=...        # the string under the app name
export REDDIT_CLIENT_SECRET=...
export REDDIT_USER_AGENT="reddit-quant-research/0.1 (by u/yourname)"   # optional, config has a default
```

The access method is stored on every row (`access_method`). All Reddit text is untrusted data: it is regex-parsed,
never executed, never followed as instructions, and instruction-like text is flagged in `ideas.flags_json`.
Author fields are dropped at ingest.

## Overfitting safety checks

- Pre-registered gates in `config.yaml`, committed before trial 1 (see git history).
- Trial counter per family (`ledger.trial_count`), budget of 25 configs per family, trials append-only.
- Selection uses train Sharpe only. Validation and final test never select.
- Deflated Sharpe Ratio with N = 25 (and a pooled N = 75 conservative figure), PBO via CSCV (16 partitions),
  parameter neighbourhood, 2x and 3x costs, 1-bar delay, top-5 trade removal, stationary block bootstrap CI.
  Note: CSCV PBO on pure noise comes out above 0.5 (a known property of complementary splits), so the 0.50 gate is strict.
- Dev runs load prices truncated at the validation end. The final segment is opened only by `research.final_test`,
  which first inserts the spec hash into `final_test_access` (UNIQUE), so a second look at the same frozen spec is refused.
- Failed experiments are never overwritten: tables are append-only via triggers.

## What is not built

- No live trading, no Alpaca orders (stub only). No portfolio optimiser: the scorecard ranks families, it does not size a
  blended portfolio. No intraday, options or short selling. Crypto, commodity/bond/international ETFs and continuous
  futures are tested as separate universes from cycle 2; futures rolls are not modelled, and yfinance continuous
  contracts can contain artifacts (see the cycle 2 report).
