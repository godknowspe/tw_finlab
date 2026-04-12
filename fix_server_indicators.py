import re

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

new_kbars = """@app.get("/api/kbars/{stock_id}")
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
        
        df = df.where(pd.notnull(df), None)
        
        result = []
        for index, row in df.iterrows():
            result.append({
                "time": index.strftime('%Y-%m-%d'),
                "open": float(row['open']) if row['open'] is not None else None,
                "high": float(row['high']) if row['high'] is not None else None,
                "low": float(row['low']) if row['low'] is not None else None,
                "close": float(row['close']) if row['close'] is not None else None,
                "value": float(row['volume']) if row['volume'] is not None else None,
                "sma20": float(row['sma20']) if row['sma20'] is not None else None,
                "macd": float(row['macd']) if row['macd'] is not None else None,
                "signal": float(row['signal']) if row['signal'] is not None else None,
                "histogram": float(row['histogram']) if row['histogram'] is not None else None,
            })
        return result
    except Exception as e:
        return {"error": str(e)}"""

content = re.sub(r'@app\.get\("/api/kbars/\{stock_id\}"\).*?def get_kbars.*?return \{"error": str\(e\)\}', new_kbars, content, flags=re.DOTALL)

if "import pandas as pd" not in content:
    content = content.replace("import datetime", "import datetime\nimport pandas as pd")

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
