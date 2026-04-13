import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.data.fetcher import get_stock_data_df
import datetime
import pandas as pd
import os
import asyncio
import random

app = FastAPI(title="TW FinLab Quant Dashboard")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app_state = {
    "settings": {"take_profit_pct": 10.0, "stop_loss_pct": 5.0},
    "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False},
    "watchlist": [
        {"symbol": "2330", "name": "TSMC", "ref_price": 800.00, "market": "TW"},
        {"symbol": "2317", "name": "Hon Hai", "ref_price": 120.00, "market": "TW"},
        {"symbol": "AAPL", "name": "Apple Inc.", "ref_price": 170.00, "market": "US"}
    ],
    "cash": {
        "TWD": 10000000.0,
        "USD": 50000.0
    },
    "trades": [
        {"id": 1, "symbol": "2330", "action": "BUY", "shares": 2000, "price": 1550.00, "timestamp": "2026-02-01T10:00:00", "currency": "TWD"},
        {"id": 2, "symbol": "AAPL", "action": "BUY", "shares": 100, "price": 175.50, "timestamp": "2026-03-05T10:00:00", "currency": "USD"},
        {"id": 3, "symbol": "2330", "action": "SELL", "shares": 1000, "price": 1850.00, "timestamp": "2026-04-01T10:00:00", "currency": "TWD"}
    ]
}

class SettingsUpdate(BaseModel):
    take_profit_pct: float
    stop_loss_pct: float

class ActionRequest(BaseModel):
    action: str

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/kbars/{stock_id}")
def get_kbars(stock_id: str):
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    try:
        df = get_stock_data_df(stock_id, start_date)
        if df.empty:
            return []
            
        # 計算 SMA 20
        df['sma20'] = df['close'].rolling(window=20).mean()
        
        # 計算 MACD (Fast=12, Slow=26, Signal=9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal']
        
        # 計算 RSI 14
        delta = df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 計算 Bollinger Bands (20, 2)
        df['bb_mid'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_up'] = df['bb_mid'] + 2 * df['bb_std']
        df['bb_low'] = df['bb_mid'] - 2 * df['bb_std']
        
        
        # 計算 KD 指標 (9, 3, 3)
        min_low = df['low'].rolling(window=9, min_periods=1).min()
        max_high = df['high'].rolling(window=9, min_periods=1).max()
        rsv = (df['close'] - min_low) / (max_high - min_low) * 100
        rsv = rsv.fillna(50)
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        
        import math
        
        def safe_float(v):
            if pd.isna(v):
                return None
            return float(v)
        sym_trades = sorted([t for t in app_state["trades"] if t["symbol"] == stock_id], key=lambda x: x["timestamp"])
        trade_idx = 0
        shares = 0
        avg_cost = 0.0
        realized_pnl = 0.0

        result = []
        for index, row in df.iterrows():
            current_date = index.strftime('%Y-%m-%d')
            
            while trade_idx < len(sym_trades) and sym_trades[trade_idx]["timestamp"][:10] <= current_date:
                t = sym_trades[trade_idx]
                t_price = t["price"]
                t_shares = t["shares"]
                if t["action"] == "BUY":
                    total_cost = (shares * avg_cost) + (t_shares * t_price)
                    shares += t_shares
                    avg_cost = total_cost / shares if shares > 0 else 0.0
                elif t["action"] == "SELL":
                    sell_shares = min(t_shares, shares)
                    realized_pnl += (t_price - avg_cost) * sell_shares
                    shares -= sell_shares
                    if shares == 0:
                        avg_cost = 0.0
                trade_idx += 1
                
            close_price = safe_float(row['close'])
            unrealized_pnl = (close_price - avg_cost) * shares if close_price is not None else 0.0
            total_pnl = realized_pnl + unrealized_pnl
            
            result.append({
                "time": current_date,
                "open": safe_float(row['open']),
                "high": safe_float(row['high']),
                "low": safe_float(row['low']),
                "close": close_price,
                "value": safe_float(row['volume']),
                "sma20": safe_float(row['sma20']),
                "macd": safe_float(row['macd']),
                "signal": safe_float(row['signal']),
                "histogram": safe_float(row['histogram']),
                "rsi": safe_float(row.get('rsi')),
                "bb_up": safe_float(row.get('bb_up')),
                "bb_mid": safe_float(row.get('bb_mid')),
                "bb_low": safe_float(row.get('bb_low')),
                "k": safe_float(row.get('k')),
                "d": safe_float(row.get('d')),
                "total_pnl": float(total_pnl)
            })
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/portfolio")
def get_portfolio():
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 這裡未來可改為透過 yfinance 動態抓取 USD/TWD 匯率，這裡暫用固定值
    usd_twd_rate = 32.5
    
    latest_prices = {}
    
    enriched_watchlist = []
    for item in app_state["watchlist"]:
        sym = item["symbol"]
        if sym not in latest_prices:
            df = get_stock_data_df(sym, start_date)
            latest_prices[sym] = float(df.iloc[-1]['close']) if not df.empty else item["ref_price"]
            
        last_price = latest_prices[sym]
        chg = last_price - item["ref_price"]
        chg_pct = (chg / item["ref_price"]) * 100
        sign = "+" if chg >= 0 else ""
        
        enriched_watchlist.append({
            "symbol": sym,
            "name": item["name"],
            "last": round(last_price, 2),
            "chg_pct": f"{sign}{chg_pct:.2f}%",
            "ref_price": item["ref_price"],
            "market": item.get("market", "TW")
        })
        
    positions_map = {}
    current_cash_twd = app_state["cash"]["TWD"]
    current_cash_usd = app_state["cash"]["USD"]
    realized_pnl_twd = 0.0
    realized_pnl_usd = 0.0
    
    for trade in sorted(app_state["trades"], key=lambda x: x["timestamp"]):
        sym = trade["symbol"]
        shares = trade["shares"]
        price = trade["price"]
        currency = trade.get("currency", "TWD")
        market = "US" if currency == "USD" else "TW"
        
        if sym not in positions_map:
            positions_map[sym] = {"shares": 0, "avg_cost": 0.0, "currency": currency, "market": market}
            
        pos = positions_map[sym]
        
        if trade["action"] == "BUY":
            total_cost = (pos["shares"] * pos["avg_cost"]) + (shares * price)
            pos["shares"] += shares
            pos["avg_cost"] = total_cost / pos["shares"] if pos["shares"] > 0 else 0.0
            if currency == "TWD":
                current_cash_twd -= (shares * price)
            else:
                current_cash_usd -= (shares * price)
                
        elif trade["action"] == "SELL":
            sell_shares = min(shares, pos["shares"])
            trade_pnl = (price - pos["avg_cost"]) * sell_shares
            
            if currency == "TWD":
                realized_pnl_twd += trade_pnl
                current_cash_twd += (sell_shares * price)
            else:
                realized_pnl_usd += trade_pnl
                current_cash_usd += (sell_shares * price)
                
            pos["shares"] -= sell_shares
            if pos["shares"] == 0:
                pos["avg_cost"] = 0.0

    enriched_positions = []
    total_market_value_twd = 0.0
    total_market_value_usd = 0.0
    
    for sym, pos in positions_map.items():
        if pos["shares"] <= 0:
            continue
            
        if sym not in latest_prices:
            df = get_stock_data_df(sym, start_date)
            latest_prices[sym] = float(df.iloc[-1]['close']) if not df.empty else pos["avg_cost"]
            
        last_price = latest_prices[sym]
        market_value = last_price * pos["shares"]
        unrealized = market_value - (pos["avg_cost"] * pos["shares"])
        
        if pos["currency"] == "TWD":
            total_market_value_twd += market_value
        else:
            total_market_value_usd += market_value
            
        enriched_positions.append({
            "symbol": sym,
            "shares": pos["shares"],
            "avg_cost": round(pos["avg_cost"], 2),
            "unrealized": int(unrealized) if pos["currency"] == "TWD" else round(unrealized, 2),
            "currency": pos["currency"],
            "market": pos["market"],
            "market_value": int(market_value) if pos["currency"] == "TWD" else round(market_value, 2),
            "last_price": round(last_price, 2)
        })

    # 計算約當台幣總資產
    equiv_cash_twd = current_cash_twd + (current_cash_usd * usd_twd_rate)
    equiv_mv_twd = total_market_value_twd + (total_market_value_usd * usd_twd_rate)
    equiv_total_equity = equiv_cash_twd + equiv_mv_twd

    return {
        "watchlist": enriched_watchlist,
        "positions": enriched_positions,
        "summary": {
            "cash_twd": int(current_cash_twd),
            "cash_usd": round(current_cash_usd, 2),
            "market_value_twd": int(total_market_value_twd),
            "market_value_usd": round(total_market_value_usd, 2),
            "realized_pnl_twd": int(realized_pnl_twd),
            "realized_pnl_usd": round(realized_pnl_usd, 2),
            "equiv_total_equity_twd": int(equiv_total_equity),
            "usd_twd_rate": usd_twd_rate
        },
        "trades": sorted(app_state["trades"], key=lambda x: x["timestamp"], reverse=True),
        "agent_state": app_state["agent_state"],
        "settings": app_state["settings"]
    }

class WatchlistItem(BaseModel):
    symbol: str
    name: str
    ref_price: float
    market: str = "TW"

class TradeItem(BaseModel):
    symbol: str
    action: str
    shares: int
    price: float
    timestamp: str
    currency: str = "TWD"

@app.post("/api/watchlist")
def add_watchlist(item: WatchlistItem):
    if not any(w["symbol"] == item.symbol for w in app_state["watchlist"]):
        app_state["watchlist"].append({"symbol": item.symbol, "name": item.name, "ref_price": item.ref_price, "market": item.market})
    return {"status": "success", "message": f"{item.symbol} 已加入自選股！"}

@app.delete("/api/watchlist/{symbol}")
def del_watchlist(symbol: str):
    app_state["watchlist"] = [w for w in app_state["watchlist"] if w["symbol"] != symbol]
    return {"status": "success", "message": f"{symbol} 已從自選股移除！"}

@app.post("/api/trades")
def add_trade(item: TradeItem):
    if item.shares <= 0 or item.price <= 0:
        return {"status": "error", "message": "股數與價格必須大於 0"}
        
    new_id = max([t["id"] for t in app_state["trades"]] + [0]) + 1
    ts = item.timestamp
    if len(ts) == 16:
        ts += ":00"
        
    new_trade = {
        "id": new_id,
        "symbol": item.symbol.upper(),
        "action": item.action.upper(),
        "shares": item.shares,
        "price": item.price,
        "timestamp": ts,
        "currency": item.currency
    }
    app_state["trades"].append(new_trade)
    action_cht = "買進" if new_trade["action"] == "BUY" else "賣出"
    return {"status": "success", "message": f"成功新增交易：{action_cht} {item.symbol} {item.shares}股 @ {item.price}"}

@app.delete("/api/trades/{trade_id}")
def del_trade(trade_id: int):
    app_state["trades"] = [t for t in app_state["trades"] if t["id"] != trade_id]
    return {"status": "success", "message": f"已刪除交易紀錄 #{trade_id}！"}


@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    app_state["settings"]["take_profit_pct"] = settings.take_profit_pct
    app_state["settings"]["stop_loss_pct"] = settings.stop_loss_pct
    return {"status": "success", "message": "策略參數已更新！"}

@app.post("/api/action")
def perform_action(req: ActionRequest):
    action = req.action
    if action == "halt":
        app_state["agent_state"]["halted"] = True
        app_state["agent_state"]["phase"] = "HALTED"
        app_state["agent_state"]["exposure"] = "0%"
        return {"status": "success", "message": "🚨 緊急停止已觸發，部位已清空！"}
    elif action == "resume":
        app_state["agent_state"]["halted"] = False
        app_state["agent_state"]["phase"] = "Monitoring"
        return {"status": "success", "message": "✅ 系統已恢復自動交易。"}
    elif action == "execute":
        return {"status": "success", "message": "⚡️ 已強制發送執行訊號！"}
    return {"status": "error", "message": "未知的指令"}


@app.get("/api/equity")
def get_equity():
    import random
    today = datetime.date.today()
    result = []
    base_value = 5000000.0
    
    for i in range(120, -1, -1):
        dt = today - datetime.timedelta(days=i)
        # 避開週末
        if dt.weekday() >= 5:
            continue
            
        if not result:
            val = base_value
        else:
            val = result[-1]["value"] * random.uniform(0.995, 1.01)
        
        result.append({
            "time": dt.strftime('%Y-%m-%d'),
            "value": round(val, 2)
        })
    return result

# WebSockets endpoint to simulate real-time ticks

@app.websocket("/api/ws/quotes/{stock_id}")
async def websocket_quotes(websocket: WebSocket, stock_id: str):
    await websocket.accept()
    
    # 抓取最後一筆歷史資料作為基準，若無則給預設值
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    df = get_stock_data_df(stock_id, start_date)
    
    if not df.empty:
        last_row = df.iloc[-1]
        current_open = float(last_row['open'])
        current_high = float(last_row['high'])
        current_low = float(last_row['low'])
        current_close = float(last_row['close'])
        # 確保 WebSocket 吐出的日期與歷史資料最後一根 K 線完全吻合
        current_time = df.index[-1].strftime('%Y-%m-%d')
    else:
        current_open = current_high = current_low = current_close = 100.0
        current_time = today.strftime('%Y-%m-%d')

    try:
        while True:
            await asyncio.sleep(0.5) # 每 0.5 秒更新一次報價
            
            # 模擬股價隨機漫步 (跳動)
            tick_diff = random.uniform(-1.0, 1.0)
            # 台積電價格較大，波動給大一點
            if stock_id == "2330" or current_close > 500:
                tick_diff = random.uniform(-3.0, 3.0)
                
            current_close = round(current_close + tick_diff, 2)
            
            # 更新今日最高/最低
            if current_close > current_high:
                current_high = current_close
            if current_close < current_low:
                current_low = current_close

            payload = {
                "symbol": stock_id,
                "candle": {
                    "time": current_time,
                    "open": current_open,
                    "high": current_high,
                    "low": current_low,
                    "close": current_close
                }
            }
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for {stock_id}")

if __name__ == "__main__":
    uvicorn.run("src.web.server:app", host="0.0.0.0", port=8000, reload=True)

from src.web.analysis import calculate_trade_analysis

@app.get("/api/analysis")
def get_trade_analysis():
    results = calculate_trade_analysis(app_state["trades"])
    return results
