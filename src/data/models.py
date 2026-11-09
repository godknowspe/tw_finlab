from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, UniqueConstraint, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

# 'raw' = yfinance auto_adjust=False: NOT dividend-adjusted (same basis as recorded trade prices)
# but still split-adjusted by Yahoo. Rows written before this column existed were fully adjusted.
PRICE_BASIS = "raw"


class DailyPrice(Base):
    __tablename__ = 'daily_price'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(String(20), nullable=False, index=True)
    interval = Column(String(10), nullable=False, default='1d', index=True)
    # Daily+ bars: midnight of the session date. Intraday: exchange-local wall-clock time.
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    price_basis = Column(String(10), nullable=False, default=PRICE_BASIS, server_default="adjusted")

    __table_args__ = (
        UniqueConstraint('stock_id', 'date', 'interval', name='uq_stock_date_interval'),
    )

class AppConfig(Base):
    __tablename__ = 'app_config'
    key = Column(String(50), primary_key=True)
    value = Column(String(500), nullable=False)


def _migrate(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("daily_price")}
    if "price_basis" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE daily_price ADD COLUMN price_basis VARCHAR(10) NOT NULL DEFAULT 'adjusted'"))


_engines = {}


def get_engine(db_path=None):
    if db_path is None:
        db_path = os.environ.get("TW_FINLAB_DB_URL")
    if db_path is None:
        # 預設儲存在專案根目錄的 data/tw_finlab.db
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.path.join(project_root, 'data')
        os.makedirs(db_dir, exist_ok=True)
        db_path = f"sqlite:///{os.path.join(db_dir, 'tw_finlab.db')}"
    if db_path not in _engines:
        engine = create_engine(db_path)
        Base.metadata.create_all(engine)
        _migrate(engine)
        _engines[db_path] = engine
    return _engines[db_path]

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
