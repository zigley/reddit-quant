"""Backtrader engine.

Execution model
  * Signals are computed on the close of bar t. Orders are submitted then and Backtrader fills
    market orders at the OPEN of bar t+1 (cheat_on_open is never enabled).
  * Costs: percentage commission per side plus percentage slippage per side (slip_open=True so the
    slippage also applies to open-price fills).
  * delay_bars=k holds each intent for k extra bars before the order is submitted.
  * Long only, 1x gross cap, fractional shares (Alpaca supports them), no derivatives.
  * Sizing (interpretation, not given by Reddit): risk 2% of equity to a close-based stop at
    entry - stop_atr * ATR(14); size also capped at 25% of equity per position and by remaining
    gross room (<= 98% of equity after the position). Max 5 concurrent positions.
    The stop is checked on the close and exits at the next open, so gaps can exceed the 2%.
"""
import math

import backtrader as bt
import numpy as np
import pandas as pd

TEMPLATES = {
    "rsi_meanrev": {"fixed": {"trend_n": 200, "rsi_exit": 60, "max_hold": 10, "stop_atr": 3.0},
                    "grid": {"rsi_n": [2, 3, 4, 5, 7], "rsi_entry": [5, 10, 15, 20, 25]},
                    "default": {"rsi_n": 4, "rsi_entry": 15}},
    "ibs_meanrev": {"fixed": {"max_hold": 5, "stop_atr": 3.0},
                    "grid": {"ibs_entry": [0.10, 0.15, 0.20, 0.25, 0.30], "trend_n": [50, 100, 150, 200, 250]},
                    "default": {"ibs_entry": 0.20, "trend_n": 150}},
    "sma_cross": {"fixed": {"stop_atr": 3.0},
                  "grid": {"fast_n": [10, 20, 30, 40, 50], "slow_n": [100, 150, 200, 250, 300]},
                  "default": {"fast_n": 30, "slow_n": 200}},
    "donchian_breakout": {"fixed": {"stop_atr": 3.0},
                          "grid": {"entry_n": [20, 40, 60, 80, 100], "exit_n": [10, 20, 30, 40, 50]},
                          "default": {"entry_n": 60, "exit_n": 30}},
    "bollinger_meanrev": {"fixed": {"trend_n": 200, "max_hold": 10, "stop_atr": 3.0},
                          "grid": {"bb_n": [10, 15, 20, 25, 30], "bb_std": [1.5, 2.0, 2.5, 3.0, 3.5]},
                          "default": {"bb_n": 20, "bb_std": 2.5}},
    "xs_momentum": {"fixed": {"rebalance_bars": 21, "stop_atr": 3.0},
                    "grid": {"lookback": [21, 63, 126, 189, 252], "top_n": [1, 2, 3, 4, 5]},
                    "default": {"lookback": 126, "top_n": 3}},
}


def grid_configs(template):
    g = TEMPLATES[template]["grid"]
    keys = list(g.keys())
    out = []
    for a in g[keys[0]]:
        for b in g[keys[1]]:
            out.append({keys[0]: a, keys[1]: b})
    return out


class GenericStrategy(bt.Strategy):
    params = dict(template="rsi_meanrev", tp=None, risk=None, delay_bars=0)

    def __init__(self):
        self.tp = dict(self.p.tp)
        self.risk = self.p.risk
        self.T = self.p.template
        self.ind = {}
        for d in self.datas:
            I = {"atr": bt.indicators.ATR(d, period=14)}
            tp = self.tp
            if self.T == "rsi_meanrev":
                I["rsi"] = bt.indicators.RSI_Safe(d.close, period=int(tp["rsi_n"]))
                I["trend"] = bt.indicators.SMA(d.close, period=int(tp["trend_n"]))
            elif self.T == "ibs_meanrev":
                I["trend"] = bt.indicators.SMA(d.close, period=int(tp["trend_n"]))
            elif self.T == "sma_cross":
                I["fast"] = bt.indicators.SMA(d.close, period=int(tp["fast_n"]))
                I["slow"] = bt.indicators.SMA(d.close, period=int(tp["slow_n"]))
            elif self.T == "donchian_breakout":
                I["hh"] = bt.indicators.Highest(d.high, period=int(tp["entry_n"]))
                I["ll"] = bt.indicators.Lowest(d.low, period=int(tp["exit_n"]))
            elif self.T == "bollinger_meanrev":
                I["bb"] = bt.indicators.BollingerBands(d.close, period=int(tp["bb_n"]), devfactor=float(tp["bb_std"]))
                I["trend"] = bt.indicators.SMA(d.close, period=int(tp["trend_n"]))
            elif self.T == "xs_momentum":
                I["warm"] = bt.indicators.SMA(d.close, period=int(tp["lookback"]) + 1)
            self.ind[d] = I
        self.pending = {d: None for d in self.datas}
        self.entry = {}
        self.entry_val = {}
        self.intents = []          # (due_bar, kind, data, score)
        self.eq_dates, self.eq_vals, self.gross_vals = [], [], []
        self.orders_log, self.trades_log = [], []
        self.n_rejected = 0
        self.bar = 0
        self.xs_target = set()

    # ----- bookkeeping -----
    def notify_order(self, order):
        d = order.data
        if order.status in (order.Submitted, order.Accepted):
            return
        if order.status == order.Completed:
            dt = bt.num2date(order.executed.dt).date()
            self.orders_log.append({"date": str(dt), "data": d._name, "side": "buy" if order.isbuy() else "sell",
                                    "size": float(order.executed.size), "price": float(order.executed.price),
                                    "value": float(abs(order.executed.size) * order.executed.price),
                                    "comm": float(order.executed.comm), "bar_open": float(d.open[0])})
            if order.isbuy():
                self.entry_val[d] = float(abs(order.executed.size) * order.executed.price)
                self.entry[d] = {"bar": self.bar, "price": float(order.executed.price),
                                 "atr": self.entry.get(("atr", d), float(self.ind[d]["atr"][0]))}
            else:
                self.entry.pop(d, None)
        elif order.status in (order.Margin, order.Rejected):
            self.n_rejected += 1
        elif order.status == order.Canceled:
            pass
        self.pending[d] = None

    def notify_trade(self, trade):
        if trade.isclosed:
            entry_val = self.entry_val.get(trade.data, 0.0)
            self.trades_log.append({
                "data": trade.data._name, "entry_date": str(bt.num2date(trade.dtopen).date()),
                "exit_date": str(bt.num2date(trade.dtclose).date()),
                "pnl": float(trade.pnlcomm), "ret": float(trade.pnlcomm / entry_val) if entry_val else 0.0,
                "bars": int(trade.barlen)})

    # ----- signals -----
    def entry_signal(self, d):
        I, tp, T = self.ind[d], self.tp, self.T
        c = d.close[0]
        if T == "rsi_meanrev":
            if I["rsi"][0] < tp["rsi_entry"] and c > I["trend"][0]:
                return float(tp["rsi_entry"] - I["rsi"][0])
        elif T == "ibs_meanrev":
            rng = d.high[0] - d.low[0]
            ibs = (c - d.low[0]) / rng if rng > 0 else 0.5
            if ibs < tp["ibs_entry"] and c > I["trend"][0]:
                return float(tp["ibs_entry"] - ibs)
        elif T == "sma_cross":
            if I["fast"][0] > I["slow"][0] and I["fast"][-1] <= I["slow"][-1]:
                return float(I["fast"][0] / I["slow"][0] - 1)
        elif T == "donchian_breakout":
            if c > I["hh"][-1]:
                return float(c / I["hh"][-1] - 1)
        elif T == "bollinger_meanrev":
            if c < I["bb"].lines.bot[0] and c > I["trend"][0]:
                return float((I["bb"].lines.bot[0] - c) / I["atr"][0]) if I["atr"][0] > 0 else 0.0
        elif T == "xs_momentum":
            if d in self.xs_target:
                lb = int(tp["lookback"])
                return float(c / d.close[-lb] - 1)
        return None

    def exit_signal(self, d):
        I, tp, T = self.ind[d], self.tp, self.T
        c = d.close[0]
        e = self.entry.get(d)
        held = self.bar - e["bar"] if e else 0
        if e and c < e["price"] - self.tp.get("stop_atr", 3.0) * e["atr"]:
            return "stop"
        if T == "rsi_meanrev":
            if I["rsi"][0] > tp["rsi_exit"]:
                return "signal"
            if held >= tp["max_hold"]:
                return "time"
        elif T == "ibs_meanrev":
            if c > d.high[-1]:
                return "signal"
            if held >= tp["max_hold"]:
                return "time"
        elif T == "sma_cross":
            if I["fast"][0] < I["slow"][0]:
                return "signal"
        elif T == "donchian_breakout":
            if c < I["ll"][-1]:
                return "signal"
        elif T == "bollinger_meanrev":
            if c > I["bb"].lines.mid[0]:
                return "signal"
            if held >= tp["max_hold"]:
                return "time"
        elif T == "xs_momentum":
            if d not in self.xs_target and self._rebalance_bar():
                return "signal"
        return None

    def _rebalance_bar(self):
        return self.bar % int(self.tp["rebalance_bars"]) == 0

    def _update_xs_target(self):
        lb, n = int(self.tp["lookback"]), int(self.tp["top_n"])
        scores = []
        for d in self.datas:
            if len(d) > lb:
                r = d.close[0] / d.close[-lb] - 1
                scores.append((r, d._name, d))
        scores.sort(key=lambda x: (-x[0], x[1]))
        self.xs_target = {d for r, _, d in scores[:n] if r > 0}

    # ----- order helpers -----
    def gross_value(self):
        return sum(abs(self.getposition(d).size) * d.close[0] for d in self.datas)

    def n_open_or_pending_entries(self):
        n = 0
        for d in self.datas:
            if self.getposition(d).size > 0 or (self.pending[d] is not None and self.pending[d].isbuy()):
                n += 1
        return n

    def pending_entry_value(self):
        v = 0.0
        for d in self.datas:
            o = self.pending[d]
            if o is not None and o.isbuy():
                v += abs(o.created.size) * d.close[0]
        return v

    def submit_entry(self, d):
        if self.getposition(d).size > 0 or self.pending[d] is not None:
            return
        if self.n_open_or_pending_entries() >= self.risk["max_concurrent_positions"]:
            return
        eq = self.broker.getvalue()
        atr = float(self.ind[d]["atr"][0])
        c = float(d.close[0])
        stop_dist = self.tp.get("stop_atr", 3.0) * atr
        if stop_dist <= 0 or c <= 0:
            return
        size_risk = self.risk["max_risk_per_position"] * eq / stop_dist
        size_cap = self.risk["max_position_concentration"] * eq / c
        room = self.risk["max_gross_leverage"] * 0.98 * eq - self.gross_value() - self.pending_entry_value()
        size = min(size_risk, size_cap, room / c)
        if size * c < 1.0:
            return
        self.entry[("atr", d)] = atr
        self.pending[d] = self.buy(data=d, size=size)

    def submit_exit(self, d):
        if self.getposition(d).size > 0 and self.pending[d] is None:
            self.pending[d] = self.close(data=d)

    # ----- main loop -----
    def next(self):
        self.bar += 1
        dt = self.datas[0].datetime.date(0)
        eqv = self.broker.getvalue()
        self.eq_dates.append(str(dt))
        self.eq_vals.append(float(eqv))
        self.gross_vals.append(float(self.gross_value() / eqv) if eqv > 0 else 0.0)

        # release delayed intents
        due = [i for i in self.intents if i[0] <= self.bar]
        self.intents = [i for i in self.intents if i[0] > self.bar]
        due.sort(key=lambda i: (i[1] != "exit", -i[3]))
        for _, kind, d, score in due:
            if kind == "exit":
                self.submit_exit(d)
            else:
                self.submit_entry(d)

        if self.T == "xs_momentum" and self._rebalance_bar():
            self._update_xs_target()

        delay = int(self.p.delay_bars)
        # exits first
        for d in self.datas:
            if self.getposition(d).size > 0 and self.pending[d] is None and not self._intent_exists(d, "exit"):
                if self.exit_signal(d):
                    self._emit("exit", d, 0.0, delay)
        # entries ranked by score
        cands = []
        for d in self.datas:
            if self.getposition(d).size == 0 and self.pending[d] is None and not self._intent_exists(d, "entry"):
                if self.T == "xs_momentum" and not self._rebalance_bar():
                    continue
                s = self.entry_signal(d)
                if s is not None:
                    cands.append((s, d))
        cands.sort(key=lambda x: (-x[0], x[1]._name))
        for s, d in cands:
            self._emit("entry", d, s, delay)

    def _intent_exists(self, d, kind):
        return any(i[2] is d and i[1] == kind for i in self.intents)

    def _emit(self, kind, d, score, delay):
        if delay <= 0:
            (self.submit_exit if kind == "exit" else self.submit_entry)(d)
        else:
            self.intents.append((self.bar + delay, kind, d, score))


def run_backtest(cfg, prices, template, params, end=None, cost_mult=1.0, delay_bars=0, cash=None):
    """Run one backtest on `prices` (dict sym->DataFrame), truncated at `end` inclusive.

    Returns dict(equity=Series, gross=Series, trades=list, orders=list, n_rejected=int).
    """
    if cfg.get("live_trading") is not False:
        raise SystemExit("live_trading must be false")
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.set_coc(False)
    cerebro.broker.setcash(cash or cfg["initial_capital"])
    cerebro.broker.setcommission(commission=cfg["costs"]["commission_perc"] * cost_mult)
    cerebro.broker.set_slippage_perc(cfg["costs"]["slippage_perc"] * cost_mult, slip_open=True, slip_limit=True,
                                     slip_match=True, slip_out=False)
    for sym, df in prices.items():
        if end is not None:
            df = df.loc[: pd.Timestamp(end)]
        feed = bt.feeds.PandasData(dataname=df, open="Open", high="High", low="Low", close="Close",
                                   volume="Volume", openinterest=None)
        cerebro.adddata(feed, name=sym)
    tp = dict(TEMPLATES[template]["fixed"])
    tp.update(params)
    cerebro.addstrategy(GenericStrategy, template=template, tp=tp, risk=cfg["risk_limits"], delay_bars=delay_bars)
    strat = cerebro.run(runonce=True, preload=True)[0]
    idx = pd.to_datetime(strat.eq_dates)
    return {"equity": pd.Series(strat.eq_vals, index=idx), "gross": pd.Series(strat.gross_vals, index=idx),
            "trades": strat.trades_log, "orders": strat.orders_log, "n_rejected": strat.n_rejected}
