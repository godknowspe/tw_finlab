import pandas as pd
from typing import Optional
from loguru import logger
from .base import BaseDataProvider
from src.api.shioaji_api import ShioajiClient, fetch_shioaji_kbars, fetch_shioaji_quote
from src.utils.retry import retry

class ShioajiProvider(BaseDataProvider):
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.client = ShioajiClient()
        self.api_key = api_key
        self.api_secret = api_secret
        self._api = None

    @property
    def api(self):
        if self._api is None:
            logger.info("Shioaji: Initializing API client...")
            self._api = self.client.get_api(self.api_key, self.api_secret)
        return self._api

    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        logger.info(f"Shioaji: Fetching kbars for {stock_id} (interval: {interval})")
        # Shioaji 的 kbars 支援不同 interval，這裡暫時處理 1d
        return fetch_shioaji_kbars(self.api, stock_id, start_date, end_date)

    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        logger.info(f"Shioaji: Fetching realtime quote for {stock_id}")
        price = fetch_shioaji_quote(self.api, stock_id)
        if price:
            return {
                "stock_id": stock_id,
                "price": price
            }
        return None
