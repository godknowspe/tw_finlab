import yfinance as yf
import pandas as pd
from typing import Optional
from loguru import logger
from .base import BaseDataProvider
from src.domain.symbols import yf_ticker
from src.utils.retry import retry

INTRADAY_PERIOD = {"15m": "60d", "30m": "60d", "60m": "730d", "1h": "730d"}
YF_INTERVAL = {"1d": "1d", "1w": "1wk", "1wk": "1wk", "1mo": "1mo", "15m": "15m", "30m": "30m", "60m": "60m", "1h": "60m"}


def drop_bad_bars(df: pd.DataFrame, ticker_id: str) -> pd.DataFrame:
    """Drop only ^TWII holiday ghost bars: zero volume with open == high == low == close.
    That pattern is structural (Yahoo emits a bar on a closed session), so it needs no
    price threshold. Everything else is kept as delivered."""
    if ticker_id != "^TWII" or df.empty:
        return df
    ghost = (df["volume"] == 0) & (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    for ts in df.index[ghost]:
        logger.warning(f"Dropped ^TWII ghost bar {ts}")
    return df[~ghost]


class YFinanceProvider(BaseDataProvider):
    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        if interval not in YF_INTERVAL:
            raise ValueError(f"Unsupported interval: {interval}")
        ticker_id = yf_ticker(stock_id)
        logger.info(f"Fetching kbars for {ticker_id} from {start_date} to {end_date} (interval: {interval})")

        # auto_adjust=False: no dividend adjustment, so PnL is measured on the same basis as the
        # recorded trade prices, and history is not rewritten after every dividend. Yahoo still
        # split-adjusts these closes; the ledger has no split events (a future split needs one).
        kwargs = {"interval": YF_INTERVAL[interval], "progress": False, "auto_adjust": False}
        if interval in INTRADAY_PERIOD:
            kwargs["period"] = INTRADAY_PERIOD[interval]
        else:
            kwargs.update(start=start_date, end=end_date)

        df = yf.download(ticker_id, **kwargs)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Intraday bars arrive tz-aware in exchange time; keep exchange wall-clock time,
        # the same convention as trade timestamps.
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df = df.dropna(subset=["open", "high", "low", "close"])
        df["volume"] = df["volume"].fillna(0)
        df.index.name = "date"
        return drop_bad_bars(df, ticker_id)

    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        info = yf.Ticker(yf_ticker(stock_id)).fast_info
        if "lastPrice" not in info:
            return None
        return {
            "stock_id": stock_id,
            "price": float(info["lastPrice"]),
            "prev_close": float(info["previousClose"]) if "previousClose" in info else None,
        }
