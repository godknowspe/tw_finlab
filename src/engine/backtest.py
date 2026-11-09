import math

import pandas as pd

from src.domain.symbols import is_tw

# Commission is charged on both sides; tax only on sells. TW: 0.1425% commission (min NT$20),
# 0.3% securities transaction tax (0.1% for ETFs). US: commission-free broker assumed.
COSTS = {
    "TW": {"fee_rate": 0.001425, "min_fee": 20.0, "tax_rate": 0.003, "etf_tax_rate": 0.001, "lot": 1000, "cash": 1000000},
    "US": {"fee_rate": 0.0, "min_fee": 0.0, "tax_rate": 0.0, "etf_tax_rate": 0.0, "lot": 1, "cash": 30000},
}


class Strategy:
    """策略基類。on_bar 看到第 i 根收盤後才下單，委託在第 i+1 根開盤成交（不偷看收盤價）。"""
    def __init__(self):
        self.broker = None
        self.data = None
        self.params = {}

    def init(self):
        """策略初始化（例如計算指標）"""

    def on_bar(self, i, bar):
        """每根 K 棒收盤後執行。i: 當前索引，bar: 當前 K 棒 (Series)"""

    @property
    def symbol(self):
        return self.data.iloc[0]["stock_id"]

    @property
    def lot(self):
        return self.broker.costs["lot"]

    def buy(self, size=None):
        self.broker.submit_order("buy", size)

    def sell(self, size=None):
        self.broker.submit_order("sell", size)


class BacktestEngine:
    """Single-symbol, long-only bar backtest with next-open execution."""

    def __init__(self, data: pd.DataFrame, initial_cash=None):
        """initial_cash is in the instrument's currency; defaults to NT$1M (TW) / US$30k (US)."""
        symbol = str(data.iloc[0]["stock_id"]) if not data.empty else ""
        self.costs = COSTS["TW" if is_tw(symbol) else "US"]
        self.data = data
        self.initial_cash = float(initial_cash if initial_cash is not None else self.costs["cash"])
        self.cash = self.initial_cash
        self.shares = 0
        self.history = []
        self.trades = []
        self._pending = None
        self._tax_rate = self.costs["etf_tax_rate"] if symbol.startswith("00") else self.costs["tax_rate"]

    def submit_order(self, side, size=None):
        """Queue an order for the next bar's open. size=None: buy as many lots as cash allows / sell all."""
        self._pending = (side, size)

    def _fee(self, notional):
        return max(notional * self.costs["fee_rate"], self.costs["min_fee"]) if self.costs["fee_rate"] else 0.0

    def _fill(self, i, side, size):
        price = float(self.data.iloc[i]["open"])
        if not (math.isfinite(price) and price > 0):
            # No valid open (halt, bad data): the order is dropped, not filled for free.
            return
        lot = self.costs["lot"]
        if side == "buy":
            if size is None:
                size = int(self.cash / (price * (1 + self.costs["fee_rate"])) // lot * lot)
                while size > 0 and size * price + self._fee(size * price) > self.cash:
                    size -= lot
            cost = size * price + self._fee(size * price)
            if size <= 0 or cost > self.cash:
                return
            self.cash -= cost
            self.shares += size
        else:
            size = self.shares if size is None else min(size, self.shares)
            if size <= 0:
                return
            notional = size * price
            self.cash += notional - self._fee(notional) - notional * self._tax_rate
            self.shares -= size
        self.trades.append({"date": self.data.index[i], "side": side, "price": price, "size": size})

    def run(self, strategy_cls):
        strategy = strategy_cls()
        strategy.data = self.data
        strategy.broker = self
        strategy.init()
        for i in range(len(self.data)):
            if self._pending:
                side, size = self._pending
                self._pending = None
                self._fill(i, side, size)
            bar = self.data.iloc[i]
            strategy.on_bar(i, bar)
            self.history.append({"date": bar.name, "total_equity": self.cash + self.shares * float(bar["close"])})
        return self._performance()

    def _performance(self):
        df = pd.DataFrame(self.history)
        if df.empty:
            return {"total_return": 0.0, "max_drawdown": 0.0, "final_equity": self.initial_cash, "equity_curve": df, "trades": []}
        peak = df["total_equity"].cummax().clip(lower=self.initial_cash)
        return {
            "total_return": df["total_equity"].iloc[-1] / self.initial_cash - 1,
            "max_drawdown": ((df["total_equity"] - peak) / peak).min(),
            "final_equity": df["total_equity"].iloc[-1],
            "equity_curve": df,
            "trades": self.trades,
        }
