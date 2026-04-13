import datetime
import re
from src.api.finmind_api import fetch_taiwan_stock_daily
from src.api.yfinance_api import fetch_us_stock_daily
from src.data.models import DailyPrice, get_engine, get_session, Base

def is_tw_stock(symbol):
    return bool(re.search(r'\d{4}', symbol)) or symbol.endswith('.TW') or symbol.endswith('.TWO')

def update_stock_data(stock_id: str, start_date: str, end_date: str):
    print(f"Fetching data for {stock_id} from {start_date} to {end_date}...")
    
    if is_tw_stock(stock_id):
        clean_id = stock_id.replace('.TW', '').replace('.TWO', '')
        df = fetch_taiwan_stock_daily(clean_id, start_date, end_date)
    else:
        df = fetch_us_stock_daily(stock_id, start_date, end_date)
    
    if df is None or df.empty:
        print(f"No data found for {stock_id} in the specified period.")
        return

    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session(engine)
    
    records_added = 0
    records_updated = 0
    
    for _, row in df.iterrows():
        existing_record = session.query(DailyPrice).filter_by(
            stock_id=stock_id, 
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
                stock_id=stock_id,
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
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    update_stock_data("2330", start_date, today)
    update_stock_data("AAPL", start_date, today)
