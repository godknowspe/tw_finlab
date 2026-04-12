import re

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

old_trade_item = """class TradeItem(BaseModel):
    symbol: str
    action: str
    shares: int
    price: float"""
new_trade_item = """class TradeItem(BaseModel):
    symbol: str
    action: str
    shares: int
    price: float
    timestamp: str"""
content = content.replace(old_trade_item, new_trade_item)

old_add_trade = """    new_trade = {
        "id": new_id,
        "symbol": item.symbol.upper(),
        "action": item.action.upper(),
        "shares": item.shares,
        "price": item.price,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }"""
new_add_trade = """    ts = item.timestamp
    if len(ts) == 16:
        ts += ":00"
        
    new_trade = {
        "id": new_id,
        "symbol": item.symbol.upper(),
        "action": item.action.upper(),
        "shares": item.shares,
        "price": item.price,
        "timestamp": ts
    }"""
content = content.replace(old_add_trade, new_add_trade)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
