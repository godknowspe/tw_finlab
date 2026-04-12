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
    "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False}
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
        
        import math
        
        def safe_float(v):
            if pd.isna(v):
                return None
            return float(v)

        result = []
        for index, row in df.iterrows():
            result.append({
                "time": index.strftime('%Y-%m-%d'),
                "open": safe_float(row['open']),
                "high": safe_float(row['high']),
                "low": safe_float(row['low']),
                "close": safe_float(row['close']),
                "value": safe_float(row['volume']),
                "sma20": safe_float(row['sma20']),
                "macd": safe_float(row['macd']),
                "signal": safe_float(row['signal']),
                "histogram": safe_float(row['histogram']),
            })
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/portfolio")
def get_portfolio():
    return {
        "watchlist": [
            {"symbol": "2330", "name": "TSMC", "last": 805.00, "chg_pct": "+0.69%", "ref_price": 800.00},
            {"symbol": "2317", "name": "Hon Hai", "last": 118.50, "chg_pct": "-1.25%", "ref_price": 120.00},
            {"symbol": "2454", "name": "MediaTek", "last": 1050.00, "chg_pct": "+0.48%", "ref_price": 1045.00}
        ],
        "positions": [
            {"symbol": "2330", "shares": 2000, "avg_cost": 1850.00, "unrealized": 300000},
            {"symbol": "2317", "shares": 5000, "avg_cost": 140.50, "unrealized": -100000}
        ],
        "agent_state": app_state["agent_state"],
        "settings": app_state["settings"]
    }

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
