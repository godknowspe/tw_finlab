import datetime
import pandas as pd
from src.data.fetcher import get_stock_data_df

def calculate_trade_analysis(trades):
    # Group trades by symbol
    symbol_trades = {}
    for t in sorted(trades, key=lambda x: x["timestamp"]):
        sym = t["symbol"]
        if sym not in symbol_trades:
            symbol_trades[sym] = []
        symbol_trades[sym].append(t)
        
    analysis_results = []
    
    for sym, s_trades in symbol_trades.items():
        if not s_trades: continue
        
        # Fetch price data from the first trade date to today
        first_date = s_trades[0]["timestamp"][:10]
        today = datetime.date.today().strftime('%Y-%m-%d')
        df = get_stock_data_df(sym, first_date)
        
        if df.empty:
            continue
            
        # We will use simple FIFO to match buys and sells
        buy_queue = [] # list of dict: {id, price, shares, date}
        
        total_realized = 0.0
        
        for t in s_trades:
            t_date = t["timestamp"][:10]
            # Find closest date in df
            try:
                dt_idx = df.index[df.index >= pd.to_datetime(t_date)][0]
            except IndexError:
                dt_idx = df.index[-1]
                
            if t["action"] == "BUY":
                buy_queue.append({
                    "id": t["id"],
                    "price": t["price"],
                    "shares": t["shares"],
                    "date": pd.to_datetime(t_date)
                })
                
                # We can calculate MAE/MFE for this buy lot from buy date to today (or until it's sold out, but for simplicity, let's calculate until its last sold portion)
                # Actually, MAE/MFE is best evaluated when the trade is CLOSED.
                
            elif t["action"] == "SELL":
                shares_to_sell = t["shares"]
                sell_price = t["price"]
                sell_date = pd.to_datetime(t_date)
                
                while shares_to_sell > 0 and buy_queue:
                    b = buy_queue[0]
                    matched_shares = min(shares_to_sell, b["shares"])
                    
                    # hold period dataframe
                    hold_df = df[(df.index >= b["date"]) & (df.index <= sell_date)]
                    if not hold_df.empty:
                        period_high = max(hold_df['high'].max(), b["price"], sell_price)
                        period_low = min(hold_df['low'].min(), b["price"], sell_price)
                    else:
                        period_high = max(b["price"], sell_price)
                        period_low = min(b["price"], sell_price)
                        
                    mae = (period_low - b["price"]) / b["price"] * 100
                    mfe = (period_high - b["price"]) / b["price"] * 100
                    
                    spread = period_high - period_low
                    if spread > 0:
                        efficiency = (sell_price - b["price"]) / spread * 100
                        # Cap it between 0 and 100, though theoretically it shouldn't exceed now
                        efficiency = max(0.0, min(100.0, efficiency))
                    else:
                        efficiency = 0.0
                        
                    realized = (sell_price - b["price"]) * matched_shares
                    total_realized += realized
                    
                    analysis_results.append({
                        "symbol": sym,
                        "buy_id": b["id"],
                        "sell_id": t["id"],
                        "buy_date": b["date"].strftime('%Y-%m-%d'),
                        "sell_date": sell_date.strftime('%Y-%m-%d'),
                        "buy_price": b["price"],
                        "sell_price": sell_price,
                        "shares": matched_shares,
                        "mae_pct": round(mae, 2),
                        "mfe_pct": round(mfe, 2),
                        "efficiency_pct": round(efficiency, 2),
                        "realized": round(realized, 2)
                    })
                    
                    shares_to_sell -= matched_shares
                    b["shares"] -= matched_shares
                    if b["shares"] == 0:
                        buy_queue.pop(0)

    return analysis_results

