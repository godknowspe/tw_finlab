"""Instrument type (ETF or individual stock) from yfinance `quoteType`, cached in app_config.

The type decides whether a trailing stop is a stop-loss (stock) or only a warning (ETF). It is
looked up once per symbol; a failed lookup falls back to a naming rule (TW codes starting 00
are ETFs) and is retried on the next start.
"""
import yfinance as yf
from loguru import logger

from src.domain.symbols import is_tw, yf_ticker
from src.services.config_service import ConfigService

_memo = {}


def is_etf(symbol: str, config: ConfigService) -> bool:
    if symbol in _memo:
        return _memo[symbol]
    key = f"qtype_{symbol}"
    qtype = config.get_config(key)
    if qtype is None:
        try:
            qtype = (yf.Ticker(yf_ticker(symbol)).info or {}).get("quoteType")
        except Exception as e:
            logger.warning(f"quoteType lookup failed for {symbol}: {e}")
            qtype = None
        if qtype:
            config.set_config(key, qtype)
    if qtype is None:
        return is_tw(symbol) and symbol.startswith("00")
    _memo[symbol] = qtype == "ETF"
    return _memo[symbol]


def adjusted_closes(symbol: str, start: str):
    """Dividend-adjusted daily closes for total-return analysis (not cached: the price cache
    stores unadjusted prices to match trade prices)."""
    df = yf.download(yf_ticker(symbol), start=start, auto_adjust=True, progress=False)
    if df.empty:
        return None
    close = df["Close"]
    return (close.iloc[:, 0] if hasattr(close, "columns") else close).dropna()
