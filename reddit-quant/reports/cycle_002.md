# Cycle 002 report

Research and paper only. Live trading is disabled. All config values are PROVISIONAL pending confirmation. All splits are retrospective (the full history was already known when the specs were written).

## Summary
- Researched: 891 Reddit posts from r/algotrading and r/Daytrading (4450 comments) retrieved via arctic_shift; 549 strategy-like posts parsed into ideas (5 near-duplicates), across 15 families.
- Markets this cycle (each is its own universe, with its own 25-trial budget and DSR N=25 / pooled N=75): crypto, cbi, futures.
- Tested: crypto: 3 families, 0 reached the locked final test; cbi: 3 families, 1 reached the locked final test; futures: 3 families, 0 reached the locked final test. Total parameter trials: 225.
- Survived dev gates (and so reached the final test): 1 of 9. Passed every dev and final gate: 0.
- Failed: 9 candidate(s) rejected (details in D).
- Ready for paper trading: no. No qualifying champion.
- Uncertain: Reddit rules are mostly incomplete, so each family test is our interpretation of a textbook version, not a replication of one author's exact rule. Reddit access was through a third-party archive (see F). Split choice, costs and all risk limits are provisional.

## A. Discovery table

| Strategy ID | Idea | Source | Testability | Main concern | Status |
|---|---|---|---|---|---|
| RQ-1v0ov4w | (title redacted; xs_momentum) | r/algotrading/comments/1v0ov4w | 0.98 | no out-of-sample or forward evidence in text; position sizing not specified | cycle tests: crypto.xs_momentum: REJECTED; cbi.xs_momentum: REJECTED |
| RQ-1tiup27 | (title redacted; xs_momentum) | r/algotrading/comments/1tiup27 | 0.98 | no out-of-sample or forward evidence in text; position sizing not specified | cycle tests: crypto.xs_momentum: REJECTED; cbi.xs_momentum: REJECTED |
| RQ-cmoekh | (title redacted; sma_cross) | r/algotrading/comments/cmoekh | 0.98 | timeframe; market and universe | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-wna4h1 | (title redacted; sma_cross) | r/algotrading/comments/wna4h1 | 0.98 | position sizing not specified | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-sebamq | (title redacted; rsi_meanrev) | r/algotrading/comments/sebamq | 0.96 | transaction costs not mentioned; no out-of-sample or forward evidence in text | cycle tests: crypto.rsi_meanrev: REJECTED; cbi.rsi_meanrev: REJECTED; futures.rsi_meanrev: REJECTED |
| RQ-1suq39o | (title redacted; rsi_meanrev) | r/algotrading/comments/1suq39o | 0.96 | position sizing not specified | cycle tests: crypto.rsi_meanrev: REJECTED; cbi.rsi_meanrev: REJECTED; futures.rsi_meanrev: REJECTED |
| RQ-mcvqq1 | (title redacted; bollinger_meanrev) | r/Daytrading/comments/mcvqq1 | 0.94 | timeframe; market and universe | cycle tests: futures.bollinger_meanrev: REJECTED |
| RQ-1h74yhu | (title redacted; bollinger_meanrev) | r/Daytrading/comments/1h74yhu | 0.94 | timeframe; market and universe | cycle tests: futures.bollinger_meanrev: REJECTED |
| RQ-ye5fa3 | (title redacted; bollinger_meanrev) | r/algotrading/comments/ye5fa3 | 0.94 | timeframe; market and universe | cycle tests: futures.bollinger_meanrev: REJECTED |
| RQ-1h3pptt | (title redacted; xs_momentum) | r/algotrading/comments/1h3pptt | 0.92 | explicit exit rule; transaction costs not mentioned | cycle tests: crypto.xs_momentum: REJECTED; cbi.xs_momentum: REJECTED |
| RQ-1vcn0tv | (title redacted; xs_momentum) | r/algotrading/comments/1vcn0tv | 0.92 | numeric parameters; transaction costs not mentioned | cycle tests: crypto.xs_momentum: REJECTED; cbi.xs_momentum: REJECTED |
| RQ-1x46igq | (title redacted; xs_momentum) | r/algotrading/comments/1x46igq | 0.92 | numeric parameters; transaction costs not mentioned | cycle tests: crypto.xs_momentum: REJECTED; cbi.xs_momentum: REJECTED |
| RQ-dh0qov | (title redacted; sma_cross) | r/algotrading/comments/dh0qov | 0.91 | numeric parameters; transaction costs not mentioned | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-dhs4xj | (title redacted; sma_cross) | r/algotrading/comments/dhs4xj | 0.91 | numeric parameters; timeframe | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-1u437da | (title redacted; sma_cross) | r/algotrading/comments/1u437da | 0.91 | explicit exit rule; transaction costs not mentioned | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-1h37hcn | (title redacted; sma_cross) | r/algotrading/comments/1h37hcn | 0.91 | numeric parameters; timeframe | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-1hdlp0o | (title redacted; sma_cross) | r/algotrading/comments/1hdlp0o | 0.91 | numeric parameters; timeframe | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-15lqxoc | (title redacted; sma_cross) | r/Daytrading/comments/15lqxoc | 0.91 | numeric parameters; timeframe | cycle tests: crypto.sma_cross: REJECTED; cbi.sma_cross: REJECTED; futures.sma_cross: REJECTED |
| RQ-ta0y3j | (title redacted; rsi_meanrev) | r/algotrading/comments/ta0y3j | 0.90 | numeric parameters; transaction costs not mentioned | cycle tests: crypto.rsi_meanrev: REJECTED; cbi.rsi_meanrev: REJECTED; futures.rsi_meanrev: REJECTED |
| RQ-1xe6pvu | (title redacted; rsi_meanrev) | r/algotrading/comments/1xe6pvu | 0.90 | numeric parameters; market and universe | cycle tests: crypto.rsi_meanrev: REJECTED; cbi.rsi_meanrev: REJECTED; futures.rsi_meanrev: REJECTED |

Showing top 20 unique ideas by testability. Full idea ledger is kept locally and is not in this public tree (549 rows). Post votes are recorded locally but not used as evidence.

Family ranking is computed separately per market from cached ideas (same score formula as cycle 1). See each market section.

## Market: crypto

Universe: BTC-USD, ETH-USD, LTC-USD, XRP-USD, BNB-USD, ADA-USD, DOGE-USD, LINK-USD. Splits (pre-registered): train 2018-09-01 to 2021-12-31, validation 2022-01-01 to 2023-12-31, locked final test 2024-01-01 to 2026-11-09. Primary benchmark: BTC-USD buy-and-hold (zero cost), plus equal-weight of the universe. Costs: 10 bp commission and 10 bps slippage per side. Annualisation uses 365 periods per year. Aligned bars: 3288 from 2017-11-09 to 2026-11-09. Data flags: BTC-USD: 2 daily moves > 25% (check adjustment); ETH-USD: 5 daily moves > 25% (check adjustment); LTC-USD: 10 daily moves > 25% (check adjustment); XRP-USD: 26 daily moves > 25% (check adjustment); BNB-USD: 12 daily moves > 25% (check adjustment); ADA-USD: 17 daily moves > 25% (check adjustment); DOGE-USD: 28 daily moves > 25% (check adjustment); LINK-USD: 18 daily moves > 25% (check adjustment).

### A. Market family ranking

| Family | Ideas | Unique | Best idea score | Family score | Eligible | Chosen |
|---|---|---|---|---|---|---|
| rsi_meanrev | 24 | 24 | 0.82 | 0.89 | True | yes |
| xs_momentum | 9 | 9 | 0.78 | 0.82 | True | yes |
| sma_cross | 6 | 6 | 0.77 | 0.81 | True | yes |
| donchian_breakout | 8 | 8 | 0.61 | 0.66 | True |  |
| bollinger_meanrev | 3 | 3 | 0.59 | 0.62 | True |  |
| other | 15 | 15 | 0.37 | 0.43 | False |  |
| pairs_stat_arb | 2 | 2 | 0.30 | 0.32 | False |  |
| ml_model | 5 | 5 | 0.26 | 0.30 | False |  |
| vwap_intraday | 1 | 1 | 0.25 | 0.26 | False |  |
| gap_fade | 1 | 1 | 0.19 | 0.21 | False |  |
| opening_range_breakout | 1 | 1 | 0.12 | 0.13 | False |  |
| options_strategy | 1 | 1 | 0.04 | 0.06 | False |  |

Pre-registered families for this market: rsi_meanrev, xs_momentum, sma_cross.

### B. Results table

Net of costs (10 bp commission + 10 bps slippage per side). Sharpe uses rf = 0, annualised with 365 periods per year. Benchmarks are zero-cost passive series.

| Version | Evaluation period | Net return | Sharpe | Max drawdown | Trades | Costs | Benchmark comparison | Main limitation |
|---|---|---|---|---|---|---|---|---|
| crypto.rsi_meanrev 089aaccf {"rsi_entry": 15, "rsi_n": 5} | train 2018-09 to 2021-12 | 13.4% | 0.93 | -3.4% | 28 | base | BTC-USD Sharpe 1.15 / return 558.0%; EW Sharpe 1.61 |  |
| crypto.rsi_meanrev 089aaccf {"rsi_entry": 15, "rsi_n": 5} | validation 2022-01 to 2023-12 | 9.2% | 1.21 | -1.2% | 9 | base | BTC-USD Sharpe 0.19 / return -8.7%; EW Sharpe 0.08 | failed D2_dsr, D9_neighbours |
| crypto.xs_momentum 2daf0870 {"lookback": 21, "top_n": 3} | train 2018-09 to 2021-12 | 437.8% | 1.74 | -27.6% | 91 | base | BTC-USD Sharpe 1.15 / return 558.0%; EW Sharpe 1.61 |  |
| crypto.xs_momentum 2daf0870 {"lookback": 21, "top_n": 3} | validation 2022-01 to 2023-12 | -21.8% | -0.57 | -40.1% | 53 | base | BTC-USD Sharpe 0.19 / return -8.7%; EW Sharpe 0.08 | failed D1_val_sharpe_positive, D2_dsr, D3_pbo, D5_max_dd, D6_cost_2x, D7_delay, D8_top_trades, D10_beats_passive |
| crypto.sma_cross 874b2c83 {"fast_n": 50, "slow_n": 250} | train 2018-09 to 2021-12 | 3456.9% | 1.52 | -70.5% | 19 | base | BTC-USD Sharpe 1.15 / return 558.0%; EW Sharpe 1.61 |  |
| crypto.sma_cross 874b2c83 {"fast_n": 50, "slow_n": 250} | validation 2022-01 to 2023-12 | 4.9% | 0.22 | -23.3% | 14 | base | BTC-USD Sharpe 0.19 / return -8.7%; EW Sharpe 0.08 | failed D3_pbo, D5_max_dd, D8_top_trades |

Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle002/ and the trials table.

### C. Current champion

No qualifying champion in this market.

Gate results (pre-registered thresholds in config.yaml, committed before these trials):

| Family | Gate | Result | Detail |
|---|---|---|---|
| crypto.rsi_meanrev | D1_val_sharpe_positive | pass | val Sharpe 1.211 |
| crypto.rsi_meanrev | D2_dsr | FAIL | DSR 0.893 (N=25, SR0 ann 0.56, SR ann 1.03); conservative N=75: 0.669 |
| crypto.rsi_meanrev | D3_pbo | pass | PBO 0.217 |
| crypto.rsi_meanrev | D4_bootstrap_ci | pass | 95% CI [0.37, 1.62], Sharpe 0.85 |
| crypto.rsi_meanrev | D5_max_dd | pass | train -0.034, val -0.012 |
| crypto.rsi_meanrev | D6_cost_2x | pass | val Sharpe at 2x 1.153 |
| crypto.rsi_meanrev | D7_delay | pass | val Sharpe with delay 1.264 |
| crypto.rsi_meanrev | D8_top_trades | pass | PnL 2384 -> 1165 after removing top 5 (37 trades) |
| crypto.rsi_meanrev | D9_neighbours | FAIL | median neighbour train Sharpe 0.392 vs selected 0.931 (n=8) |
| crypto.rsi_meanrev | D10_beats_passive | pass | val Sharpe 1.211 vs BTC-USD 0.191, EW 0.081 |
| crypto.xs_momentum | D1_val_sharpe_positive | FAIL | val Sharpe -0.567 |
| crypto.xs_momentum | D2_dsr | FAIL | DSR 0.904 (N=25, SR0 ann 0.55, SR ann 1.11); conservative N=75: 0.715 |
| crypto.xs_momentum | D3_pbo | FAIL | PBO 0.531 |
| crypto.xs_momentum | D4_bootstrap_ci | pass | 95% CI [0.17, 1.99], Sharpe 0.92 |
| crypto.xs_momentum | D5_max_dd | FAIL | train -0.276, val -0.401 |
| crypto.xs_momentum | D6_cost_2x | FAIL | val Sharpe at 2x -0.645 |
| crypto.xs_momentum | D7_delay | FAIL | val Sharpe with delay -0.431 |
| crypto.xs_momentum | D8_top_trades | FAIL | PnL 30016 -> -4118 after removing top 5 (144 trades) |
| crypto.xs_momentum | D9_neighbours | pass | median neighbour train Sharpe 1.152 vs selected 1.738 (n=5) |
| crypto.xs_momentum | D10_beats_passive | FAIL | val Sharpe -0.567 vs BTC-USD 0.191, EW 0.081 |
| crypto.sma_cross | D1_val_sharpe_positive | pass | val Sharpe 0.222 |
| crypto.sma_cross | D2_dsr | pass | DSR 0.993 (N=25, SR0 ann 0.29, SR ann 1.21); conservative N=75: 0.822 |
| crypto.sma_cross | D3_pbo | FAIL | PBO 0.938 |
| crypto.sma_cross | D4_bootstrap_ci | pass | 95% CI [0.34, 1.96], Sharpe 1.00 |
| crypto.sma_cross | D5_max_dd | FAIL | train -0.705, val -0.233 |
| crypto.sma_cross | D6_cost_2x | pass | val Sharpe at 2x 0.214 |
| crypto.sma_cross | D7_delay | pass | val Sharpe with delay 0.108 |
| crypto.sma_cross | D8_top_trades | FAIL | PnL 269073 -> -90220 after removing top 5 (33 trades) |
| crypto.sma_cross | D9_neighbours | pass | median neighbour train Sharpe 1.400 vs selected 1.520 (n=5) |
| crypto.sma_cross | D10_beats_passive | pass | val Sharpe 0.222 vs BTC-USD 0.191, EW 0.081 |

### D. Rejected candidates

- crypto.rsi_meanrev (089aaccf): D2_dsr (DSR 0.893 (N=25, SR0 ann 0.56, SR ann 1.03); conservative N=75: 0.669); D9_neighbours (median neighbour train Sharpe 0.392 vs selected 0.931 (n=8))
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- crypto.xs_momentum (2daf0870): D1_val_sharpe_positive (val Sharpe -0.567); D2_dsr (DSR 0.904 (N=25, SR0 ann 0.55, SR ann 1.11); conservative N=75: 0.715); D3_pbo (PBO 0.531); D5_max_dd (train -0.276, val -0.401); D6_cost_2x (val Sharpe at 2x -0.645); D7_delay (val Sharpe with delay -0.431); D8_top_trades (PnL 30016 -> -4118 after removing top 5 (144 trades)); D10_beats_passive (val Sharpe -0.567 vs BTC-USD 0.191, EW 0.081)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- crypto.sma_cross (874b2c83): D3_pbo (PBO 0.938); D5_max_dd (train -0.705, val -0.233); D8_top_trades (PnL 269073 -> -90220 after removing top 5 (33 trades))
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.

## Market: cbi

Universe: GLD, SLV, USO, DBC, TLT, IEF, HYG, EFA, EEM, VNQ, UUP. Splits (pre-registered): train 2008-07-01 to 2016-12-31, validation 2017-01-01 to 2020-12-31, locked final test 2021-01-01 to 2026-11-09. Primary benchmark: EFA buy-and-hold (zero cost), plus equal-weight of the universe. Costs: 1 bp commission and 5 bps slippage per side. Annualisation uses 252 periods per year. Aligned bars: 4928 from 2007-04-11 to 2026-11-09. Data flags: SLV: 1 daily moves > 25% (check adjustment); USO: 2 daily moves > 25% (check adjustment).

### A. Market family ranking

| Family | Ideas | Unique | Best idea score | Family score | Eligible | Chosen |
|---|---|---|---|---|---|---|
| sma_cross | 2 | 2 | 0.98 | 1.00 | True | yes |
| xs_momentum | 8 | 8 | 0.79 | 0.83 | True | yes |
| rsi_meanrev | 6 | 6 | 0.76 | 0.80 | True | yes |
| donchian_breakout | 5 | 5 | 0.76 | 0.79 | True |  |
| ibs_meanrev | 1 | 1 | 0.75 | 0.76 | True |  |
| bollinger_meanrev | 1 | 1 | 0.52 | 0.54 | True |  |
| options_strategy | 1 | 1 | 0.39 | 0.40 | False |  |
| other | 3 | 3 | 0.31 | 0.33 | False |  |
| pairs_stat_arb | 1 | 1 | 0.30 | 0.31 | False |  |
| opening_range_breakout | 1 | 1 | 0.12 | 0.13 | False |  |

Pre-registered families for this market: sma_cross, xs_momentum, rsi_meanrev.

### B. Results table

Net of costs (1 bp commission + 5 bps slippage per side). Sharpe uses rf = 0, annualised with 252 periods per year. Benchmarks are zero-cost passive series.

| Version | Evaluation period | Net return | Sharpe | Max drawdown | Trades | Costs | Benchmark comparison | Main limitation |
|---|---|---|---|---|---|---|---|---|
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | train 2008-07 to 2016-12 | 73.0% | 0.75 | -12.8% | 51 | base | EFA Sharpe 0.17 / return 8.3%; EW Sharpe 0.17 |  |
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | validation 2017-01 to 2020-12 | 37.5% | 1.13 | -8.3% | 22 | base | EFA Sharpe 0.57 / return 41.5%; EW Sharpe 0.56 | failed F5_beats_spy |
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | final test 2021-01 to 2026-11 | 45.3% | 0.63 | -16.8% | 36 | base | EFA Sharpe 0.65 / return 70.7%; EW Sharpe 0.98 | failed F5_beats_spy |
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | final test, 2x costs | 44.1% | 0.62 | -17.3% | 36 | 2x costs | stress run | |
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | final test, 3x costs | 43.0% | 0.61 | -17.9% | 36 | 3x costs | stress run | |
| cbi.sma_cross 6471d574 {"fast_n": 40, "slow_n": 150} | final test, 1-bar delay | 44.8% | 0.64 | -14.1% | 39 | 1-bar delay | stress run | |
| cbi.xs_momentum 50ba1d4f {"lookback": 63, "top_n": 3} | train 2008-07 to 2016-12 | 43.8% | 0.45 | -19.1% | 124 | base | EFA Sharpe 0.17 / return 8.3%; EW Sharpe 0.17 |  |
| cbi.xs_momentum 50ba1d4f {"lookback": 63, "top_n": 3} | validation 2017-01 to 2020-12 | 16.5% | 0.43 | -14.4% | 60 | base | EFA Sharpe 0.57 / return 41.5%; EW Sharpe 0.56 | failed D2_dsr, D4_bootstrap_ci, D9_neighbours, D10_beats_passive |
| cbi.rsi_meanrev 929630a4 {"rsi_entry": 15, "rsi_n": 5} | train 2008-07 to 2016-12 | 6.7% | 0.25 | -8.6% | 81 | base | EFA Sharpe 0.17 / return 8.3%; EW Sharpe 0.17 |  |
| cbi.rsi_meanrev 929630a4 {"rsi_entry": 15, "rsi_n": 5} | validation 2017-01 to 2020-12 | 8.4% | 0.82 | -3.6% | 41 | base | EFA Sharpe 0.57 / return 41.5%; EW Sharpe 0.56 | failed D2_dsr, D4_bootstrap_ci, D9_neighbours |

Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle002/ and the trials table.

### C. Current champion

No qualifying champion in this market.

Gate results (pre-registered thresholds in config.yaml, committed before these trials):

| Family | Gate | Result | Detail |
|---|---|---|---|
| cbi.sma_cross | D1_val_sharpe_positive | pass | val Sharpe 1.127 |
| cbi.sma_cross | D2_dsr | pass | DSR 0.975 (N=25, SR0 ann 0.29, SR ann 0.85); conservative N=75: 0.824 |
| cbi.sma_cross | D3_pbo | pass | PBO 0.145 |
| cbi.sma_cross | D4_bootstrap_ci | pass | 95% CI [0.29, 1.37], Sharpe 0.85 |
| cbi.sma_cross | D5_max_dd | pass | train -0.128, val -0.083 |
| cbi.sma_cross | D6_cost_2x | pass | val Sharpe at 2x 1.110 |
| cbi.sma_cross | D7_delay | pass | val Sharpe with delay 1.041 |
| cbi.sma_cross | D8_top_trades | pass | PnL 11908 -> 4713 after removing top 5 (73 trades) |
| cbi.sma_cross | D9_neighbours | pass | median neighbour train Sharpe 0.518 vs selected 0.751 (n=8) |
| cbi.sma_cross | D10_beats_passive | pass | val Sharpe 1.127 vs EFA 0.565, EW 0.562 |
| cbi.sma_cross | F1_sharpe | pass | final Sharpe 0.630 |
| cbi.sma_cross | F2_max_dd | pass | final max DD -0.168 |
| cbi.sma_cross | F3_cost_2x | pass | final Sharpe at 2x 0.618 |
| cbi.sma_cross | F4_delay | pass | final Sharpe with delay 0.637 |
| cbi.sma_cross | F5_beats_spy | FAIL | final Sharpe 0.630 vs EFA 0.646 |
| cbi.sma_cross | F6_min_trades | pass | final trades 36 |
| cbi.xs_momentum | D1_val_sharpe_positive | pass | val Sharpe 0.429 |
| cbi.xs_momentum | D2_dsr | FAIL | DSR 0.723 (N=25, SR0 ann 0.27, SR ann 0.44); conservative N=75: 0.314 |
| cbi.xs_momentum | D3_pbo | pass | PBO 0.385 |
| cbi.xs_momentum | D4_bootstrap_ci | FAIL | 95% CI [-0.09, 0.99], Sharpe 0.44 |
| cbi.xs_momentum | D5_max_dd | pass | train -0.191, val -0.144 |
| cbi.xs_momentum | D6_cost_2x | pass | val Sharpe at 2x 0.422 |
| cbi.xs_momentum | D7_delay | pass | val Sharpe with delay 0.396 |
| cbi.xs_momentum | D8_top_trades | pass | PnL 8809 -> 502 after removing top 5 (184 trades) |
| cbi.xs_momentum | D9_neighbours | FAIL | median neighbour train Sharpe 0.047 vs selected 0.451 (n=8) |
| cbi.xs_momentum | D10_beats_passive | FAIL | val Sharpe 0.429 vs EFA 0.565, EW 0.562 |
| cbi.rsi_meanrev | D1_val_sharpe_positive | pass | val Sharpe 0.823 |
| cbi.rsi_meanrev | D2_dsr | FAIL | DSR 0.542 (N=25, SR0 ann 0.37, SR ann 0.40); conservative N=75: 0.259 |
| cbi.rsi_meanrev | D3_pbo | pass | PBO 0.482 |
| cbi.rsi_meanrev | D4_bootstrap_ci | FAIL | 95% CI [-0.08, 0.93], Sharpe 0.40 |
| cbi.rsi_meanrev | D5_max_dd | pass | train -0.086, val -0.036 |
| cbi.rsi_meanrev | D6_cost_2x | pass | val Sharpe at 2x 0.716 |
| cbi.rsi_meanrev | D7_delay | pass | val Sharpe with delay 1.229 |
| cbi.rsi_meanrev | D8_top_trades | pass | PnL 1578 -> 707 after removing top 5 (122 trades) |
| cbi.rsi_meanrev | D9_neighbours | FAIL | median neighbour train Sharpe 0.085 vs selected 0.249 (n=8) |
| cbi.rsi_meanrev | D10_beats_passive | pass | val Sharpe 0.823 vs EFA 0.565, EW 0.562 |

### D. Rejected candidates

- cbi.sma_cross (6471d574): F5_beats_spy (final Sharpe 0.630 vs EFA 0.646)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- cbi.xs_momentum (50ba1d4f): D2_dsr (DSR 0.723 (N=25, SR0 ann 0.27, SR ann 0.44); conservative N=75: 0.314); D4_bootstrap_ci (95% CI [-0.09, 0.99], Sharpe 0.44); D9_neighbours (median neighbour train Sharpe 0.047 vs selected 0.451 (n=8)); D10_beats_passive (val Sharpe 0.429 vs EFA 0.565, EW 0.562)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- cbi.rsi_meanrev (929630a4): D2_dsr (DSR 0.542 (N=25, SR0 ann 0.37, SR ann 0.40); conservative N=75: 0.259); D4_bootstrap_ci (95% CI [-0.08, 0.93], Sharpe 0.40); D9_neighbours (median neighbour train Sharpe 0.085 vs selected 0.249 (n=8))
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.

## Market: futures

Universe: ES=F, NQ=F, GC=F, ZN=F. Splits (pre-registered): train 2005-01-01 to 2016-12-31, validation 2017-01-01 to 2020-12-31, locked final test 2021-01-01 to 2026-11-09. Primary benchmark: ES=F buy-and-hold (zero cost), plus equal-weight of the universe. Costs: 1 bp commission and 5 bps slippage per side. Annualisation uses 252 periods per year. Aligned bars: 6540 from 2000-09-21 to 2026-11-09. Data flags: ES=F: High below Open/Close/Low on some bars; ES=F: 10 zero-volume bars; NQ=F: High below Open/Close/Low on some bars; NQ=F: 10 zero-volume bars; GC=F: High below Open/Close/Low on some bars; GC=F: 403 zero-volume bars; ZN=F: High below Open/Close/Low on some bars; ZN=F: 10 zero-volume bars.

### A. Market family ranking

| Family | Ideas | Unique | Best idea score | Family score | Eligible | Chosen |
|---|---|---|---|---|---|---|
| sma_cross | 9 | 9 | 0.91 | 0.96 | True | yes |
| bollinger_meanrev | 9 | 9 | 0.87 | 0.92 | True | yes |
| rsi_meanrev | 23 | 23 | 0.83 | 0.89 | True | yes |
| xs_momentum | 21 | 21 | 0.79 | 0.85 | True |  |
| donchian_breakout | 24 | 24 | 0.75 | 0.81 | True |  |
| other | 26 | 26 | 0.51 | 0.58 | False |  |
| ml_model | 4 | 4 | 0.40 | 0.43 | False |  |
| options_strategy | 6 | 6 | 0.32 | 0.36 | False |  |
| vwap_intraday | 5 | 5 | 0.32 | 0.36 | False |  |
| pairs_stat_arb | 1 | 1 | 0.30 | 0.31 | False |  |
| gap_fade | 5 | 5 | 0.25 | 0.29 | False |  |
| macd_cross | 1 | 1 | 0.20 | 0.21 | False |  |
| volume_signal | 1 | 1 | 0.13 | 0.14 | False |  |

Pre-registered families for this market: sma_cross, bollinger_meanrev, rsi_meanrev.

### B. Results table

Net of costs (1 bp commission + 5 bps slippage per side). Sharpe uses rf = 0, annualised with 252 periods per year. Benchmarks are zero-cost passive series.

| Version | Evaluation period | Net return | Sharpe | Max drawdown | Trades | Costs | Benchmark comparison | Main limitation |
|---|---|---|---|---|---|---|---|---|
| futures.sma_cross 52a9236b {"fast_n": 50, "slow_n": 100} | train 2005-01 to 2016-12 | 84.4% | 0.77 | -9.8% | 62 | base | ES=F Sharpe 0.36 / return 84.1%; EW Sharpe 0.69 |  |
| futures.sma_cross 52a9236b {"fast_n": 50, "slow_n": 100} | validation 2017-01 to 2020-12 | 18.4% | 0.59 | -14.4% | 16 | base | ES=F Sharpe 0.74 / return 67.6%; EW Sharpe 1.30 | failed D3_pbo, D10_beats_passive |
| futures.bollinger_meanrev 479bc7b8 {"bb_n": 15, "bb_std": 2.0} | train 2005-01 to 2016-12 | 27.1% | 0.72 | -5.6% | 164 | base | ES=F Sharpe 0.36 / return 84.1%; EW Sharpe 0.69 |  |
| futures.bollinger_meanrev 479bc7b8 {"bb_n": 15, "bb_std": 2.0} | validation 2017-01 to 2020-12 | 4.1% | 0.28 | -9.5% | 55 | base | ES=F Sharpe 0.74 / return 67.6%; EW Sharpe 1.30 | failed D2_dsr, D10_beats_passive |
| futures.rsi_meanrev c3bcefad {"rsi_entry": 5, "rsi_n": 3} | train 2005-01 to 2016-12 | 11.2% | 0.80 | -1.3% | 26 | base | ES=F Sharpe 0.36 / return 84.1%; EW Sharpe 0.69 |  |
| futures.rsi_meanrev c3bcefad {"rsi_entry": 5, "rsi_n": 3} | validation 2017-01 to 2020-12 | 3.4% | 0.31 | -3.0% | 14 | base | ES=F Sharpe 0.74 / return 67.6%; EW Sharpe 1.30 | failed D2_dsr, D3_pbo, D10_beats_passive |

Grid summary (all trials, train / validation Sharpe at base costs) is in artifacts/cycle002/ and the trials table.

### C. Current champion

No qualifying champion in this market.

Gate results (pre-registered thresholds in config.yaml, committed before these trials):

| Family | Gate | Result | Detail |
|---|---|---|---|
| futures.sma_cross | D1_val_sharpe_positive | pass | val Sharpe 0.595 |
| futures.sma_cross | D2_dsr | pass | DSR 0.956 (N=25, SR0 ann 0.28, SR ann 0.72); conservative N=75: 0.721 |
| futures.sma_cross | D3_pbo | FAIL | PBO 0.791 |
| futures.sma_cross | D4_bootstrap_ci | pass | 95% CI [0.24, 1.23], Sharpe 0.72 |
| futures.sma_cross | D5_max_dd | pass | train -0.098, val -0.144 |
| futures.sma_cross | D6_cost_2x | pass | val Sharpe at 2x 0.584 |
| futures.sma_cross | D7_delay | pass | val Sharpe with delay 0.564 |
| futures.sma_cross | D8_top_trades | pass | PnL 11219 -> 3571 after removing top 5 (78 trades) |
| futures.sma_cross | D9_neighbours | pass | median neighbour train Sharpe 0.689 vs selected 0.765 (n=3) |
| futures.sma_cross | D10_beats_passive | FAIL | val Sharpe 0.595 vs ES=F 0.735, EW 1.297 |
| futures.bollinger_meanrev | D1_val_sharpe_positive | pass | val Sharpe 0.280 |
| futures.bollinger_meanrev | D2_dsr | FAIL | DSR 0.868 (N=25, SR0 ann 0.29, SR ann 0.58); conservative N=75: 0.512 |
| futures.bollinger_meanrev | D3_pbo | pass | PBO 0.469 |
| futures.bollinger_meanrev | D4_bootstrap_ci | pass | 95% CI [0.11, 1.04], Sharpe 0.58 |
| futures.bollinger_meanrev | D5_max_dd | pass | train -0.056, val -0.095 |
| futures.bollinger_meanrev | D6_cost_2x | pass | val Sharpe at 2x 0.185 |
| futures.bollinger_meanrev | D7_delay | pass | val Sharpe with delay 0.590 |
| futures.bollinger_meanrev | D8_top_trades | pass | PnL 3235 -> 2366 after removing top 5 (219 trades) |
| futures.bollinger_meanrev | D9_neighbours | pass | median neighbour train Sharpe 0.467 vs selected 0.717 (n=8) |
| futures.bollinger_meanrev | D10_beats_passive | FAIL | val Sharpe 0.280 vs ES=F 0.735, EW 1.297 |
| futures.rsi_meanrev | D1_val_sharpe_positive | pass | val Sharpe 0.308 |
| futures.rsi_meanrev | D2_dsr | FAIL | DSR 0.644 (N=25, SR0 ann 0.42, SR ann 0.52); conservative N=75: 0.421 |
| futures.rsi_meanrev | D3_pbo | FAIL | PBO 0.601 |
| futures.rsi_meanrev | D4_bootstrap_ci | pass | 95% CI [0.15, 0.95], Sharpe 0.52 |
| futures.rsi_meanrev | D5_max_dd | pass | train -0.013, val -0.030 |
| futures.rsi_meanrev | D6_cost_2x | pass | val Sharpe at 2x 0.275 |
| futures.rsi_meanrev | D7_delay | pass | val Sharpe with delay 0.562 |
| futures.rsi_meanrev | D8_top_trades | pass | PnL 1500 -> 885 after removing top 5 (40 trades) |
| futures.rsi_meanrev | D9_neighbours | pass | median neighbour train Sharpe 0.577 vs selected 0.796 (n=5) |
| futures.rsi_meanrev | D10_beats_passive | FAIL | val Sharpe 0.308 vs ES=F 0.735, EW 1.297 |

### D. Rejected candidates

- futures.sma_cross (52a9236b): D3_pbo (PBO 0.791); D10_beats_passive (val Sharpe 0.595 vs ES=F 0.735, EW 1.297)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- futures.bollinger_meanrev (479bc7b8): D2_dsr (DSR 0.868 (N=25, SR0 ann 0.29, SR ann 0.58); conservative N=75: 0.512); D10_beats_passive (val Sharpe 0.280 vs ES=F 0.735, EW 1.297)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.
- futures.rsi_meanrev (c3bcefad): D2_dsr (DSR 0.644 (N=25, SR0 ann 0.42, SR ann 0.52); conservative N=75: 0.421); D3_pbo (PBO 0.601); D10_beats_passive (val Sharpe 0.308 vs ES=F 0.735, EW 1.297)
  Reconsider with: a new spec version and fresh data not used here (bars after the recorded data end, or a different universe), pre-registered before testing. The locked final segment cannot be reused for this spec.

## E. Next experiments

- Get Reddit API credentials (REDDIT_CLIENT_ID/SECRET) so posts and comments can be read from reddit.com directly and the archive-derived permalinks verified. Falsifiable: every cited URL resolves and its text matches the archive.
- Replicate the strongest single Reddit rule exactly as written (author numbers, not the grid centre) as one pre-registered spec, 1 trial, on fresh post-cycle bars only. Falsifiable: Sharpe above 0 and above the market's primary buy-and-hold after 2x costs.
- Add a second, independent daily dataset (for example a different vendor) and re-run the already-frozen specs for data-source sensitivity. Falsifiable: Sharpe within 0.15 of the yfinance result.
- Weekly cycle: only bars after the recorded data end are new; wait for enough fresh data (at least 6 months) before any re-evaluation of a rejected family, with a new spec version.

## F. Audit summary

- Tools actually used: Python 3.13 venv (backtrader, yfinance, pandas, numpy, scipy, pyyaml), SQLite, git; cached Reddit posts from cycle 1 (no new scrape this cycle)
- Reddit access attempts: none this cycle (reuse of cycle 1 cached posts and comments, --skip-scrape)
- Reddit coverage: 42 of 160 subreddit x keyword x year query windows returned data; 118 windows hit server-side timeouts (HTTP 422 Timeout) and were skipped, so coverage is partial and biased toward windows the archive could serve
- Parser quality: keyword/regex assignment, precision not measured; titles show noise. Families are used for ranking only; each family test is our textbook-style template, not a replication of any post. Cycle 2 did not re-parse or overwrite idea rows.
- Reddit access caveat: reddit.com returned HTTP 403 in cycle 1. Posts and comments came from a third-party archive (Arctic Shift), permalinks are built from archive records and were not live-verified. Authors dropped at ingest. Cycle 2 reused that cache.
- Data: crypto: yfinance adjusted daily, 8 symbols, 3288 aligned bars, 2017-11-09 to 2026-11-09, retrieved 2026-11-10T03:25:15-0700, manifest hash b2459dad8228a9dd, calendar alignment {'method': 'intersection', 'common_bars': 3288, 'first': '2017-11-09', 'last': '2026-11-09', 'dropped_vs_own_calendar': {'BTC-USD': 0, 'ETH-USD': 0, 'LTC-USD': 0, 'XRP-USD': 0, 'BNB-USD': 0, 'ADA-USD': 0, 'DOGE-USD': 0, 'LINK-USD': 0}} | cbi: yfinance adjusted daily, 11 symbols, 4928 aligned bars, 2007-04-11 to 2026-11-09, retrieved 2026-11-10T03:25:17-0700, manifest hash e5b0d99dbecac795, calendar alignment {'method': 'intersection', 'common_bars': 4928, 'first': '2007-04-11', 'last': '2026-11-09', 'dropped_vs_own_calendar': {'GLD': 0, 'SLV': 0, 'USO': 0, 'DBC': 0, 'TLT': 0, 'IEF': 0, 'HYG': 0, 'EFA': 0, 'EEM': 0, 'VNQ': 0, 'UUP': 0}} | futures: yfinance adjusted daily, 4 symbols, 6540 aligned bars, 2000-09-21 to 2026-11-09, retrieved 2026-11-10T03:25:47-0700, manifest hash e70e84048d143b2e, calendar alignment {'method': 'intersection', 'common_bars': 6540, 'first': '2000-09-21', 'last': '2026-11-09', 'dropped_vs_own_calendar': {'ES=F': 58, 'NQ=F': 58, 'GC=F': 19, 'ZN=F': 23}}
- Data issues: crypto: BTC-USD: 2 daily moves > 25% (check adjustment); ETH-USD: 5 daily moves > 25% (check adjustment); LTC-USD: 10 daily moves > 25% (check adjustment); XRP-USD: 26 daily moves > 25% (check adjustment); BNB-USD: 12 daily moves > 25% (check adjustment); ADA-USD: 17 daily moves > 25% (check adjustment); DOGE-USD: 28 daily moves > 25% (check adjustment); LINK-USD: 18 daily moves > 25% (check adjustment) | cbi: SLV: 1 daily moves > 25% (check adjustment); USO: 2 daily moves > 25% (check adjustment) | futures: ES=F: High below Open/Close/Low on some bars; ES=F: 10 zero-volume bars; NQ=F: High below Open/Close/Low on some bars; NQ=F: 10 zero-volume bars; GC=F: High below Open/Close/Low on some bars; GC=F: 403 zero-volume bars; ZN=F: High below Open/Close/Low on some bars; ZN=F: 10 zero-volume bars
- Total parameter trials this cycle: 225 (budget: 25 per family, 3 families per market, separate trial counters and DSR N per market)
- Robustness evaluation runs (not trials): 27 dev stress runs plus final-test runs for survivors
- Final-test accesses this cycle: 1 (each spec hash can be accessed once; enforced by a UNIQUE constraint in the ledger)
- Compute: 247 s summed wall time over the 225 trials, plus stress runs and report building, about 2.2 minutes end to end. Inside the 120 minute cycle budget.
- Posts flagged as injection-like: 4 (kept as data, never followed)
- Constraints: Single dataset vendor; Sharpe rf=0; fractional shares assumed; stops are close-based and exit at next open; the risk-per-position sizing rule is our interpretation; the delay test applies 1 extra bar to all orders; PBO via CSCV is biased above 0.5 on pure noise, so the 0.50 gate is strict. Futures use yfinance continuous contracts with roll artifacts. Crypto uses 365-day annualisation and 7-day bars.
- Monitoring: None configured. No scheduler is running; cron line is documented only.

