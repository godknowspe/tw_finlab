"""
Pure trade replay. Every view of the portfolio (current positions, per-bar PnL on the chart,
historical equity, holdings export) goes through `Ledger`, so they cannot disagree.

Cost method: moving average. Fees are capitalised into the buy cost basis; sell fee and tax
reduce realised PnL. Cash moves by the net amount actually paid or received.
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


def trade_sort_key(t: dict):
    return (t["timestamp"], t["id"])


@dataclass
class Position:
    symbol: str
    currency: str
    shares: int = 0
    cost: float = 0.0          # total cost basis of the shares still held, fees included
    realized_pnl: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.cost / self.shares if self.shares else 0.0


@dataclass
class Ledger:
    cash: Dict[str, float]
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})
    # Deposits needed so far to fund buys that exceeded available cash (for invested-capital ROI).
    funded: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})
    # Cash including those deposits, so it never goes below zero.
    funded_cash: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})

    @classmethod
    def empty(cls, cash_twd: float = 0.0, cash_usd: float = 0.0) -> "Ledger":
        cash = {"TWD": float(cash_twd), "USD": float(cash_usd)}
        return cls(cash=cash, funded_cash=dict(cash))

    def apply(self, t: dict):
        sym, cur = t["symbol"], t["currency"]
        shares, price = int(t["shares"]), float(t["price"])
        fee, tax = float(t.get("fee", 0.0)), float(t.get("tax", 0.0))
        pos = self.positions.setdefault(sym, Position(sym, cur))

        if t["action"] == "BUY":
            outlay = shares * price + fee + tax
            if self.funded_cash[cur] < outlay:
                deposit = outlay - self.funded_cash[cur]
                self.funded[cur] += deposit
                self.funded_cash[cur] += deposit
            self.funded_cash[cur] -= outlay
            pos.cost += outlay
            pos.shares += shares
            self.cash[cur] -= outlay
        else:
            if shares > pos.shares:
                raise ValueError(f"trade {t['id']}: sell {shares} {sym} but only {pos.shares} held")
            basis = pos.cost * shares / pos.shares
            proceeds = shares * price - fee - tax
            pnl = proceeds - basis
            pos.cost -= basis
            pos.shares -= shares
            pos.realized_pnl += pnl
            self.realized_pnl[cur] += pnl
            self.cash[cur] += proceeds
            self.funded_cash[cur] += proceeds
            if pos.shares == 0:
                pos.cost = 0.0

    def open_positions(self) -> Dict[str, Position]:
        return {s: p for s, p in self.positions.items() if p.shares > 0}


def replay(trades: Iterable[dict], cash_twd: float = 0.0, cash_usd: float = 0.0) -> Ledger:
    ledger = Ledger.empty(cash_twd, cash_usd)
    for t in sorted(trades, key=trade_sort_key):
        ledger.apply(t)
    return ledger


def validate_trades(trades: List[dict]) -> Optional[str]:
    """Returns an error message if replaying the trades would oversell, else None."""
    try:
        replay(trades)
    except ValueError as e:
        return str(e)
    return None
