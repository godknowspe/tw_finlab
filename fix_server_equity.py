with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

equity_api = """
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
"""

content = content.replace("# WebSockets endpoint to simulate real-time ticks", equity_api)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
