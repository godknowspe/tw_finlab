import os
import pandas as pd
from FinMind.data import DataLoader

def fetch_taiwan_stock_daily(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取台股個股日線資料
    """
    dl = DataLoader()
    
    # 嘗試從環境變數讀取 FinMind API Token (增加抓取次數上限)
    token = os.getenv("FINMIND_TOKEN")
    if token:
        dl.login_by_token(api_token=token)
        
    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date
    )
    
    # 資料清理與格式轉換，配合模型
    if not df.empty:
        # FinMind 回傳的欄位通常包含: date, stock_id, Trading_Volume, Trading_money, open, max, min, close, spread, Trading_turnover
        # 將欄位名稱轉換為與資料庫模型一致
        rename_mapping = {
            'Trading_Volume': 'volume',
            'max': 'high',
            'min': 'low'
        }
        df = df.rename(columns=rename_mapping)
        # 確保 date 是 datetime.date 格式
        df['date'] = pd.to_datetime(df['date']).dt.date
        
    return df
