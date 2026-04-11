import pandas as pd
from src.data.models import get_engine

def get_stock_data_df(stock_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    engine = get_engine()
    query = f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}'"
    if start_date:
        query += f" AND date >= '{start_date}'"
    if end_date:
        query += f" AND date <= '{end_date}'"
    query += " ORDER BY date ASC"
    
    df = pd.read_sql_query(query, engine)
    if not df.empty:
        # 將字串轉換為 pandas datetime 格式
        df['date'] = pd.to_datetime(df['date'])
        # Backtrader 的 PandasData 預設需要 DatetimeIndex
        df.set_index('date', inplace=True)
    return df
