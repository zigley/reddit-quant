# Cycle 001 report

Research and paper only. Live trading is disabled. All config values are PROVISIONAL pending confirmation. All splits are retrospective (the full history was already known when the specs were written).

## Summary
- Researched: 891 Reddit posts from r/algotrading and r/Daytrading (4450 comments) retrieved via arctic_shift; 549 strategy-like posts parsed into ideas (5 near-duplicates), across 15 families.
- Tested: 3 families, 75 parameter trials on train and validation (2005 to 2020), then 0 family candidate(s) on the locked final test (2021 to 2026-11-09).
- Survived dev gates (and so reached the final test): 0 of 3. Passed every dev and final gate: 0.
- Failed: 3 candidate(s) rejected (details in D).
- Ready for paper trading: no. No qualifying champion.
- Uncertain: Reddit rules are mostly incomplete, so each family test is our interpretation of a textbook version, not a replication of one author's exact rule. Reddit access was through a third-party archive (see F). Split choice, costs and all risk limits are provisional.

## A. Discovery table

| Strategy ID | Idea | Source | Testability | Main concern | Status |
|---|---|---|---|---|---|
| RQ-1v0ov4w | (title redacted; xs_momentum) | r/algotrading/comments/1v0ov4w | 0.98 | no out-of-sample or forward evidence in text; position sizing not specified | family xs_momentum: REJECTED |
| RQ-1tiup27 | (title redacted; xs_momentum) | r/algotrading/comments/1tiup27 | 0.98 | no out-of-sample or forward evidence in text; position sizing not specified | family xs_momentum: REJECTED |
| RQ-cmoekh | (title redacted; sma_cross) | r/algotrading/comments/cmoekh | 0.98 | timeframe; market and universe | family sma_cross: REJECTED |
| RQ-wna4h1 | (title redacted; sma_cross) | r/algotrading/comments/wna4h1 | 0.98 | position sizing not specified | family sma_cross: REJECTED |
| RQ-sebamq | (title redacted; rsi_meanrev) | r/algotrading/comments/sebamq | 0.96 | transaction costs not mentioned; no out-of-sample or forward evidence in text | family rsi_meanrev: REJECTED |
| RQ-1suq39o | (title redacted; rsi_meanrev) | r/algotrading/comments/1suq39o | 0.96 | position sizing not specified | family rsi_meanrev: REJECTED |
| RQ-mcvqq1 | (title redacted; bollinger_meanrev) | r/Daytrading/comments/mcvqq1 | 0.94 | timeframe; market and universe | ledger only (not in top 3 families) |
| RQ-1h74yhu | (title redacted; bollinger_meanrev) | r/Daytrading/comments/1h74yhu | 0.94 | timeframe; market and universe | ledger only (not in top 3 families) |
| RQ-ye5fa3 | (title redacted; bollinger_meanrev) | r/algotrading/comments/ye5fa3 | 0.94 | timeframe; market and universe | ledger only (not in top 3 families) |
| RQ-1h3pptt | (title redacted; xs_momentum) | r/algotrading/comments/1h3pptt | 0.92 | explicit exit rule; transaction costs not mentioned | family xs_momentum: REJECTED |
| RQ-1vcn0tv | (title redacted; xs_momentum) | r/algotrading/comments/1vcn0tv | 0.92 | numeric parameters; transaction costs not mentioned | family xs_momentum: REJECTED |
| RQ-1x46igq | (title redacted; xs_momentum) | r/algotrading/comments/1x46igq | 0.92 | numeric parameters; transaction costs not mentioned | family xs_momentum: REJECTED |
| RQ-dh0qov | (title redacted; sma_cross) | r/algotrading/comments/dh0qov | 0.91 | numeric parameters; transaction costs not mentioned | family sma_cross: REJECTED |
| RQ-dhs4xj | (title redacted; sma_cross) | r/algotrading/comments/dhs4xj | 0.91 | numeric parameters; timeframe | family sma_cross: REJECTED |
| RQ-1u437da | (title redacted; sma_cross) | r/algotrading/comments/1u437da | 0.91 | explicit exit rule; transaction costs not mentioned | family sma_cross: REJECTED |
| RQ-1h37hcn | (title redacted; sma_cross) | r/algotrading/comments/1h37hcn | 0.91 | numeric parameters; timeframe | family sma_cross: REJECTED |
| RQ-1hdlp0o | (title redacted; sma_cross) | r/algotrading/comments/1hdlp0o | 0.91 | numeric parameters; timeframe | family sma_cross: REJECTED |
| RQ-15lqxoc | (title redacted; sma_cross) | r/Daytrading/comments/15lqxoc | 0.91 | numeric parameters; timeframe | family sma_cross: REJECTED |
| RQ-ta0y3j | (title redacted; rsi_meanrev) | r/algotrading/comments/ta0y3j | 0.90 | numeric parameters; transaction costs not mentioned | family rsi_meanrev: REJECTED |
| RQ-1xe6pvu | (title redacted; rsi_meanrev) | r/algotrading/comments/1xe6pvu | 0.90 | numeric parameters; market and universe | family rsi_meanrev: REJECTED |

Showing top 20 unique ideas by testability. Full idea ledger is kept locally and is not in this public tree (549 rows). Post votes are recorded locally but not used as evidence.

Family ranking (testability score, eligible = has a v1 template):

| Family | Ideas | Unique | Best idea score | Family score | Eligible |
|---|---|---|---|---|---|
| xs_momentum | 78 | 78 | 0.98 | 1.07 | True |
| rsi_meanrev | 151 | 146 | 0.96 | 1.06 | True |
| sma_cross | 30 | 30 | 0.98 | 1.05 | True |
| bollinger_meanrev | 39 | 39 | 0.94 | 1.01 | True |
| donchian_breakout | 69 | 69 | 0.89 | 0.97 | True |
| ibs_meanrev | 2 | 2 | 0.75 | 0.77 | True |
| other | 91 | 91 | 0.51 | 0.60 | False |
| ml_model | 16 | 16 | 0.54 | 0.59 | False |
| pairs_stat_arb | 13 | 13 | 0.51 | 0.56 | False |
| macd_cross | 7 | 7 | 0.48 | 0.53 | False |
| options_strategy | 25 | 25 | 0.40 | 0.46 | False |
| vwap_intraday | 13 | 13 | 0.39 | 0.44 | False |
| gap_fade | 11 | 11 | 0.33 | 0.38 | False |
| volume_signal | 2 | 2 | 0.13 | 0.15 | False |
| opening_range_breakout | 2 | 2 | 0.12 | 0.14 | False |

## B. Results table

Net of costs (1 bp commission + 5 bps slippage per side). Sharpe uses rf = 0. Benchmarks are zero-cost passive series.

| Version | Evaluation period | Net return | Sharpe | Max drawdown | Trades | Costs | Benchmark comparison | Main limitation |
|---|---|---|---|---|---|---|---|---|
| xs_momentum 71348ba2 {"lookback": 189, "top_n": 5} | train 2005-2016 | 97.2% | 0.54 | -22.3% | 126 | base | SPY Sharpe 0.47 / return 137.1%; EW Sharpe 0.53 |  |
| xs_momentum 71348ba2 {"lookback": 189, "top_n": 5} | validation 2017-2020 | 44.0% | 0.67 | -20.6% | 40 | base | SPY Sharpe 0.84 / return 80.3%; EW Sharpe 0.73 | failed D2_dsr, D10_beats_passive |
| rsi_meanrev 9e014de1 {"rsi_entry": 20, "rsi_n": 4} | train 2005-2016 | 65.6% | 0.70 | -11.0% | 395 | base | SPY Sharpe 0.47 / return 137.1%; EW Sharpe 0.53 |  |
| rsi_meanrev 9e014de1 {"rsi_entry": 20, "rsi_n": 4} | validation 2017-2020 | -11.3% | -0.31 | -21.8% | 146 | base | SPY Sharpe 0.84 / return 80.3%; EW Sharpe 0.73 | failed D1_val_sharpe_positive, D2_dsr, D3_pbo, D4_bootstrap_ci, D6_cost_2x, D7_delay, D10_beats_passive |
| sma_cross 5fc26e6a {"fast_n": 40, "slow_n": 200} | train 2005-2016 | 200.9% | 0.87 | -16.3% | 45 | base | SPY Sharpe 0.47 / return 137.1%; EW Sharpe 0.53 |  |
| sma_cross 5fc26e6a {"fast_n": 40, "slow_n": 200} | validation 2017-2020 | 28.5% | 0.57 | -19.9% | 17 | base | SPY Sharpe 0.84 / return 80.3%; EW Sharpe 0.73 | failed D3_pbo, D10_beats_passive |

Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle001/<family>/ and the trials table.

## C. Current champion

No qualifying champion.

Gate results per family (pre-registered thresholds in config.yaml, committed before trial 1):

| Family | Gate | Result | Detail |
|---|---|---|---|
| xs_momentum | D1_val_sharpe_positive | pass | val Sharpe 0.671 |
| xs_momentum | D2_dsr | FAIL | DSR 0.837 (N=25, SR0 ann 0.32, SR ann 0.58); conservative N=75: 0.472 |
| xs_momentum | D3_pbo | pass | PBO 0.204 |
| xs_momentum | D4_bootstrap_ci | pass | 95% CI [0.12, 1.09], Sharpe 0.58 |
| xs_momentum | D5_max_dd | pass | train -0.223, val -0.206 |
| xs_momentum | D6_cost_2x | pass | val Sharpe at 2x 0.658 |
| xs_momentum | D7_delay | pass | val Sharpe with delay 0.624 |
| xs_momentum | D8_top_trades | pass | PnL 13134 -> 6437 after removing top 5 (166 trades) |
| xs_momentum | D9_neighbours | pass | median neighbour train Sharpe 0.427 vs selected 0.545 (n=5) |
| xs_momentum | D10_beats_passive | FAIL | val Sharpe 0.671 vs SPY 0.837, EW 0.731 |
| rsi_meanrev | D1_val_sharpe_positive | FAIL | val Sharpe -0.308 |
| rsi_meanrev | D2_dsr | FAIL | DSR 0.549 (N=25, SR0 ann 0.35, SR ann 0.38); conservative N=75: 0.202 |
| rsi_meanrev | D3_pbo | FAIL | PBO 0.582 |
| rsi_meanrev | D4_bootstrap_ci | FAIL | 95% CI [-0.06, 0.87], Sharpe 0.38 |
| rsi_meanrev | D5_max_dd | pass | train -0.110, val -0.218 |
| rsi_meanrev | D6_cost_2x | FAIL | val Sharpe at 2x -0.331 |
| rsi_meanrev | D7_delay | FAIL | val Sharpe with delay -0.150 |
| rsi_meanrev | D8_top_trades | pass | PnL 4677 -> 3609 after removing top 5 (541 trades) |
| rsi_meanrev | D9_neighbours | pass | median neighbour train Sharpe 0.524 vs selected 0.696 (n=8) |
| rsi_meanrev | D10_beats_passive | FAIL | val Sharpe -0.308 vs SPY 0.837, EW 0.731 |
| sma_cross | D1_val_sharpe_positive | pass | val Sharpe 0.569 |
| sma_cross | D2_dsr | pass | DSR 0.993 (N=25, SR0 ann 0.15, SR ann 0.79); conservative N=75: 0.769 |
| sma_cross | D3_pbo | FAIL | PBO 0.582 |
| sma_cross | D4_bootstrap_ci | pass | 95% CI [0.34, 1.30], Sharpe 0.79 |
| sma_cross | D5_max_dd | pass | train -0.163, val -0.199 |
| sma_cross | D6_cost_2x | pass | val Sharpe at 2x 0.559 |
| sma_cross | D7_delay | pass | val Sharpe with delay 0.573 |
| sma_cross | D8_top_trades | pass | PnL 19922 -> 4557 after removing top 5 (62 trades) |
| sma_cross | D9_neighbours | pass | median neighbour train Sharpe 0.699 vs selected 0.872 (n=8) |
| sma_cross | D10_beats_passive | FAIL | val Sharpe 0.569 vs SPY 0.837, EW 0.731 |

## D. Rejected candidates

- xs_momentum (71348ba2): D2_dsr (DSR 0.837 (N=25, SR0 ann 0.32, SR ann 0.58); conservative N=75: 0.472); D10_beats_passive (val Sharpe 0.671 vs SPY 0.837, EW 0.731)
  Reconsider with: a new spec version and fresh data not used here (post-2026-11-09 bars, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- rsi_meanrev (9e014de1): D1_val_sharpe_positive (val Sharpe -0.308); D2_dsr (DSR 0.549 (N=25, SR0 ann 0.35, SR ann 0.38); conservative N=75: 0.202); D3_pbo (PBO 0.582); D4_bootstrap_ci (95% CI [-0.06, 0.87], Sharpe 0.38); D6_cost_2x (val Sharpe at 2x -0.331); D7_delay (val Sharpe with delay -0.150); D10_beats_passive (val Sharpe -0.308 vs SPY 0.837, EW 0.731)
  Reconsider with: a new spec version and fresh data not used here (post-2026-11-09 bars, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- sma_cross (5fc26e6a): D3_pbo (PBO 0.582); D10_beats_passive (val Sharpe 0.569 vs SPY 0.837, EW 0.731)
  Reconsider with: a new spec version and fresh data not used here (post-2026-11-09 bars, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.

Ledger-only families (not tested this cycle): bollinger_meanrev (not in top 3), donchian_breakout (not in top 3), ibs_meanrev (not in top 3), other (no v1 template), ml_model (no v1 template), pairs_stat_arb (no v1 template), macd_cross (no v1 template), options_strategy (no v1 template), vwap_intraday (no v1 template), gap_fade (no v1 template), volume_signal (no v1 template), opening_range_breakout (no v1 template)

## E. Next experiments

- Get Reddit API credentials (REDDIT_CLIENT_ID/SECRET) so posts and comments can be read from reddit.com directly and the archive-derived permalinks verified. Falsifiable: every cited URL resolves and its text matches the archive.
- Replicate the strongest single Reddit rule exactly as written (author numbers, not the grid centre) as one pre-registered spec, 1 trial, on fresh post-cycle bars only. Falsifiable: Sharpe above 0 and above SPY buy-and-hold after 2x costs.
- Extend the passive comparison to a volatility-matched SPY (same exposure) so low-exposure mean-reversion families are not judged only on raw Sharpe. Pre-register before any run.
- Add a second, independent daily dataset (for example a different vendor) and re-run the already-frozen specs for data-source sensitivity. Falsifiable: Sharpe within 0.15 of the yfinance result.
- Weekly cycle: only post-2026-11-09 bars are new; wait for enough fresh data (at least 6 months) before any re-evaluation of a rejected family, with a new spec version.

## F. Audit summary

- Tools actually used: Python 3.13 venv (backtrader 1.9.78.123, yfinance 1.8.0, pandas 3.1.1, numpy 2.5.4, scipy, pyyaml, praw installed but unused), SQLite, git, curl, Arctic Shift public archive API; Bright Data MCP (token rejected, no data) and Firecrawl CLI (not authenticated, no data) were tried and failed
- Reddit access attempts: praw/-: skipped x1; public_json/posts: blocked x1; arctic_shift/posts: ok x1; arctic_shift/comments: error x5; arctic_shift/summary: ok x1 (public_json detail: HTTP 403 from https://old.reddit.com/r/algotrading/top.json)
- Reddit coverage: 42 of 160 subreddit x keyword x year query windows returned data; 118 windows hit server-side timeouts (HTTP 422 Timeout) and were skipped, so coverage is partial and biased toward windows the archive could serve
- Parser quality: keyword/regex assignment, precision not measured; titles show noise (some posts that mention RSI or Bollinger in passing are assigned to that family). Families are used for ranking only; each family test is our textbook-style template, not a replication of any post.
- Reddit access caveat: reddit.com returned HTTP 403 to this machine. Posts and comments came from a third-party archive (Arctic Shift), permalinks are built from archive records and were not live-verified. Authors dropped at ingest.
- Data: yfinance adjusted daily, 13 symbols, 5498 bars each, 2005-01-03 to 2026-11-09, retrieved 2026-11-09T23:43:20-0700, manifest hash ff457a7962536907
- Data issues: sanity checks found none (calendar alignment, OHLC consistency, >25% moves, duplicates, zero volume). Adjusted history may change retroactively; the last bar's adjustment is provisional.
- Total parameter trials this cycle: 75 (budget: 25 per family x 3 families)
- Robustness evaluation runs (not trials): 9 dev stress runs plus final-test runs for survivors
- Final-test accesses this cycle: 0 (each spec hash can be accessed once; enforced by a UNIQUE constraint in the ledger)
- Compute: 166 s summed wall time over the 75 trials (3 worker processes), plus 9 dev stress runs and report building, about 2 minutes end to end for the testing phase. The rate-limited Reddit archive scrape took about 18 minutes (23:42 to 00:00 MT) (236 requests incl. retries). Well inside the 120 minute cycle budget.
- Posts flagged as injection-like: 4 (kept as data, never followed)
- Constraints: Single dataset vendor; 13-ETF universe is small; Sharpe rf=0; fractional shares assumed; stops are close-based and exit at next open; the risk-per-position sizing rule is our interpretation; the delay test applies 1 extra bar to all orders; PBO via CSCV is biased above 0.5 on pure noise (the sanity test shows this), so the 0.50 gate is strict.
- Pre-run smoke test: Before this run the pipeline was exercised once in a scratch copy using 6 synthetic posts and price data truncated at 2015-12-31 with shortened splits (train to 2010, validation 2011-2013, scratch final 2014-2015). It was only to catch code bugs. Separately, before the specs were frozen, one engine smoke run printed train-segment (2005-2016) metrics for the default parameters of all six templates; those runs are not recorded as trials and no validation or final data was used (the same configs were later re-run as grid trials). Scratch results are not in this ledger and no gate, split or config value was changed afterwards. The scratch run did show that slow trend systems produce few trades on a short final window, which is what the pre-registered F6 minimum-trades gate (20) penalises.
- Monitoring: None configured. No scheduler is running; cron line is documented only.

