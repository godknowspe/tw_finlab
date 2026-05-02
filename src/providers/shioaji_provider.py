import pandas as pd
from typing import Optional
from .base import BaseDataProvider
from src.api.shioaji_api import ShioajiClient, fetch_shioaji_kbars, fetch_shioaji_quote

class ShioajiProvider(BaseDataProvider):
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.client = ShioajiClient()
        self.api_key = api_key
        self.api_secret = api_secret
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = self.client.get_api(self.api_key, self.api_secret)
        return self._api

    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        # Shioaji 的 kbars 支援不同 interval，這裡暫時處理 1d
        # 如果需要分鐘層級，可以在這裡擴展
        return fetch_shioaji_kbars(self.api, stock_id, start_date, end_date)

    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        price = fetch_shioaji_quote(self.api, stock_id)
        if price:
            return {
                "stock_id": stock_id,
                "price": price
            }
        return None
