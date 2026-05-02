import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional

class BaseDataProvider(ABC):
    @abstractmethod
    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        """獲取 K 線資料"""
        pass

    @abstractmethod
    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        """獲取即時報價"""
        pass
