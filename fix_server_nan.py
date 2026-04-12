import re

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

old_loop = """        df = df.where(pd.notnull(df), None)
        
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
            })"""

new_loop = """        import math
        
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
            })"""

content = content.replace(old_loop, new_loop)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
