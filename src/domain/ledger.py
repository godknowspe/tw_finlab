"""
Pure trade replay. Every view of the portfolio (current positions, per-bar PnL on the chart,
historical equity, holdings export) goes through `Ledger`, so they cannot disagree.

Cost method: moving average. Fees are capitalised into the buy cost basis; sell fee and tax
reduce realised PnL.

Cash starts at 0 and is never negative: when a buy costs more than the cash on hand, the
shortfall is recorded as a deposit (`funded`). Sale proceeds stay as cash and fund later buys
first. So cash is "money left over from sales", and `funded` is the capital put in.

Each buy is also tracked as a lot. A sell is split across the open lots in proportion to their
remaining shares, which is exactly what the moving average does to the position, so the lots
always sum to the position (shares, cost basis, realised PnL). There is no FIFO/LIFO choice to
make: shares are fungible and every open lot takes part in every exit.
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


def trade_sort_key(t: dict):
    # `id` orders same-minute trades as entered; `uid` breaks ties deterministically when two
    # hosts happened to use the same number, so every host replays in the same order.
    return (t["timestamp"], t["id"], t.get("uid", ""))


@dataclass
class Lot:
    trade: dict                 # the BUY that opened it
    shares: float               # still held; fractional after pro-rata sells
    cost: float                 # cost basis of those shares, fees included
    realized_pnl: float = 0.0   # this lot's share of every sell's realised PnL
    proceeds: float = 0.0       # net sale proceeds allocated to this lot
    sold: float = 0.0           # shares of this lot sold so far
    exits: List[dict] = field(default_factory=list)   # (sell trade id, shares, price)


@dataclass
class Position:
    symbol: str
    currency: str
    shares: int = 0
    cost: float = 0.0          # total cost basis of the shares still held, fees included
    realized_pnl: float = 0.0
    lots: List[Lot] = field(default_factory=list)
    net_paid: float = 0.0      # everything paid for buys minus everything received from sells, fees in

    @property
    def avg_cost(self) -> float:
        return self.cost / self.shares if self.shares else 0.0

    @property
    def break_even(self) -> float:
        """Price at which selling all remaining shares makes this symbol's whole history break
        even: net amount paid / shares held. Realised gains pull it below avg_cost, losses above.
        Can be negative once realised gains exceed what is still invested. Ignores the fee and
        tax that selling at that price would itself cost."""
        return self.net_paid / self.shares if self.shares else 0.0


@dataclass
class Ledger:
    cash: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})
    funded: Dict[str, float] = field(default_factory=lambda: {"TWD": 0.0, "USD": 0.0})

    @classmethod
    def empty(cls) -> "Ledger":
        return cls()

    def apply(self, t: dict):
        sym, cur = t["symbol"], t["currency"]
        shares, price = int(t["shares"]), float(t["price"])
        fee, tax = float(t.get("fee", 0.0)), float(t.get("tax", 0.0))
        pos = self.positions.setdefault(sym, Position(sym, cur))

        if t["action"] == "BUY":
            outlay = shares * price + fee + tax
            if self.cash[cur] < outlay:
                deposit = outlay - self.cash[cur]
                self.funded[cur] += deposit
                self.cash[cur] += deposit
            self.cash[cur] -= outlay
            pos.net_paid += outlay
            pos.cost += outlay
            pos.shares += shares
            pos.lots.append(Lot(trade=t, shares=float(shares), cost=outlay))
        else:
            if shares > pos.shares:
                raise ValueError(f"trade {t['id']}: sell {shares} {sym} but only {pos.shares} held")
            basis = pos.cost * shares / pos.shares
            proceeds = shares * price - fee - tax
            pnl = proceeds - basis
            fraction = shares / pos.shares
            for lot in pos.lots:
                if lot.shares <= 0:
                    continue
                n = lot.shares * fraction
                lot_basis, lot_proceeds = lot.cost * fraction, proceeds * n / shares
                lot.shares -= n
                lot.cost -= lot_basis
                lot.sold += n
                lot.proceeds += lot_proceeds
                lot.realized_pnl += lot_proceeds - lot_basis
                lot.exits.append({"trade_id": t["id"], "shares": n, "price": price})
            pos.cost -= basis
            pos.shares -= shares
            pos.realized_pnl += pnl
            self.realized_pnl[cur] += pnl
            self.cash[cur] += proceeds
            pos.net_paid -= proceeds
            if pos.shares == 0:
                pos.cost = 0.0
                for lot in pos.lots:
                    lot.shares, lot.cost = 0.0, 0.0

    def open_positions(self) -> Dict[str, Position]:
        return {s: p for s, p in self.positions.items() if p.shares > 0}


def replay(trades: Iterable[dict]) -> Ledger:
    ledger = Ledger.empty()
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
