import time
from typing import Dict, Iterable, Optional, Tuple

import yfinance as yf
from loguru import logger

from src.domain.symbols import is_tw, yf_ticker
from src.providers.factory import ProviderFactory
from src.services.config_service import ConfigService

# (last, previous close) per symbol; previous close may be None
Quotes = Dict[str, Tuple[float, Optional[float]]]

_cache: Dict[str, Tuple[float, Tuple[float, Optional[float]]]] = {}
CACHE_SECONDS = 20


def shioaji_api_if_enabled(config: ConfigService):
    if config.get_config("ds_realtime", "yfinance") != "Shioaji":
        return None
    try:
        return ProviderFactory.get_provider(
            "shioaji",
            api_key=config.get_config("ds_shioaji_api_key", ""),
            api_secret=config.get_config("ds_shioaji_api_secret", ""),
        ).api
    except Exception as e:
        logger.error(f"Shioaji unavailable for quotes: {e}")
        return None


def _shioaji_quotes(api, symbols) -> Quotes:
    contracts = [c for c in (api.Contracts.Stocks.get(s) for s in symbols) if c]
    out = {}
    if contracts:
        for contract, snap in zip(contracts, api.snapshots(contracts)):
            if snap and snap.close > 0:
                ref = float(contract.reference) if getattr(contract, "reference", None) else None
                out[contract.code] = (float(snap.close), ref)
    return out


def _yf_quote(symbol: str) -> Optional[Tuple[float, Optional[float]]]:
    info = yf.Ticker(yf_ticker(symbol)).fast_info
    if "lastPrice" not in info:
        return None
    prev = float(info["previousClose"]) if "previousClose" in info else None
    return float(info["lastPrice"]), prev


def get_quotes(symbols: Iterable[str], shioaji_api=None) -> Quotes:
    """Latest price and previous close. TW symbols via Shioaji snapshots when enabled, the
    rest via yfinance. Results are cached briefly so page refreshes do not hammer yfinance."""
    now = time.time()
    wanted = sorted(set(symbols))
    out: Quotes = {s: _cache[s][1] for s in wanted if s in _cache and now - _cache[s][0] < CACHE_SECONDS}
    missing = [s for s in wanted if s not in out]

    if shioaji_api:
        tw = [s for s in missing if is_tw(s)]
        if tw:
            try:
                out.update(_shioaji_quotes(shioaji_api, tw))
            except Exception as e:
                logger.error(f"Shioaji snapshot error: {e}")

    for s in [s for s in missing if s not in out]:
        try:
            q = _yf_quote(s)
            if q:
                out[s] = q
        except Exception as e:
            logger.warning(f"yfinance quote failed for {s}: {e}")

    for s in missing:
        if s in out:
            _cache[s] = (now, out[s])
    return out
