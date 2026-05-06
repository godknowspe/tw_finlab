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

        # 處理未平倉 (Open positions)
        for b in buy_queue:
            if b["shares"] > 0:
                current_price = float(df.iloc[-1]['close']) if not df.empty else b["price"]
                today_date = pd.to_datetime(today)
                
                hold_df = df[(df.index >= b["date"])]
                if not hold_df.empty:
                    period_high = max(hold_df['high'].max(), b["price"], current_price)
                    period_low = min(hold_df['low'].min(), b["price"], current_price)
                else:
                    period_high = max(b["price"], current_price)
                    period_low = min(b["price"], current_price)
                    
                mae = (period_low - b["price"]) / b["price"] * 100
                mfe = (period_high - b["price"]) / b["price"] * 100
                
                spread = period_high - period_low
                if spread > 0:
                    efficiency = (current_price - b["price"]) / spread * 100
                    efficiency = max(0.0, min(100.0, efficiency))
                else:
                    efficiency = 0.0
                    
                unrealized = (current_price - b["price"]) * b["shares"]
                
                analysis_results.append({
                    "symbol": sym,
                    "buy_id": b["id"],
                    "sell_id": None, # 代表未平倉
                    "buy_date": b["date"].strftime('%Y-%m-%d'),
                    "sell_date": "-",
                    "buy_price": b["price"],
                    "sell_price": current_price,
                    "shares": b["shares"],
                    "mae_pct": round(mae, 2),
                    "mfe_pct": round(mfe, 2),
                    "efficiency_pct": round(efficiency, 2),
                    "realized": round(unrealized, 2), # 這裡借用 realized 欄位放未實現損益
                    "status": "OPEN"
                })

    for r in analysis_results:
        if "status" not in r:
            r["status"] = "CLOSED"

    return analysis_results


import json
import datetime
from src.data.models import get_engine

def calculate_historical_equity(trades, initial_cash_twd, initial_cash_usd, usd_twd_rate=32.5):
    if not trades:
        return {"tw": [], "us": [], "total": []}
        
    symbols = set(t["symbol"] for t in trades)
    db_syms = list(symbols) + [s + ".TW" for s in symbols if s.isdigit()]
    
    engine = get_engine()
    
    if len(db_syms) == 1:
        query = f"SELECT stock_id, date, close FROM daily_price WHERE stock_id = '{db_syms[0]}' AND interval='1d' ORDER BY date"
    else:
        query = f"SELECT stock_id, date, close FROM daily_price WHERE stock_id IN {tuple(db_syms)} AND interval='1d' ORDER BY date"
        
    df_prices = pd.read_sql(query, engine)
    
    trades_by_date = {}
    for t in trades:
        dt = datetime.datetime.fromisoformat(t["timestamp"]).date()
        if dt not in trades_by_date:
            trades_by_date[dt] = []
        trades_by_date[dt].append(t)
        
    start_date = min(trades_by_date.keys())
    end_date = datetime.date.today()
    
    prices_by_date = {}
    for _, row in df_prices.iterrows():
        d = pd.to_datetime(row['date']).date()
        if d not in prices_by_date:
            prices_by_date[d] = {}
        sym = row['stock_id'].replace('.TW', '') if row['stock_id'].endswith('.TW') else row['stock_id']
        prices_by_date[d][sym] = float(row['close'])
        
    # 我們不再依賴初始現金來計算絕對 Equity，而是採用累積投入本金來計算報酬率 (ROI %)
    cash_twd = 0.0
    cash_usd = 0.0
    
    # 紀錄我們總共投入了多少本金 (只增不減，或是每次入金時增加)
    # 為了簡化，只要買入時如果 cash 不夠，就是「入金」
    total_invested_twd = 0.0
    total_invested_usd = 0.0
    
    positions = {}
    
    result_tw = []
    result_us = []
    result_total = []
    
    last_known_prices = {}
    
    current_date = start_date
    while current_date <= end_date:
        if current_date in trades_by_date:
            # Sort trades by timestamp to ensure correct order
            day_trades = sorted(trades_by_date[current_date], key=lambda x: x["timestamp"])
            for t in day_trades:
                sym = t["symbol"]
                shares = float(t["shares"])
                price = float(t["price"])
                currency = t.get("currency", "TWD")
                
                if sym not in positions:
                    positions[sym] = {"shares": 0, "currency": currency}
                    
                if t["action"] == "BUY":
                    positions[sym]["shares"] += shares
                    cost = shares * price
                    if currency == "TWD":
                        if cash_twd < cost:
                            # 閒置現金不夠買，必須從外部入金
                            deposit = cost - cash_twd
                            total_invested_twd += deposit
                            cash_twd += deposit
                        cash_twd -= cost
                    else:
                        if cash_usd < cost:
                            deposit = cost - cash_usd
                            total_invested_usd += deposit
                            cash_usd += deposit
                        cash_usd -= cost
                elif t["action"] == "SELL":
                    sell_shares = min(shares, positions[sym]["shares"])
                    positions[sym]["shares"] -= sell_shares
                    if currency == "TWD":
                        cash_twd += sell_shares * price
                    else:
                        cash_usd += sell_shares * price
                        
        if current_date in prices_by_date:
            for sym, p in prices_by_date[current_date].items():
                last_known_prices[sym] = p
                
        if current_date.weekday() < 5:
            mv_twd = 0.0
            mv_usd = 0.0
            for sym, pos in positions.items():
                if pos["shares"] > 0:
                    # 如果當天還沒有任何歷史價格，就拿買進成本當作臨時價格
                    # 這裡為了簡單，我們可以直接拿 trades 裡的價格，但上面沒存。所以用 last_known_prices。
                    p = last_known_prices.get(sym, 0.0) 
                    if pos["currency"] == "TWD":
                        mv_twd += pos["shares"] * p
                    else:
                        mv_usd += pos["shares"] * p
                        
            eq_twd = cash_twd + mv_twd
            eq_usd = cash_usd + mv_usd
            eq_total = eq_twd + (eq_usd * float(usd_twd_rate))
            
            # 總投入成本
            base_twd = total_invested_twd
            base_usd = total_invested_usd
            base_total = base_twd + (base_usd * float(usd_twd_rate))
            
            # 計算 ROI (%)
            roi_twd = ((eq_twd / base_twd) - 1.0) * 100 if base_twd > 0 else 0.0
            roi_usd = ((eq_usd / base_usd) - 1.0) * 100 if base_usd > 0 else 0.0
            roi_total = ((eq_total / base_total) - 1.0) * 100 if base_total > 0 else 0.0
            
            date_str = current_date.strftime('%Y-%m-%d')
            result_tw.append({"time": date_str, "value": round(roi_twd, 2)})
            result_us.append({"time": date_str, "value": round(roi_usd, 2)})
            result_total.append({"time": date_str, "value": round(roi_total, 2)})
            
        current_date += datetime.timedelta(days=1)
        
    return {
        "tw": result_tw,
        "us": result_us,
        "total": result_total
    }
