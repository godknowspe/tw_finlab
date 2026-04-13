import yfinance as yf
import pandas as pd

def fetch_us_stock_daily(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取美股個股日線資料
    """
    ticker = yf.Ticker(stock_id)
    df = ticker.history(start=start_date, end=end_date)
    
    if not df.empty:
        df.reset_index(inplace=True)
        rename_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        df = df.rename(columns=rename_mapping)
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['stock_id'] = stock_id
        
    return df
