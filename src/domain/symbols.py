import re

# Listed TW codes: 4 digits plus optional 1-2 char suffix (0050, 2330, 00631L, 00878).
_TW_CODE = re.compile(r"^\d{4}[0-9A-Z]{0,2}$")


def canonical_symbol(symbol: str) -> str:
    """Ledger/cache key: upper-case, no whitespace, TWSE '.TW' suffix stripped (2330.TW -> 2330).
    OTC '.TWO' is kept because yfinance needs it and it cannot be inferred from the code."""
    s = symbol.strip().upper()
    if s.endswith(".TW") and _TW_CODE.match(s[:-3]):
        s = s[:-3]
    return s


def is_tw(symbol: str) -> bool:
    s = canonical_symbol(symbol)
    return bool(_TW_CODE.match(s)) or s.endswith(".TWO")


def market_of(symbol: str) -> str:
    return "TW" if is_tw(symbol) else "US"


def currency_of(symbol: str) -> str:
    return "TWD" if is_tw(symbol) else "USD"


def yf_ticker(symbol: str) -> str:
    s = canonical_symbol(symbol)
    if s.startswith("^") or s.endswith(".TWO") or not is_tw(s):
        return s
    return f"{s}.TW"
