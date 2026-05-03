import os
import pandas as pd
from typing import Optional
from loguru import logger
from .base import BaseDataProvider
from src.api.finmind_api import fetch_taiwan_stock_daily
from src.utils.retry import retry

class FinMindProvider(BaseDataProvider):
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("FINMIND_TOKEN")

    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        logger.info(f"FinMind: Fetching kbars for {stock_id} (interval: {interval})")
        # FinMind 主要支援日線
        if interval != "1d":
            logger.warning(f"FinMind only supports 1d interval, requested: {interval}")
            return pd.DataFrame()
        return fetch_taiwan_stock_daily(stock_id, start_date, end_date)

    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        # FinMind 即時報價需要另外的 API，暫時實作基礎
        return None
