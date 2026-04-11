import pytest
import pandas as pd
from src.data.fetcher import get_stock_data_df
from src.data.models import Base, DailyPrice
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_get_stock_data_df_empty(monkeypatch):
    # Mock engine
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    
    # Mock the get_session logic or just pass a custom engine/session if possible, 
    # but the fetcher hardcodes the engine. For a simple test, just check the empty case.
    # To be safe, we can mock pandas read_sql
    def mock_read_sql(*args, **kwargs):
        return pd.DataFrame()
    monkeypatch.setattr(pd, 'read_sql', mock_read_sql)
    
    df = get_stock_data_df("0000", "2020-01-01", "2020-01-10")
    assert df.empty
