import datetime
import threading

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from src.providers.factory import ProviderFactory
from src.services.config_service import ConfigService
from src.services.data_service import DataService

INTRADAY = {"15m", "30m", "60m", "1h"}
_fetch_lock = threading.Lock()


def _history_start(interval: str) -> str:
    years = 10 if interval == "1d" else 20
    days = 60 if interval in INTRADAY else 365 * years
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


_last_refresh = {}
# Minimum gap between refetches of one (symbol, interval) once the cache is long enough.
THROTTLE_SECONDS = {"15m": 300, "30m": 300, "60m": 600, "1h": 600}
DEFAULT_THROTTLE_SECONDS = 900


def needs_fetch(df: pd.DataFrame, interval: str, key=None, now: datetime.datetime = None) -> bool:
    """Fetch when the cache is empty or short; otherwise at most once per throttle window.
    Whether the last bar is still forming, has just closed, or a newer bar exists, the only
    way to know is to ask the provider, so the throttle is the single freshness rule."""
    now = now or datetime.datetime.now()
    if df.empty or len(df) < (500 if interval in INTRADAY else 100):
        return True
    last_refresh = _last_refresh.get(key) if key is not None else None
    throttle = THROTTLE_SECONDS.get(interval, DEFAULT_THROTTLE_SECONDS)
    return last_refresh is None or (now - last_refresh).total_seconds() >= throttle


class MarketDataService:
    def __init__(self, db: Session):
        self.db = db
        self.data = DataService(db)
        self.config = ConfigService(db)

    def _provider_chain(self):
        source = self.config.get_config("ds_kline", "yfinance")
        chain = [source] + (["yfinance"] if source.lower() != "yfinance" else [])
        for name in chain:
            try:
                yield name, ProviderFactory.get_provider(
                    name,
                    api_key=self.config.get_config("ds_shioaji_api_key", ""),
                    api_secret=self.config.get_config("ds_shioaji_api_secret", ""),
                )
            except Exception as e:
                logger.error(f"Provider {name} unavailable: {e}")

    def refresh(self, symbol: str, interval: str = "1d") -> bool:
        """Fetch from the configured source, falling back to yfinance on error OR empty result."""
        start = _history_start(interval)
        end = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        with _fetch_lock:
            _last_refresh[(symbol, interval)] = datetime.datetime.now()
            for name, provider in self._provider_chain():
                try:
                    df = provider.fetch_kbars(symbol, start, end, interval)
                except Exception as e:
                    logger.error(f"{name} fetch failed for {symbol} {interval}: {e}")
                    continue
                if df is not None and not df.empty:
                    self.data.save_stock_data(df, symbol, interval)
                    return True
                logger.warning(f"{name} returned no {interval} bars for {symbol}")
        return False

    def get_bars(self, symbol: str, interval: str = "1d") -> pd.DataFrame:
        df = self.data.get_stock_data_df(symbol, interval=interval)
        if needs_fetch(df, interval, key=(symbol, interval)) or self.data.has_stale_basis(symbol, interval):
            if self.refresh(symbol, interval):
                df = self.data.get_stock_data_df(symbol, interval=interval)
        return df

    def daily_closes(self, symbols) -> pd.DataFrame:
        """Wide frame of raw daily closes (index = session date, one column per symbol),
        fetching any symbol whose cache is missing or stale."""
        cols = {}
        for sym in sorted(set(symbols)):
            df = self.get_bars(sym, "1d")
            if not df.empty:
                cols[sym] = df["close"]
        if not cols:
            return pd.DataFrame()
        return pd.DataFrame(cols).sort_index()
