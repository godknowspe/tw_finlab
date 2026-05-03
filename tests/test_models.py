import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.models import Base, DailyPrice, AppConfig
import datetime

@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_daily_price(session):
    price = DailyPrice(
        stock_id="2330",
        interval="1d",
        date=datetime.datetime(2026, 5, 1),
        open=1000.0,
        high=1010.0,
        low=990.0,
        close=1005.0,
        volume=100000.0
    )
    session.add(price)
    session.commit()
    
    saved_price = session.query(DailyPrice).first()
    assert saved_price.stock_id == "2330"
    assert saved_price.close == 1005.0

def test_app_config(session):
    config = AppConfig(key="ds_kline", value="yfinance")
    session.add(config)
    session.commit()
    
    saved_config = session.query(AppConfig).filter_by(key="ds_kline").first()
    assert saved_config.value == "yfinance"

def test_unique_constraint(session):
    date = datetime.datetime(2026, 5, 1)
    p1 = DailyPrice(stock_id="2330", interval="1d", date=date, open=100.0, high=110.0, low=90.0, close=105.0, volume=10.0)
    session.add(p1)
    session.commit()
    
    p2 = DailyPrice(stock_id="2330", interval="1d", date=date, open=101.0, high=111.0, low=91.0, close=106.0, volume=11.0)
    session.add(p2)
    with pytest.raises(Exception): # sqlalchemy.exc.IntegrityError
        session.commit()
