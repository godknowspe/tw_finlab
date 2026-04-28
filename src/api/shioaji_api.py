import shioaji as sj
import pandas as pd
import time
from typing import Optional

class ShioajiClient:
    _instance = None
    _api = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShioajiClient, cls).__new__(cls)
        return cls._instance

    def get_api(self, api_key: str = "", api_secret: str = ""):
        if self._api is None:
            self._api = sj.Shioaji()
            if api_key and api_secret:
                self._api.login(
                    api_key=api_key,
                    secret_key=api_secret
                )
        return self._api

def fetch_shioaji_kbars(api, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取 Shioaji K 線資料
    """
    # 判斷市場 (暫時只處理台股)
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return pd.DataFrame()

    kbars = api.kbars(
        contract=contract,
        start=start_date,
        end=end_date
    )
    
    df = pd.DataFrame({**kbars})
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.rename(columns={
            "ts": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        # 轉換為 date 格式以符合現有邏輯
        df["date"] = df["date"].dt.date
        df["stock_id"] = stock_id
        
    return df

def fetch_shioaji_quote(api, stock_id: str) -> Optional[float]:
    """
    獲取 Shioaji 即時報價 (快照)
    """
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return None
    
    # 訂閱或直接抓快照
    snapshot = api.snapshots([contract])
    if snapshot:
        return float(snapshot[0].close)
    return None
