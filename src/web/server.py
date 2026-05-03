import json
import os
import uvicorn
import yfinance as yf
import datetime
import pandas as pd
import numpy as np
import asyncio
import copy
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Fix yfinance file descriptor leak
try:
    import tempfile
    yf_cache_dir = os.path.join(tempfile.gettempdir(), "yfinance_cache")
    if not os.path.exists(yf_cache_dir):
        os.makedirs(yf_cache_dir, exist_ok=True)
    yf.set_tz_cache_location(yf_cache_dir)
except Exception:
    pass

from src.data.models import get_engine, get_session, Base, DailyPrice, AppConfig
from src.services.config_service import ConfigService
from src.services.data_service import DataService
from src.services.indicator_service import IndicatorService
from src.services.portfolio_service import PortfolioService
from src.providers.factory import ProviderFactory

app = FastAPI(title="TW FinLab Quant Dashboard")

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_state.json")
static_dir = os.path.join(os.path.dirname(__file__), "static")
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))

if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# --- Dependency ---
def get_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    db = get_session(engine)
    try:
        yield db
    finally:
        db.close()

# --- State Management ---
def load_app_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("LOAD ERROR:", e)
    return {
        "settings": {"take_profit_pct": 10.0, "stop_loss_pct": 5.0},
        "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False},
        "watchlist": [
            {"symbol": "2330", "name": "TSMC", "ref_price": 800.00, "market": "TW"},
            {"symbol": "2317", "name": "Hon Hai", "ref_price": 120.00, "market": "TW"},
            {"symbol": "AAPL", "name": "Apple Inc.", "ref_price": 170.00, "market": "US"}
        ],
        "cash": {"TWD": 1000000.0, "USD": 50000.0},
        "trades": []
    }

def save_app_state(state):
    tmp_path = STATE_FILE + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, STATE_FILE)
    except Exception as e:
        print(f"SAVE ERROR: {e}")

app_state = load_app_state()

# --- Pydantic Models ---
class ConfigUpdate(BaseModel):
    kline: str
    realtime: str
    shioaji_api_key: str = ""
    shioaji_api_secret: str = ""
    shioaji_person_id: str = ""
    shioaji_password: str = ""

class SettingsUpdate(BaseModel):
    take_profit_pct: float
    stop_loss_pct: float

class WatchlistItem(BaseModel):
    symbol: str
    name: str = ""
    ref_price: float = 0.0
    market: str = "TW"

class TradeItem(BaseModel):
    symbol: str
    action: str
    shares: int
    price: float
    timestamp: str
    currency: str = "TWD"

class ActionRequest(BaseModel):
    action: str

# --- Routes ---

@app.get("/")
async def root(request: Request):
    if os.path.exists(os.path.join(frontend_dist, "index.html")):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile = any(mobile_os in user_agent for mobile_os in ["android", "iphone", "ipad", "mobile"])
    if is_mobile and os.path.exists(os.path.join(static_dir, "mobile.html")):
        return FileResponse(os.path.join(static_dir, "mobile.html"))
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/config")
def get_config(db: Session = Depends(get_db)):
    config_service = ConfigService(db)
    all_configs = config_service.get_all_configs()
    return {k.replace("ds_", ""): v for k, v in all_configs.items() if k.startswith("ds_")}

@app.post("/api/config")
def update_config(config: ConfigUpdate, db: Session = Depends(get_db)):
    config_service = ConfigService(db)
    data = config.dict()
    for k, v in data.items():
        config_service.set_config(f"ds_{k}", v)
    return {"status": "success", "message": "Configuration updated in database."}

@app.get("/api/kbars/{stock_id}")
def get_kbars(stock_id: str, interval: str = "1d", db: Session = Depends(get_db)):
    data_service = DataService(db)
    config_service = ConfigService(db)
    
    df = data_service.get_stock_data_df(stock_id, interval=interval)
    
    now = datetime.datetime.now()
    need_fetch = False
    is_min_inv = interval in ['15m', '30m', '60m', '1h']
    
    if df.empty:
        need_fetch = True
    else:
        if is_min_inv and len(df) < 500:
            need_fetch = True
        elif not is_min_inv and len(df) < 100:
            need_fetch = True
        else:
            last_date = df.index[-1]
            diff_days = (now - last_date).days
            if interval == '1d' and diff_days >= 1: need_fetch = True
            elif interval in ['1w', '1wk'] and diff_days >= 7: need_fetch = True
            elif interval in ['1m', '1mo'] and diff_days >= 30: need_fetch = True
            elif is_min_inv and (now - last_date).total_seconds() > 3600: need_fetch = True

    if need_fetch:
        source = config_service.get_config("ds_kline", "yfinance")
        creds = {
            "api_key": config_service.get_config("ds_shioaji_api_key", ""),
            "api_secret": config_service.get_config("ds_shioaji_api_secret", "")
        }
        try:
            provider = ProviderFactory.get_provider(source, **creds)
            if interval == '1d':
                start_date = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime('%Y-%m-%d')
            elif interval in ['1w', '1wk', '1m', '1mo']:
                start_date = (datetime.date.today() - datetime.timedelta(days=365*20)).strftime('%Y-%m-%d')
            else:
                start_date = (datetime.date.today() - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
                
            end_date = datetime.date.today().strftime('%Y-%m-%d')
            new_df = provider.fetch_kbars(stock_id, start_date, end_date, interval)
            
            if not new_df.empty:
                data_service.save_stock_data(new_df, stock_id, interval)
                df = data_service.get_stock_data_df(stock_id, interval=interval)
        except Exception as e:
            print(f"Fetch Error: {e}")
            if source != "yfinance":
                try:
                    provider = ProviderFactory.get_provider("yfinance")
                    new_df = provider.fetch_kbars(stock_id, start_date, end_date, interval)
                    if not new_df.empty:
                        data_service.save_stock_data(new_df, stock_id, interval)
                        df = data_service.get_stock_data_df(stock_id, interval=interval)
                except: pass

    if df.empty: return []

    df = IndicatorService.add_all_indicators(df)
    
    # --- PnL Calculation ---
    sym_trades = sorted([t for t in app_state["trades"] if t["symbol"] == stock_id], key=lambda x: x["timestamp"])
    trade_idx, shares, avg_cost, realized_pnl = 0, 0, 0.0, 0.0
    
    result = []
    is_minute_interval = interval in ['15m', '30m', '60m', '1h']

    for index, row in df.iterrows():
        current_date_str = index.strftime('%Y-%m-%d')
        while trade_idx < len(sym_trades) and sym_trades[trade_idx]["timestamp"][:10] <= current_date_str:
            t = sym_trades[trade_idx]
            t_price, t_shares = float(t["price"]), int(t["shares"])
            if t["action"] == "BUY":
                avg_cost = ((shares * avg_cost) + (t_shares * t_price)) / (shares + t_shares)
                shares += t_shares
            elif t["action"] == "SELL":
                sell_shares = min(t_shares, shares)
                realized_pnl += (t_price - avg_cost) * sell_shares
                shares -= sell_shares
                if shares == 0: avg_cost = 0.0
            trade_idx += 1
            
        close_price = float(row['close'])
        unrealized_pnl = (close_price - avg_cost) * shares if shares > 0 else 0.0
        total_pnl = realized_pnl + unrealized_pnl if (shares > 0 or realized_pnl != 0) else None
        pnl_pct = ((close_price - avg_cost) / avg_cost * 100) if (shares > 0 and avg_cost > 0) else None

        def f(val):
            return float(val) if not (pd.isna(val) or np.isinf(val)) else None

        result.append({
            "time": int(index.timestamp()) if is_minute_interval else index.strftime('%Y-%m-%d'),
            "open": f(row['open']), "high": f(row['high']), "low": f(row['low']), "close": f(row['close']),
            "value": f(row['volume']),
            "sma5": f(row.get('sma5')), "sma10": f(row.get('sma10')), "sma20": f(row.get('sma20')),
            "macd": f(row.get('macd')), "signal": f(row.get('signal')), "histogram": f(row.get('histogram')),
            "rsi": f(row.get('rsi')), "bb_up": f(row.get('bb_up')), "bb_mid": f(row.get('bb_mid')), "bb_low": f(row.get('bb_low')),
            "k": f(row.get('k')), "d": f(row.get('d')),
            "total_pnl": f(total_pnl), "pnl_pct": f(pnl_pct)
        })
    return result

@app.get("/api/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    portfolio_service = PortfolioService(app_state["cash"]["TWD"], app_state["cash"]["USD"])
    port_data = portfolio_service.calculate_positions(app_state["trades"])
    symbols = list(port_data["positions"].keys()) + [w["symbol"] for w in app_state["watchlist"]]
    latest_prices = {}
    if symbols:
        try:
            yf_syms = []
            for s in set(symbols):
                if s.startswith("^") or "." in s: yf_syms.append(s)
                elif s.isdigit(): yf_syms.append(f"{s}.TW")
                else: yf_syms.append(s)
            data = yf.download(yf_syms, period="5d", progress=False)
            if not data.empty:
                for s in set(symbols):
                    if s.startswith("^") or "." in s: yf_s = s
                    elif s.isdigit(): yf_s = f"{s}.TW"
                    else: yf_s = s
                    try:
                        if len(yf_syms) > 1:
                            v = data['Close'][yf_s].dropna()
                            if not v.empty: latest_prices[s] = float(v.iloc[-1])
                        else:
                            v = data['Close'].dropna()
                            if not v.empty: latest_prices[s] = float(v.iloc[-1])
                    except: pass
        except: pass
    enriched = portfolio_service.enrich_portfolio(port_data, latest_prices)
    enriched_watchlist = []
    for item in app_state["watchlist"]:
        sym = item["symbol"]
        last = latest_prices.get(sym, item.get("ref_price", 0))
        last = float(last) if not (pd.isna(last) or np.isinf(last)) else 0.0
        ref_price = float(item.get("ref_price", 0))
        ref_price = ref_price if not (pd.isna(ref_price) or np.isinf(ref_price)) else 0.0
        chg_pct = (last - ref_price) / ref_price * 100 if ref_price != 0 else 0
        enriched_watchlist.append({
            "symbol": sym, "name": item.get("name", sym), "ref_price": ref_price,
            "market": item.get("market", "TW"), "last": round(last, 2),
            "chg_pct": f"{'+' if chg_pct >= 0 else ''}{chg_pct:.2f}%"
        })
    return {
        "watchlist": enriched_watchlist, "positions": enriched["positions"],
        "summary": { **enriched["summary"], "cash_twd": port_data["cash"]["TWD"], "cash_usd": port_data["cash"]["USD"] },
        "trades": sorted(app_state["trades"], key=lambda x: x["timestamp"], reverse=True),
        "settings": app_state["settings"], "agent_state": app_state["agent_state"]
    }

@app.post("/api/watchlist")
def add_watchlist(item: WatchlistItem):
    if not any(w["symbol"] == item.symbol for w in app_state["watchlist"]):
        app_state["watchlist"].append(item.dict())
        save_app_state(app_state)
    return {"status": "success"}

@app.delete("/api/watchlist/{symbol}")
def del_watchlist(symbol: str):
    app_state["watchlist"] = [w for w in app_state["watchlist"] if w["symbol"] != symbol]
    save_app_state(app_state)
    return {"status": "success"}

@app.post("/api/trades")
def add_trade(item: TradeItem):
    new_id = max([t["id"] for t in app_state["trades"]] + [0]) + 1
    trade = item.dict()
    trade["id"] = new_id
    app_state["trades"].append(trade)
    save_app_state(app_state)
    return {"status": "success"}

@app.delete("/api/trades/{trade_id}")
def del_trade(trade_id: int):
    app_state["trades"] = [t for t in app_state["trades"] if t["id"] != trade_id]
    save_app_state(app_state)
    return {"status": "success"}


from src.engine.backtest import BacktestEngine
from src.engine.strategies import STRATEGIES
from src.web.analysis import calculate_trade_analysis
import random

@app.get("/api/backtest/{symbol}")
def run_backtest(symbol: str, strategies: str = "RSI", interval: str = "1d", db: Session = Depends(get_db)):
    data_service = DataService(db)
    
    # 取得歷史資料
    df = data_service.get_stock_data_df(symbol, interval=interval)
    
    if df.empty:
        return {"error": "No data available for backtest"}
        
    df['stock_id'] = symbol
    selected_strategies = strategies.split(",")
    results_map = {}

    for s_name in selected_strategies:
        if s_name in STRATEGIES:
            engine = BacktestEngine(df)
            res = engine.run(STRATEGIES[s_name])
            
            is_minute_interval = interval in ['15m', '30m', '60m', '1h']
            
            equity_curve = res['equity_curve'].copy()
            chart_data = []
            for _, row in equity_curve.iterrows():
                ts = row['date']
                if is_minute_interval:
                    chart_time = int(ts.timestamp()) if hasattr(ts, 'timestamp') else int(pd.to_datetime(ts).timestamp())
                else:
                    chart_time = ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10]
                
                chart_data.append({
                    "time": chart_time,
                    "value": round(row['total_equity'], 2)
                })
            
            trade_markers = []
            for t in res.get('trades', []):
                ts = t['date']
                if is_minute_interval:
                    chart_time = int(ts.timestamp()) if hasattr(ts, 'timestamp') else int(pd.to_datetime(ts).timestamp())
                else:
                    chart_time = ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10]
                    
                trade_markers.append({
                    "time": chart_time,
                    "side": t['side'],
                    "price": t['price'],
                    "size": t['size']
                })

            results_map[s_name] = {
                "total_return_pct": round(res['total_return'] * 100, 2),
                "max_drawdown_pct": round(res['max_drawdown'] * 100, 2),
                "final_equity": int(res['final_equity']),
                "chart_data": chart_data,
                "trades": trade_markers
            }
        
    return results_map

@app.get("/api/equity")
def get_equity():
    random.seed(42)
    today = datetime.date.today()
    result = []
    base_value = 1000000.0
    
    for i in range(3650, -1, -1):
        dt = today - datetime.timedelta(days=i)
        if dt.weekday() >= 5:
            continue
            
        if not result:
            val = base_value
        else:
            val = result[-1]["value"] * random.uniform(0.992, 1.009)
        
        result.append({
            "time": dt.strftime('%Y-%m-%d'),
            "value": round(val, 2)
        })
    return result

@app.get("/api/analysis")
def get_trade_analysis():
    results = calculate_trade_analysis(app_state["trades"])
    return results

@app.websocket("/api/ws/watchlist")
async def websocket_watchlist(websocket: WebSocket):
    await websocket.accept()
    last_prices = {}
    try:
        while True:
            symbols = [w["symbol"] for w in app_state["watchlist"]]
            if symbols:
                yf_syms = []
                for s in symbols:
                    if s.startswith("^") or "." in s: yf_syms.append(s)
                    elif s.isdigit(): yf_syms.append(f"{s}.TW")
                    else: yf_syms.append(s)
                data = await asyncio.to_thread(yf.download, yf_syms, period="5d", progress=False)
                updates = []
                if not data.empty:
                    for s in symbols:
                        if s.startswith("^") or "." in s: yf_s = s
                        elif s.isdigit(): yf_s = f"{s}.TW"
                        else: yf_s = s
                        try:
                            v = data['Close'][yf_s].dropna() if len(yf_syms) > 1 else data['Close'].dropna()
                            if not v.empty:
                                price = float(v.iloc[-1])
                                if price != last_prices.get(s):
                                    last_prices[s] = price
                                    updates.append({"symbol": s, "price": round(price, 2), "time": datetime.datetime.now().strftime('%H:%M:%S')})
                        except: pass
                if updates: await websocket.send_json({"type": "updates", "data": updates})
            await asyncio.sleep(30)
    except Exception: pass

if __name__ == "__main__":
    uvicorn.run("src.web.server:app", host="0.0.0.0", port=8000, reload=True)
