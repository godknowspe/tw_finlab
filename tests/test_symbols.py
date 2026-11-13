import pytest

from src.domain.symbols import currency_of, market_of, yf_ticker
from src.schemas.state import WatchlistItem


@pytest.mark.parametrize("sym", ["2330", "0050", "00631L", "6488.TWO", "^TWII", "^TWOII"])
def test_taiwan_symbols_including_indexes_are_tw(sym):
    assert market_of(sym) == "TW" and currency_of(sym) == "TWD"


@pytest.mark.parametrize("sym", ["VTI", "QQQ", "^GSPC", "^IXIC"])
def test_other_symbols_are_us(sym):
    assert market_of(sym) == "US" and currency_of(sym) == "USD"


def test_index_keeps_its_yahoo_symbol_and_the_watchlist_regroups_stored_entries():
    assert yf_ticker("^TWII") == "^TWII"
    assert WatchlistItem(symbol="^twii", market="US").market == "TW"
