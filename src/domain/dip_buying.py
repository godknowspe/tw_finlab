"""
Dip-buying backtest on a total-return (dividend-adjusted) price series.

Every strategy receives the same money: `monthly` on the first session of each month.
- invest_now: all of it is invested immediately
- dip: `monthly - reserve` is invested immediately and `reserve` goes to a cash pot; each time the
  price closes `trigger` below the reference (the highest close since the last add), up to
  `add_frac` x current holdings value (or the whole pot when add_frac is None) is taken from the
  pot and invested, and the reference resets to that price
- idle_cash: like dip but the pot is never used (shows what holding cash back costs)
The comparison isolates timing: same deposits, same dates, only when the money goes in differs.
"""
from typing import Optional

import pandas as pd


def _month_starts(px: pd.Series) -> set:
    firsts = px.groupby([px.index.year, px.index.month]).head(1)
    return set(firsts.index)


def simulate(px: pd.Series, monthly: float, reserve: float, trigger: Optional[float], add_frac: Optional[float]) -> dict:
    starts = _month_starts(px)
    shares = cash = deposited = 0.0
    ref = float(px.iloc[0])
    adds, curve = [], []
    for day, p in px.items():
        p = float(p)
        if day in starts:
            deposited += monthly
            invest_now = monthly if trigger is None and reserve == 0 else monthly - reserve
            shares += invest_now / p
            cash += monthly - invest_now
        if trigger is not None:
            ref = max(ref, p)
            if cash > 0 and p <= ref * (1 - trigger):
                amount = min(cash, add_frac * shares * p) if add_frac else cash
                shares += amount / p
                cash -= amount
                adds.append({"date": day.strftime("%Y-%m-%d"), "price": round(p, 2), "amount": round(amount)})
                ref = p
        curve.append({"time": day.strftime("%Y-%m-%d"), "value": round(shares * p + cash)})
    final = shares * float(px.iloc[-1]) + cash
    return {"final": round(final), "deposited": round(deposited), "cash_left": round(cash),
            "adds": adds, "curve": curve}


def compare(px: pd.Series, monthly: float, reserve: float, trigger: float, add_frac: Optional[float]) -> dict:
    px = px.dropna()
    base = simulate(px, monthly, 0.0, None, None)
    idle = simulate(px, monthly, reserve, None, None)
    dip = simulate(px, monthly, reserve, trigger, add_frac)
    peak_dd = float((px / px.cummax() - 1).min())
    years = (px.index[-1] - px.index[0]).days / 365.25
    return {
        "start": px.index[0].strftime("%Y-%m-%d"), "end": px.index[-1].strftime("%Y-%m-%d"),
        "cagr_pct": round(((float(px.iloc[-1]) / float(px.iloc[0])) ** (1 / years) - 1) * 100, 2),
        "max_drawdown_pct": round(peak_dd * 100, 2),
        "strategies": {
            "invest_now": base, "idle_cash": idle, "dip": dip,
        },
        "dip_vs_invest_now_pct": round((dip["final"] / base["final"] - 1) * 100, 2),
        "dip_vs_idle_cash_pct": round((dip["final"] / idle["final"] - 1) * 100, 2),
    }
