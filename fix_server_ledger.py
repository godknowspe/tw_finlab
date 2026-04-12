with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

old_state = """app_state = {
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

new_state = """app_state = {
    "settings": {"take_profit_pct": 10.0, "stop_loss_pct": 5.0},
    "agent_state": {"target": "2330.TW", "phase": "Accumulation", "exposure": "65%", "halted": False},
    "watchlist": [
        {"symbol": "2330", "name": "TSMC", "ref_price": 800.00},
        {"symbol": "2317", "name": "Hon Hai", "ref_price": 120.00},
        {"symbol": "2454", "name": "MediaTek", "ref_price": 1045.00}
    ],
    "cash": 10000000.0, # 初始千萬資金
    "trades": [
        {"id": 1, "symbol": "2330", "action": "BUY", "shares": 2000, "price": 1550.00, "timestamp": "2026-02-01T10:00:00"},
        {"id": 2, "symbol": "2317", "action": "BUY", "shares": 5000, "price": 140.50, "timestamp": "2026-03-05T10:00:00"},
        {"id": 3, "symbol": "2330", "action": "BUY", "shares": 1000, "price": 1600.00, "timestamp": "2026-03-10T10:00:00"},
        {"id": 4, "symbol": "2330", "action": "SELL", "shares": 1000, "price": 1850.00, "timestamp": "2026-04-01T10:00:00"}
    ]
}"""

content = content.replace(old_state, new_state)

old_port_func = """    enriched_positions = []
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
    }"""

new_port_func = """    positions_map = {}
    current_cash = app_state["cash"]
    realized_pnl = 0.0
    
    for trade in sorted(app_state["trades"], key=lambda x: x["timestamp"]):
        sym = trade["symbol"]
        shares = trade["shares"]
        price = trade["price"]
        
        if sym not in positions_map:
            positions_map[sym] = {"shares": 0, "avg_cost": 0.0}
            
        pos = positions_map[sym]
        
        if trade["action"] == "BUY":
            total_cost = (pos["shares"] * pos["avg_cost"]) + (shares * price)
            pos["shares"] += shares
            pos["avg_cost"] = total_cost / pos["shares"] if pos["shares"] > 0 else 0.0
            current_cash -= (shares * price)
        elif trade["action"] == "SELL":
            sell_shares = min(shares, pos["shares"])
            trade_pnl = (price - pos["avg_cost"]) * sell_shares
            realized_pnl += trade_pnl
            pos["shares"] -= sell_shares
            current_cash += (sell_shares * price)
            
            if pos["shares"] == 0:
                pos["avg_cost"] = 0.0

    enriched_positions = []
    total_market_value = 0.0
    
    for sym, pos in positions_map.items():
        if pos["shares"] <= 0:
            continue
            
        if sym not in latest_prices:
            df = get_stock_data_df(sym, start_date)
            latest_prices[sym] = float(df.iloc[-1]['close']) if not df.empty else pos["avg_cost"]
            
        last_price = latest_prices[sym]
        market_value = last_price * pos["shares"]
        total_market_value += market_value
        unrealized = market_value - (pos["avg_cost"] * pos["shares"])
        
        enriched_positions.append({
            "symbol": sym,
            "shares": pos["shares"],
            "avg_cost": round(pos["avg_cost"], 2),
            "unrealized": int(unrealized)
        })

    return {
        "watchlist": enriched_watchlist,
        "positions": enriched_positions,
        "summary": {
            "cash": int(current_cash),
            "market_value": int(total_market_value),
            "total_equity": int(current_cash + total_market_value),
            "realized_pnl": int(realized_pnl)
        },
        "trades": sorted(app_state["trades"], key=lambda x: x["timestamp"], reverse=True),
        "agent_state": app_state["agent_state"],
        "settings": app_state["settings"]
    }"""

content = content.replace(old_port_func, new_port_func)

old_pos_endpoints = """class PositionItem(BaseModel):
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
    return {"status": "success", "message": f"{symbol} 持股已刪除！"}"""

new_pos_endpoints = """class TradeItem(BaseModel):
    symbol: str
    action: str
    shares: int
    price: float

@app.post("/api/watchlist")
def add_watchlist(item: WatchlistItem):
    if not any(w["symbol"] == item.symbol for w in app_state["watchlist"]):
        app_state["watchlist"].append({"symbol": item.symbol, "name": item.name, "ref_price": item.ref_price})
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
    new_trade = {
        "id": new_id,
        "symbol": item.symbol.upper(),
        "action": item.action.upper(),
        "shares": item.shares,
        "price": item.price,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }
    app_state["trades"].append(new_trade)
    action_cht = "買進" if new_trade["action"] == "BUY" else "賣出"
    return {"status": "success", "message": f"成功新增交易：{action_cht} {item.symbol} {item.shares}股 @ {item.price}"}

@app.delete("/api/trades/{trade_id}")
def del_trade(trade_id: int):
    app_state["trades"] = [t for t in app_state["trades"] if t["id"] != trade_id]
    return {"status": "success", "message": f"已刪除交易紀錄 #{trade_id}！"}"""

content = content.replace(old_pos_endpoints, new_pos_endpoints)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
