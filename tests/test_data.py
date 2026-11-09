import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.models import Base, DailyPrice
from src.providers.yfinance_provider import drop_bad_bars
from src.services.data_service import DataService


@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def bars(*closes, start="2026-05-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000.0] * len(closes)}, index=idx)


def test_save_and_read_back(db_session):
    svc = DataService(db_session)
    svc.save_stock_data(bars(105.0), "2330.TW", "1d")
    df = svc.get_stock_data_df("2330", interval="1d")
    assert df["close"].tolist() == [105.0]


def test_save_upserts_existing_bar(db_session):
    """An intraday snapshot of today's bar must be overwritten by the final close."""
    svc = DataService(db_session)
    svc.save_stock_data(bars(100.0), "2330", "1d")
    svc.save_stock_data(bars(120.0), "2330", "1d")
    assert svc.get_stock_data_df("2330")["close"].tolist() == [120.0]
    assert db_session.query(DailyPrice).count() == 1


def test_rows_on_old_price_basis_are_ignored_then_replaced(db_session):
    db_session.add(DailyPrice(stock_id="0050", interval="1d", date=pd.Timestamp("2026-05-01"),
                              open=1, high=1, low=1, close=1, volume=1, price_basis="adjusted"))
    db_session.commit()
    svc = DataService(db_session)
    assert svc.get_stock_data_df("0050").empty
    assert svc.has_stale_basis("0050", "1d")
    svc.save_stock_data(bars(98.0, 99.0), "0050", "1d")
    assert not svc.has_stale_basis("0050", "1d")
    assert svc.get_stock_data_df("0050")["close"].tolist() == [98.0, 99.0]


def test_drop_bad_bars_only_removes_twii_ghost_bars():
    # Real data is kept even when it jumps or has a missing day.
    assert drop_bad_bars(bars(100, 121, 133, 146), "2330.TW")["close"].tolist() == [100, 121, 133, 146]
    assert drop_bad_bars(bars(100, 125, 101), "AAPL")["close"].tolist() == [100, 125, 101]
    ghost = bars(100, 100, 101)
    ghost.iloc[1, ghost.columns.get_loc("volume")] = 0
    assert drop_bad_bars(ghost, "^TWII")["close"].tolist() == [100, 101]


def test_needs_fetch_throttles_but_always_catches_up():
    import datetime
    from src.services import market_data
    df = bars(*([100.0] * 600))
    key = ("X", "15m")
    t0 = datetime.datetime(2026, 6, 1, 10, 14)
    market_data._last_refresh[key] = t0
    assert not market_data.needs_fetch(df, "15m", key, now=t0 + datetime.timedelta(minutes=2))
    assert market_data.needs_fetch(df, "15m", key, now=t0 + datetime.timedelta(minutes=6))
    assert market_data.needs_fetch(df, "1d", ("Y", "1d"), now=t0)           # never refreshed in this process
    assert market_data.needs_fetch(bars(1.0), "1d", key, now=t0)            # too short
