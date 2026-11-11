"""
Valuation on top of `ledger.replay`. Two return measures, named for what they divide by:

- account equity: cash left over from sales + holdings at market (what /api/portfolio shows);
  money only enters as the deposits needed to fund buys (see ledger.py)
- invested-capital ROI: that equity over the deposits made so far (what the Equity chart shows)

A position with no known price is never valued at 0: current valuation falls back to cost
and says so; history carries the last known price forward and, before the first known price,
holds the position at cost. Either way the result lists which symbols were estimated.
"""
import datetime
import math
from typing import Dict, List

import pandas as pd

from src.domain.bars import bar_ends
from src.domain.ledger import Ledger, replay, trade_sort_key


def valid_price(p) -> bool:
    return p is not None and math.isfinite(p) and p > 0


def value_positions(ledger: Ledger, prices: Dict[str, float], fx_usd_twd: float) -> dict:
    rows, mv, estimated = [], {"TWD": 0.0, "USD": 0.0}, []
    for sym, pos in ledger.open_positions().items():
        price = prices.get(sym)
        if not valid_price(price):
            price = pos.avg_cost
            estimated.append(sym)
        market_value = price * pos.shares
        mv[pos.currency] += market_value
        unrealized = market_value - pos.cost
        rows.append({
            "symbol": sym,
            "shares": pos.shares,
            "avg_cost": round(pos.avg_cost, 4),
            "break_even": round(pos.break_even, 4),
            "last_price": round(price, 4),
            "currency": pos.currency,
            "market_value": round(market_value, 2),
            "unrealized": round(unrealized, 2),
            "unrealized_pct": round(unrealized / pos.cost * 100, 2) if pos.cost else 0.0,
            "realized": round(pos.realized_pnl, 2),
            "price_estimated": sym in estimated,
        })
    equity_twd = ledger.cash["TWD"] + mv["TWD"] + (ledger.cash["USD"] + mv["USD"]) * fx_usd_twd
    return {
        "positions": rows,
        "summary": {
            "cash_twd": round(ledger.cash["TWD"], 2),
            "cash_usd": round(ledger.cash["USD"], 2),
            "deposited_twd": round(ledger.funded["TWD"], 2),
            "deposited_usd": round(ledger.funded["USD"], 2),
            "market_value_twd": round(mv["TWD"], 2),
            "market_value_usd": round(mv["USD"], 2),
            "realized_twd": round(ledger.realized_pnl["TWD"], 2),
            "realized_usd": round(ledger.realized_pnl["USD"], 2),
            "total_equity_twd": round(equity_twd, 2),
            "usd_twd_rate": fx_usd_twd,
            "estimated_prices": estimated,
        },
    }


def _roi(equity: float, invested: float) -> float:
    return round((equity / invested - 1.0) * 100, 2) if invested > 0 else 0.0


def historical_roi(trades: List[dict], closes: pd.DataFrame, fx: pd.Series, fallback_fx: float,
                   today: datetime.date = None) -> dict:
    """Daily invested-capital ROI per market and combined, from the first trade to today.

    Combined ROI is in TWD: each day's USD equity is converted at that day's USD/TWD (`fx`,
    carried forward over gaps), and USD deposits at the rate of the day they were made, so the
    combined line includes currency gains and losses. Before the first known rate the earliest
    one is used; `fallback_fx` only when there is no rate history at all."""
    if not trades:
        return {"tw": [], "us": [], "total": [], "estimated": []}
    today = today or datetime.date.today()
    ordered = sorted(trades, key=trade_sort_key)
    by_day: Dict[datetime.date, List[dict]] = {}
    for t in ordered:
        by_day.setdefault(datetime.date.fromisoformat(t["timestamp"][:10]), []).append(t)

    closes = closes.copy()
    if not closes.empty:
        closes.index = pd.to_datetime(closes.index).date

    day = min(by_day)
    # Carry forward the last valid close from before the first trade day.
    last_price: Dict[str, float] = {}
    for d, row in closes[closes.index < day].iterrows() if not closes.empty else []:
        for sym, p in row.items():
            if valid_price(p):
                last_price[sym] = float(p)

    rates = {}
    if fx is not None and not fx.empty:
        fx = fx.copy()
        fx.index = pd.to_datetime(fx.index).date
        rates = {d: float(r) for d, r in fx.items() if valid_price(r)}
    # Start from the last rate on or before the first trade day, else the earliest known rate.
    earlier = [d for d in rates if d <= day]
    rate = rates[max(earlier)] if earlier else (rates[min(rates)] if rates else fallback_fx)

    ledger = Ledger.empty()
    estimated = set()
    out = {"tw": [], "us": [], "total": []}
    while day <= today:
        rate = rates.get(day, rate)
        for t in by_day.get(day, []):
            ledger.apply(t, usd_twd=rate)
        if day in closes.index:
            for sym, p in closes.loc[day].items():
                if valid_price(p):
                    last_price[sym] = float(p)
        if day.weekday() < 5:
            mv = {"TWD": 0.0, "USD": 0.0}
            for sym, pos in ledger.open_positions().items():
                if sym in last_price:
                    mv[pos.currency] += last_price[sym] * pos.shares
                else:
                    mv[pos.currency] += pos.cost
                    estimated.add(sym)
            eq_twd = ledger.cash["TWD"] + mv["TWD"]
            eq_usd = ledger.cash["USD"] + mv["USD"]
            inv_twd, inv_usd = ledger.funded["TWD"], ledger.funded["USD"]
            stamp = day.isoformat()
            out["tw"].append({"time": stamp, "value": _roi(eq_twd, inv_twd)})
            out["us"].append({"time": stamp, "value": _roi(eq_usd, inv_usd)})
            out["total"].append({"time": stamp, "value": _roi(eq_twd + eq_usd * rate, ledger.funded_twd)})
        day += datetime.timedelta(days=1)
    out["estimated"] = sorted(estimated)
    return out


def bar_pnl(trades: List[dict], bar_index: pd.DatetimeIndex, closes: pd.Series, interval: str) -> List[dict]:
    """Per-bar total PnL (realized + unrealized) for one symbol, valued at each bar's close.
    A trade is applied once its time is before the bar's end (bars.bar_end), so a fill inside
    the bar counts in that bar, and fills after the last bar never leak into it."""
    ordered = sorted(trades, key=trade_sort_key)
    ends = bar_ends(bar_index, interval)
    ledger = Ledger.empty()
    sym = ordered[0]["symbol"] if ordered else None
    i, out = 0, []
    for n, end in enumerate(ends):
        while i < len(ordered) and pd.Timestamp(ordered[i]["timestamp"]) < end:
            ledger.apply(ordered[i])
            i += 1
        pos = ledger.positions.get(sym) if sym else None
        if pos is None or (pos.shares == 0 and pos.realized_pnl == 0):
            out.append({"total_pnl": None, "pnl_pct": None})
            continue
        close = float(closes.iloc[n])
        unrealized = close * pos.shares - pos.cost if pos.shares else 0.0
        out.append({
            "total_pnl": pos.realized_pnl + unrealized,
            "pnl_pct": (unrealized / pos.cost * 100) if pos.shares and pos.cost else None,
        })
    return out
