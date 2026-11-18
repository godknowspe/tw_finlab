"""Single-instrument, self-financed backtest with next-open execution. No look-ahead by design.

Per session t, in this order:
  1. carry the position from close(t-1) to open(t): the open's gap is earned or suffered by the
     shares held, cash accrues interest by calendar days, and a dividend with ex-date t is paid
     to whoever held the shares at close(t-1) (a buyer filling at open(t) does not get it)
  2. trade at open(t) toward the target weight decided from information up to close(t-1)
  3. carry from open(t) to close(t) and mark equity

`target` holds the weight decided AFTER the close of its own date, so it is applied one session
later. Fractional shares are used (a research idealisation, stated in the report). Cash never
goes negative and no leverage is allowed. Equity starts at 1.0 on `start`; the part of the data
before `start` is warm-up for the signals only.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Costs:
    fee: float = 0.001425          # brokerage, charged on both sides
    tax: float = 0.001             # ETF transaction tax, sells only
    slippage: float = 0.0005       # per side, as an adverse move of the fill price
    cash_rate: float = 0.0         # annual, on idle cash, by calendar days


def run(bars: pd.DataFrame, target: pd.Series, costs: Costs, start, rebalance_band: float = 0.0,
        rebalance_every: Optional[int] = None) -> dict:
    """`bars`: open/high/low/close/dividend per session. `target`: desired weight in [0, 1] per
    date, known at that date's close. `rebalance_band`: only trade when |weight - target| exceeds
    it (0 = always trade to the target); opening from zero and going to zero ignore it. `rebalance_every`: only consider trading on every n-th
    session after `start` (entries and exits to/from zero are always allowed)."""
    bars = bars.loc[bars.index >= pd.Timestamp(start)]
    tgt = target.reindex(bars.index).ffill().fillna(0.0).clip(0.0, 1.0)
    shares, cash = 0.0, 1.0
    prev_close, prev_day = None, None
    eq, wt, cs, fills = [], [], [], []
    costs_paid = 0.0
    decided = 0.0                                               # weight decided at the previous close
    for n, (day, b) in enumerate(bars.iterrows()):
        if prev_close is not None:
            if costs.cash_rate:
                cash *= 1 + costs.cash_rate / 365 * (day - prev_day).days
            cash += shares * float(b["dividend"])               # holders at the previous close
            # (price gap is earned by `shares` implicitly: value = shares * open below)
            val = shares * b["open"] + cash
            weight = shares * b["open"] / val if val > 0 else 0.0
            want = decided
            due = rebalance_every is None or n % rebalance_every == 0 or want == 0.0 or shares == 0.0
            entering_or_exiting = (shares == 0.0 and want > 0.0) or want == 0.0
            if due and abs(weight - want) > (1e-12 if entering_or_exiting else max(rebalance_band, 1e-12)):
                goal = want * val                               # value to hold in shares
                diff = goal - shares * b["open"]
                if diff > 0:                                    # buy: pay slippage and fee, never spend more cash than exists
                    px = b["open"] * (1 + costs.slippage)
                    spend = min(diff, cash / (1 + costs.fee))
                    qty = spend / px
                    fee = spend * costs.fee
                    shares += qty
                    cash -= spend + fee
                    costs_paid += fee + qty * (px - b["open"])
                    fills.append({"date": day, "side": "BUY", "price": float(px), "qty": float(qty), "cost": float(fee + qty * (px - b["open"]))})
                elif diff < 0:
                    px = b["open"] * (1 - costs.slippage)
                    qty = min(shares, -diff / b["open"])
                    gross = qty * px
                    fee, tax = gross * costs.fee, gross * costs.tax
                    shares -= qty
                    cash += gross - fee - tax
                    costs_paid += fee + tax + qty * (b["open"] - px)
                    fills.append({"date": day, "side": "SELL", "price": float(px), "qty": float(qty), "cost": float(fee + tax + qty * (b["open"] - px))})
        total = shares * b["close"] + cash
        eq.append(total)
        wt.append(shares * b["close"] / total if total > 0 else 0.0)
        cs.append(cash)
        decided = float(tgt.loc[day])                           # takes effect at the next open
        prev_close, prev_day = b["close"], day
    idx = bars.index
    return {"equity": pd.Series(eq, index=idx), "weight": pd.Series(wt, index=idx), "cash": pd.Series(cs, index=idx),
            "fills": fills, "costs_paid": float(costs_paid)}
