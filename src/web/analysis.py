"""
Per-buy review. Each BUY is judged on its own, on two separate questions:

Timing - was this a good moment to buy?
  Measured on the price path after the buy, independent of any later trade, so a top-up or a
  sale never changes how an earlier buy is scored.
  - ret_{N}d: close N trading days after the buy vs the buy price (N = 5, 20, 60)
  - mae / mfe: worst low / best high within the first WINDOW trading days, vs the buy price
  A window that has not fully elapsed is computed on the days available; `days_observed` says
  how many.

Outcome - what did this buy earn?
  From ledger lots: every sell is split across the open buys in proportion to their remaining
  shares (the same arithmetic as the moving-average cost on the Positions page), so the
  realised + unrealised PnL of all buys of a symbol sums exactly to that symbol's position.
  - realized: this buy's share of all sells; unrealized: its remaining shares at the last close
  - return_pct: (realized + unrealized) / cost of the buy

Context - how did it change the average cost?
  - avg_cost_before / avg_cost_after: the position's average cost just before and after this buy;
    a top-up below the average lowers it.
"""
import pandas as pd

from src.domain.ledger import Ledger, trade_sort_key

HORIZONS = (5, 20, 60)
WINDOW = 20


def _timing(bars: pd.DataFrame, buy_day: pd.Timestamp, price: float) -> dict:
    out = {f"ret_{n}d": None for n in HORIZONS}
    out.update(mae_pct=None, mfe_pct=None, days_observed=0)
    if bars.empty:
        return out
    after = bars[bars.index >= buy_day]
    if after.empty:
        return out
    # Day 0 is the buy session; day N is N sessions later.
    for n in HORIZONS:
        if len(after) > n:
            out[f"ret_{n}d"] = round((float(after["close"].iloc[n]) / price - 1) * 100, 2)
    window = after.iloc[: WINDOW + 1]
    out["mae_pct"] = round((min(float(window["low"].min()), price) / price - 1) * 100, 2)
    out["mfe_pct"] = round((max(float(window["high"].max()), price) / price - 1) * 100, 2)
    out["days_observed"] = len(window) - 1
    return out


def calculate_trade_analysis(trades, bars_for):
    """One row per BUY. `bars_for(symbol)` returns that symbol's daily OHLC DataFrame."""
    ledger = Ledger.empty()
    context = {}
    for t in sorted(trades, key=trade_sort_key):
        if t["action"] == "BUY":
            pos = ledger.positions.get(t["symbol"])
            before = pos.avg_cost if pos and pos.shares else None
            ledger.apply(t)
            context[t["uid"]] = (before, ledger.positions[t["symbol"]].avg_cost)
        else:
            ledger.apply(t)

    rows = []
    for sym, pos in ledger.positions.items():
        bars = bars_for(sym)
        last = float(bars["close"].iloc[-1]) if not bars.empty else None
        for lot in pos.lots:
            t = lot.trade
            buy_cost = t["shares"] * t["price"] + t.get("fee", 0.0) + t.get("tax", 0.0)
            unrealized = (last * lot.shares - lot.cost) if (last is not None and lot.shares > 0) else 0.0
            before, after = context[t["uid"]]
            rows.append({
                "uid": t["uid"],
                "symbol": sym,
                "currency": t["currency"],
                "buy_date": t["timestamp"][:10],
                "buy_price": t["price"],
                "shares": t["shares"],
                "remaining": round(lot.shares, 2),
                "status": "OPEN" if lot.shares > 1e-9 else "CLOSED",
                "avg_exit": round(lot.proceeds / lot.sold, 4) if lot.sold else None,
                "last_price": last,
                "price_estimated": last is None and lot.shares > 0,
                "realized": round(lot.realized_pnl, 2),
                "unrealized": round(unrealized, 2),
                "total_pnl": round(lot.realized_pnl + unrealized, 2),
                "return_pct": round((lot.realized_pnl + unrealized) / buy_cost * 100, 2),
                "avg_cost_before": round(before, 4) if before is not None else None,
                "avg_cost_after": round(after, 4),
                **_timing(bars, pd.Timestamp(t["timestamp"][:10]), t["price"]),
            })
    rows.sort(key=lambda r: (r["buy_date"], r["uid"]), reverse=True)
    return {"horizons": list(HORIZONS), "window": WINDOW, "buys": rows}
