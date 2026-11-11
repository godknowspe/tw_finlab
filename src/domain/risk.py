"""
Volatility-based trailing stops and sell/buy-back round trips. Pure functions over prices and
trades; no I/O.

Stops
  stop = (highest close of the last LOOKBACK sessions) x (1 - pct), with pct = ATR_MULT x ATR(14)
  as a fraction of the last close, unless the user set a percentage for that symbol. The stop
  trails the recent high, so it rises with the price and never depends on the buy price.
  ETFs get the same line but only as a warning; individual stocks get a stop-loss.

Round trips
  A round trip starts with any sell (partial or full), collects every later sell until
  the sold shares have been bought back, and ends with the buy that completes the buy-back.
  Extra shares in that closing buy are a new purchase, not part of the trip. If nothing has
  bought the shares back within REBUY_WINDOW sessions of the last sell, it was a reduction.
  An unfinished trip is shown as open and marked at the last close.
  Result vs simply holding = sale proceeds - buy-back cost - fees and tax on both legs.
"""
from typing import Dict, List, Optional

import pandas as pd

from src.domain.ledger import trade_sort_key

ATR_PERIOD = 14
ATR_MULT = 2.5
LOOKBACK = 20
REBUY_WINDOW = 60


def atr_pct(bars: pd.DataFrame, period: int = ATR_PERIOD) -> Optional[float]:
    """Average true range over `period` sessions, as a fraction of the last close."""
    if len(bars) < period + 1:
        return None
    c, h, l = bars["close"], bars["high"], bars["low"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    value = tr.tail(period).mean() / c.iloc[-1]
    return float(value) if pd.notna(value) and value > 0 else None


def trailing_stop(bars: pd.DataFrame, is_etf: bool, custom_pct: Optional[float] = None,
                  live_price: Optional[float] = None) -> Optional[dict]:
    """Stop level for one holding, or None without enough price history. The line comes from
    daily closes; `live_price` (an intraday quote) is what is checked against it, so a breach
    during the session shows before the daily bar closes."""
    atr = atr_pct(bars)
    if atr is None:
        return None
    suggested = ATR_MULT * atr
    pct = custom_pct / 100 if custom_pct else suggested
    last = float(live_price) if live_price else float(bars["close"].iloc[-1])
    high = max(float(bars["close"].tail(LOOKBACK).max()), last)
    stop = high * (1 - pct)
    return {
        "kind": "warning" if is_etf else "stop_loss",
        "stop_price": round(stop, 4),
        "stop_pct": round(pct * 100, 2),
        "suggested_pct": round(suggested * 100, 2),
        "custom": bool(custom_pct),
        "ref_high": round(high, 4),
        "last": round(last, 4),
        "distance_pct": round((last / stop - 1) * 100, 2),
        "triggered": last <= stop,
    }


def trade_cost(t: dict) -> float:
    """Recorded fee + tax, or an estimate when none was entered: TW 0.1425% each side plus
    0.3% (stocks) / 0.1% (ETFs, 00xx codes) tax on sells; US brokers assumed commission-free."""
    if t.get("fee") or t.get("tax"):
        return float(t.get("fee", 0.0)) + float(t.get("tax", 0.0))
    if t["currency"] != "TWD":
        return 0.0
    notional = t["shares"] * t["price"]
    tax = (0.001 if t["symbol"].startswith("00") else 0.003) if t["action"] == "SELL" else 0.0
    return notional * (0.001425 + tax)


def round_trips(trades: List[dict], closes: Dict[str, pd.Series]) -> List[dict]:
    out = []
    by_symbol: Dict[str, List[dict]] = {}
    for t in sorted(trades, key=trade_sort_key):
        by_symbol.setdefault(t["symbol"], []).append(t)

    for sym, ts in by_symbol.items():
        c = closes.get(sym)
        sessions = c.index if c is not None and not c.empty else None
        held, trip = 0, None

        def gap(since, until):
            if sessions is None:
                return (until - since).days * 5 // 7
            return int(((sessions > since) & (sessions <= until)).sum())

        def close_trip(status, end=None):
            sold, back = trip["sold"], trip["rebought"]
            avg_sell = trip["proceeds"] / sold
            avg_buy = trip["buy_cost"] / back if back else None
            row = {
                "symbol": sym, "currency": ts[0]["currency"], "status": status,
                "start": trip["start"], "end": end, "shares_sold": sold, "shares_rebought": back,
                "avg_sell": round(avg_sell, 4), "avg_buy": round(avg_buy, 4) if avg_buy else None,
                "fees": round(trip["fees"], 2), "sells": trip["sells"], "buys": trip["buys"],
            }
            if status == "closed":
                row["vs_hold"] = round(trip["proceeds"] - trip["buy_cost"] - trip["fees"], 2)
            elif status == "open" and c is not None and not c.empty:
                last = float(c.iloc[-1])
                left = sold - back
                # As if the remaining shares were bought back now.
                row["vs_hold"] = round(trip["proceeds"] - trip["buy_cost"] - left * last - trip["fees"], 2)
                row["marked_at"] = last
            else:
                row["vs_hold"] = None
            row["vs_hold_pct"] = round(row["vs_hold"] / trip["proceeds"] * 100, 2) if row["vs_hold"] is not None else None
            out.append(row)

        for t in ts:
            day = pd.Timestamp(t["timestamp"][:10])
            if trip and trip["rebought"] < trip["sold"] and gap(trip["last_sell"], day) > REBUY_WINDOW:
                close_trip("reduction")
                trip = None
            if t["action"] == "SELL":
                if trip is None:
                    trip = {"start": t["timestamp"][:10], "sold": 0, "rebought": 0, "proceeds": 0.0,
                            "buy_cost": 0.0, "fees": 0.0, "sells": [], "buys": []}
                trip["sold"] += t["shares"]
                trip["proceeds"] += t["shares"] * t["price"]
                trip["fees"] += trade_cost(t)
                trip["last_sell"] = day
                trip["sells"].append(t["uid"])
                held -= t["shares"]
            else:
                held += t["shares"]
                if trip:
                    n = min(t["shares"], trip["sold"] - trip["rebought"])
                    trip["rebought"] += n
                    trip["buy_cost"] += n * t["price"]
                    trip["fees"] += trade_cost(t) * n / t["shares"]
                    trip["buys"].append(t["uid"])
                    if trip["rebought"] == trip["sold"]:
                        close_trip("closed", t["timestamp"][:10])
                        trip = None
        if trip:
            if c is not None and not c.empty and gap(trip["last_sell"], c.index[-1]) > REBUY_WINDOW:
                close_trip("reduction")
            else:
                close_trip("open")
    out.sort(key=lambda r: r["start"], reverse=True)
    return out
