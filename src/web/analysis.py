import pandas as pd

from src.domain.ledger import trade_sort_key


def _excursions(bars: pd.DataFrame, buy_price: float, exit_price: float):
    if bars.empty:
        hi, lo = max(buy_price, exit_price), min(buy_price, exit_price)
    else:
        hi = max(bars["high"].max(), buy_price, exit_price)
        lo = min(bars["low"].min(), buy_price, exit_price)
    mae = (lo - buy_price) / buy_price * 100
    mfe = (hi - buy_price) / buy_price * 100
    spread = hi - lo
    efficiency = max(0.0, min(100.0, (exit_price - buy_price) / spread * 100)) if spread > 0 else 0.0
    return round(mae, 2), round(mfe, 2), round(efficiency, 2)


def calculate_trade_analysis(trades, bars_for):
    """
    FIFO lot matching per symbol with MAE / MFE / exit efficiency per matched lot.
    This is per-lot trade review; account-level PnL uses the moving-average ledger instead,
    so realized figures here can differ from the portfolio view when lots have different costs.
    `bars_for(symbol)` returns that symbol's daily OHLC DataFrame.
    Fees are allocated pro rata to the matched shares.
    """
    by_symbol = {}
    for t in sorted(trades, key=trade_sort_key):
        by_symbol.setdefault(t["symbol"], []).append(t)

    results = []
    for sym, s_trades in by_symbol.items():
        df = bars_for(sym)
        queue = []
        for t in s_trades:
            day = pd.Timestamp(t["timestamp"][:10])
            fee_per_share = (t.get("fee", 0.0) + t.get("tax", 0.0)) / t["shares"]
            if t["action"] == "BUY":
                queue.append({"id": t["id"], "price": t["price"], "shares": t["shares"], "date": day, "cost_ps": fee_per_share})
                continue
            remaining = t["shares"]
            while remaining > 0 and queue:
                lot = queue[0]
                n = min(remaining, lot["shares"])
                hold = df[(df.index >= lot["date"]) & (df.index <= day)] if not df.empty else df
                mae, mfe, eff = _excursions(hold, lot["price"], t["price"])
                realized = (t["price"] - lot["price"] - lot["cost_ps"] - fee_per_share) * n
                results.append({
                    "symbol": sym, "buy_id": lot["id"], "sell_id": t["id"],
                    "buy_date": lot["date"].strftime('%Y-%m-%d'), "sell_date": day.strftime('%Y-%m-%d'),
                    "buy_price": lot["price"], "sell_price": t["price"], "shares": n,
                    "mae_pct": mae, "mfe_pct": mfe, "efficiency_pct": eff,
                    "realized": round(realized, 2), "status": "CLOSED",
                })
                remaining -= n
                lot["shares"] -= n
                if lot["shares"] == 0:
                    queue.pop(0)

        for lot in queue:
            if df.empty:
                current, price_known = lot["price"], False
            else:
                current, price_known = float(df.iloc[-1]["close"]), True
            hold = df[df.index >= lot["date"]] if not df.empty else df
            mae, mfe, eff = _excursions(hold, lot["price"], current)
            results.append({
                "symbol": sym, "buy_id": lot["id"], "sell_id": None,
                "buy_date": lot["date"].strftime('%Y-%m-%d'), "sell_date": "-",
                "buy_price": lot["price"], "sell_price": current, "shares": lot["shares"],
                "mae_pct": mae, "mfe_pct": mfe, "efficiency_pct": eff,
                "realized": round((current - lot["price"] - lot["cost_ps"]) * lot["shares"], 2),
                "status": "OPEN", "price_estimated": not price_known,
            })
    return results
