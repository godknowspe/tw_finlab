import datetime
from src.api.finmind_api import fetch_taiwan_stock_daily
from src.data.models import DailyPrice, get_engine, get_session, Base

def update_stock_data(stock_id: str, start_date: str, end_date: str):
    print(f"Fetching data for {stock_id} from {start_date} to {end_date}...")
    df = fetch_taiwan_stock_daily(stock_id, start_date, end_date)
    
    if df.empty:
        print(f"No data found for {stock_id} in the specified period.")
        return

    engine = get_engine()
    # 確保資料表存在
    Base.metadata.create_all(engine)
    
    session = get_session(engine)
    
    records_added = 0
    records_updated = 0
    
    for _, row in df.iterrows():
        # 檢查紀錄是否已存在
        existing_record = session.query(DailyPrice).filter_by(
            stock_id=str(row['stock_id']), 
            date=row['date']
        ).first()
        
        if existing_record:
            existing_record.open = row['open']
            existing_record.high = row['high']
            existing_record.low = row['low']
            existing_record.close = row['close']
            existing_record.volume = row['volume']
            records_updated += 1
        else:
            new_record = DailyPrice(
                stock_id=str(row['stock_id']),
                date=row['date'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
            session.add(new_record)
            records_added += 1
            
    session.commit()
    print(f"Data update complete for {stock_id}. Added: {records_added}, Updated: {records_updated}.")

if __name__ == "__main__":
    # 測試抓取台積電 (2330) 過去 30 天的資料
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    update_stock_data("2330", start_date, today)
