import re

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

# Make portfolio state dynamic
old_state = """app_state = {
    "settings": {"take_profit_pct": 10.0, "stop_loss_pct": 5.0},
    "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False}
}"""
new_state = """app_state = {
    "settings": {"take_profit_pct": 10.0, "stop_loss_pct": 5.0},
    "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False},
    "watchlist": [
        {"symbol": "2330", "name": "TSMC", "ref_price": 800.00},
        {"symbol": "2317", "name": "Hon Hai", "ref_price": 120.00},
        {"symbol": "2454", "name": "MediaTek", "ref_price": 1045.00}
    ],
    "positions": [
        {"symbol": "2330", "shares": 2000, "avg_cost": 1850.00},
        {"symbol": "2317", "shares": 5000, "avg_cost": 140.50}
    ]
}"""
content = content.replace(old_state, new_state)

# Replace get_portfolio to calculate current values dynamically
old_portfolio_api = """@app.get("/api/portfolio")
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
    }"""

new_portfolio_api = """@app.get("/api/portfolio")
def get_portfolio():
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    
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
            "last": last_price,
            "chg_pct": f"{sign}{chg_pct:.2f}%",
            "ref_price": item["ref_price"]
        })
        
    enriched_positions = []
    for pos in app_state["positions"]:
        sym = pos["symbol"]
        if sym not in latest_prices:
            df = get_stock_data_df(sym, start_date)
            latest_prices[sym] = float(df.iloc[-1]['close']) if not df.empty else pos["avg_cost"]
            
        last_price = latest_prices[sym]
        unrealized = (last_price - pos["avg_cost"]) * pos["shares"]
        
        enriched_positions.append({
            "symbol": sym,
            "shares": pos["shares"],
            "avg_cost": pos["avg_cost"],
            "unrealized": int(unrealized)
        })

    return {
        "watchlist": enriched_watchlist,
        "positions": enriched_positions,
        "agent_state": app_state["agent_state"],
        "settings": app_state["settings"]
    }

class WatchlistItem(BaseModel):
    symbol: str
    name: str
    ref_price: float

class PositionItem(BaseModel):
    symbol: str
    shares: int
    avg_cost: float

@app.post("/api/watchlist")
def add_watchlist(item: WatchlistItem):
    if not any(w["symbol"] == item.symbol for w in app_state["watchlist"]):
        app_state["watchlist"].append({"symbol": item.symbol, "name": item.name, "ref_price": item.ref_price})
    return {"status": "success", "message": f"{item.symbol} 已加入自選股！"}

@app.delete("/api/watchlist/{symbol}")
def del_watchlist(symbol: str):
    app_state["watchlist"] = [w for w in app_state["watchlist"] if w["symbol"] != symbol]
    return {"status": "success", "message": f"{symbol} 已從自選股移除！"}

@app.post("/api/positions")
def add_position(item: PositionItem):
    for p in app_state["positions"]:
        if p["symbol"] == item.symbol:
            p["shares"] = item.shares
            p["avg_cost"] = item.avg_cost
            return {"status": "success", "message": f"{item.symbol} 持股已更新！"}
    app_state["positions"].append({"symbol": item.symbol, "shares": item.shares, "avg_cost": item.avg_cost})
    return {"status": "success", "message": f"{item.symbol} 已加入持股明細！"}

@app.delete("/api/positions/{symbol}")
def del_position(symbol: str):
    app_state["positions"] = [p for p in app_state["positions"] if p["symbol"] != symbol]
    return {"status": "success", "message": f"{symbol} 持股已刪除！"}
"""
content = content.replace(old_portfolio_api, new_portfolio_api)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
