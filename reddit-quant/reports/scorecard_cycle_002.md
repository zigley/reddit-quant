| Market | Family | Selected params | Train Sharpe | Val Sharpe | DSR | PBO | Gates | Final Sharpe | Status |
|---|---|---|---|---|---|---|---|---|---|
| crypto | crypto.rsi_meanrev | {"rsi_entry": 15, "rsi_n": 5} | 0.93 | 1.21 | 0.89 | 0.22 | 8/10 | n/a | REJECTED |
| crypto | crypto.xs_momentum | {"lookback": 21, "top_n": 3} | 1.74 | -0.57 | 0.90 | 0.53 | 2/10 | n/a | REJECTED |
| crypto | crypto.sma_cross | {"fast_n": 50, "slow_n": 250} | 1.52 | 0.22 | 0.99 | 0.94 | 7/10 | n/a | REJECTED |
| cbi | cbi.sma_cross | {"fast_n": 40, "slow_n": 150} | 0.75 | 1.13 | 0.98 | 0.15 | 15/16 | 0.63 | REJECTED |
| cbi | cbi.xs_momentum | {"lookback": 63, "top_n": 3} | 0.45 | 0.43 | 0.72 | 0.39 | 6/10 | n/a | REJECTED |
| cbi | cbi.rsi_meanrev | {"rsi_entry": 15, "rsi_n": 5} | 0.25 | 0.82 | 0.54 | 0.48 | 7/10 | n/a | REJECTED |
| futures | futures.sma_cross | {"fast_n": 50, "slow_n": 100} | 0.77 | 0.59 | 0.96 | 0.79 | 8/10 | n/a | REJECTED |
| futures | futures.bollinger_meanrev | {"bb_n": 15, "bb_std": 2.0} | 0.72 | 0.28 | 0.87 | 0.47 | 8/10 | n/a | REJECTED |
| futures | futures.rsi_meanrev | {"rsi_entry": 5, "rsi_n": 3} | 0.80 | 0.31 | 0.64 | 0.60 | 7/10 | n/a | REJECTED |
