"""USD/TWD exchange rate: live for current valuation, daily history for the equity curve.

Live rate comes from yfinance `TWD=X` (TWD per USD), cached for CACHE_SECONDS. If it cannot
be fetched, `settings.usd_twd_rate` is used and the result says so (`live=False`).
Daily history goes through the same price cache as stocks (symbol `TWD=X`).
"""
import threading
import time
from typing import Optional, Tuple

import yfinance as yf
from loguru import logger

FX_SYMBOL = "TWD=X"
CACHE_SECONDS = 600
_lock = threading.Lock()
_cache: Optional[Tuple[float, float]] = None     # (fetched_at, rate)


def get_usd_twd(fallback: float) -> Tuple[float, bool]:
    """(rate, live). `live` is False when the configured fallback had to be used."""
    global _cache
    with _lock:
        if _cache and time.time() - _cache[0] < CACHE_SECONDS:
            return _cache[1], True
        try:
            rate = float(yf.Ticker(FX_SYMBOL).fast_info["lastPrice"])
            if not 10 < rate < 100:          # sanity bound for TWD per USD
                raise ValueError(f"implausible USD/TWD {rate}")
            _cache = (time.time(), rate)
            return rate, True
        except Exception as e:
            logger.warning(f"Live USD/TWD unavailable, using configured {fallback}: {e}")
            if _cache:                        # a stale live rate beats the static setting
                return _cache[1], True
            return fallback, False
