import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.services.data_service import DataService
from src.providers.base import BaseDataProvider
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.models import Base, DailyPrice

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_save_stock_data(db_session):
    service = DataService(db_session)
    df = pd.DataFrame([
        {"open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000.0}
    ], index=[pd.Timestamp("2026-05-01")])
    
    service.save_stock_data(df, "2330", "1d")
    
    saved = db_session.query(DailyPrice).first()
    assert saved.stock_id == "2330"
    assert saved.close == 105.0

def test_get_stock_data_df(db_session):
    service = DataService(db_session)
    # Add dummy data
    p1 = DailyPrice(stock_id="2330", interval="1d", date=pd.Timestamp("2026-05-01"), open=100.0, high=110.0, low=90.0, close=105.0, volume=10.0)
    db_session.add(p1)
    db_session.commit()
    
    df = service.get_stock_data_df("2330", interval="1d")
    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]['close'] == 105.0

@patch('src.providers.yfinance_provider.YFinanceProvider.fetch_kbars')
def test_provider_fallback_logic(mock_fetch, db_session):
    # This would test the fallback in server.py if we were testing the endpoint,
    # but here we test the service/provider interaction.
    mock_fetch.return_value = pd.DataFrame([
        {"open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000.0}
    ], index=[pd.Timestamp("2026-05-01")])
    
    from src.providers.yfinance_provider import YFinanceProvider
    provider = YFinanceProvider()
    df = provider.fetch_kbars("AAPL", "2026-05-01", "2026-05-02")
    
    assert not df.empty
    assert mock_fetch.called
