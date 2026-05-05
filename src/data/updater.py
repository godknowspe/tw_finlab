import datetime
import re
import pandas as pd
from src.api.finmind_api import fetch_taiwan_stock_daily
from src.api.yfinance_api import fetch_us_stock_daily
from src.data.models import DailyPrice, get_engine, get_session, Base

def is_tw_stock(symbol):
    return bool(re.search(r'\d{4}', symbol)) or symbol.endswith('.TW') or symbol.endswith('.TWO')

def update_stock_data(stock_id: str, start_date: str, end_date: str, interval: str = '1d'):
    print(f"Fetching data for {stock_id} ({interval}) from {start_date} to {end_date}...")
    
    if interval == '1d':
        if is_tw_stock(stock_id):
            clean_id = stock_id.replace('.TW', '').replace('.TWO', '')
            df = fetch_taiwan_stock_daily(clean_id, start_date, end_date)
        else:
            df = fetch_us_stock_daily(stock_id, start_date, end_date)
    else:
        # 分 K 暫時統一用 yfinance 抓取
        import yfinance as yf
        yf_sym = f"{stock_id}.TW" if stock_id.isdigit() else stock_id
        df = yf.download(yf_sym, start=start_date, end=end_date, interval=interval, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            df.reset_index(inplace=True)
            df.rename(columns={df.columns[0]: 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)

    if df is None or df.empty:
        print(f"No data found for {stock_id} in the specified period.")
        return

    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session(engine)
    
    records_added = 0
    records_updated = 0
    
    # === 異常資料過濾機制 ===
    from loguru import logger
    import math
    prev_close = None
    
    # 確保資料是按照時間排序的，才好比對前一根 K 線
    if 'date' in df.columns:
        df = df.sort_values(by='date')
        
    for _, row in df.iterrows():
        try:
            c = float(row['close'])
            o = float(row['open'])
            h = float(row['high'])
            l = float(row['low'])
            v = float(row['volume'])
        except (ValueError, TypeError):
            continue
            
        if math.isnan(c) or math.isnan(o):
            continue

        is_anomaly = False
        anomaly_reason = ""
        
        # 1. 振幅過濾防呆：與前一根 K 線對比
        # 這裡設定 15% 容錯 (台股極限 10%，加密貨幣不適用此限制，但您的標的是台美股)
        if prev_close is not None and prev_close > 0:
            pct_change = abs((c - prev_close) / prev_close)
            # 針對大盤或台股作嚴格過濾
            if pct_change > 0.15 and (stock_id.endswith('.TW') or stock_id == '^TWII' or is_tw_stock(stock_id)):
                is_anomaly = True
                anomaly_reason = f"Extreme price swing > 15% (Prev: {prev_close:.2f}, Cur: {c:.2f})"
        
        # 2. 針對 ^TWII 的 yfinance 假日幽靈 K 線：通常量為 0 且沒有波動，或者收盤價極端異常
        if stock_id == '^TWII' and v == 0 and o == h == l == c:
            is_anomaly = True
            anomaly_reason = f"Phantom data detected (Zero Volume, Flat price: {c})"
            
        if is_anomaly:
            logger.warning(f"🚨 [Anomaly Filter] Dropped {stock_id} at {row['date']}: {anomaly_reason}")
            continue
            
        prev_close = c
        # 注意：如果是分 K，row['date'] 會是 Timestamp 對象
        d = row['date']
        if hasattr(d, 'to_pydatetime'):
            d = d.to_pydatetime()
            
        # 移除任何微秒，避免對比失敗
        if hasattr(d, 'microsecond'):
            d = d.replace(microsecond=0)
            
        existing_record = session.query(DailyPrice).filter_by(
            stock_id=stock_id, 
            date=d,
            interval=interval
        ).first()
        
        if existing_record:
            existing_record.open = float(row['open'])
            existing_record.high = float(row['high'])
            existing_record.low = float(row['low'])
            existing_record.close = float(row['close'])
            existing_record.volume = float(row['volume'])
            records_updated += 1
        else:
            new_record = DailyPrice(
                stock_id=stock_id,
                interval=interval,
                date=d,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume'])
            )
            session.add(new_record)
            records_added += 1
            
    session.commit()
    print(f"Data update complete for {stock_id}. Added: {records_added}, Updated: {records_updated}.")

if __name__ == "__main__":
    import json
    import os
    
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime('%Y-%m-%d')
    
    # 讀取 server 的 app_state.json 來獲取自選股和持倉的標的
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web', 'app_state.json')
    symbols = set()
    
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                for w in state.get("watchlist", []):
                    symbols.add(w.get("symbol"))
                for t in state.get("trades", []):
                    symbols.add(t.get("symbol"))
        except Exception as e:
            print("Error loading app_state.json:", e)
    
    if not symbols:
        # 預設至少抓大盤和常見標的
        symbols.update(["^TWII", "^GSPC", "2330", "AAPL"])
        
    for sym in symbols:
        if sym:
            update_stock_data(sym, start_date, today)
