import pytest
import pandas as pd
from src.api.finmind_api import fetch_taiwan_stock_daily

def test_fetch_taiwan_stock_daily_returns_dataframe():
    # 只抓取一兩天的歷史資料進行測試，避免消耗太多 API 額度
    df = fetch_taiwan_stock_daily(stock_id="2330", start_date="2023-01-03", end_date="2023-01-04")
    
    # 驗證回傳的型別與資料是否為空
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    
    # 驗證是否包含模型所需的必要欄位
    expected_columns = {'stock_id', 'date', 'open', 'high', 'low', 'close', 'volume'}
    assert expected_columns.issubset(set(df.columns))
    
    # 驗證資料內容的正確性
    assert str(df.iloc[0]['stock_id']) == "2330"
