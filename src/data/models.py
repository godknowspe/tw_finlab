from sqlalchemy import Column, Integer, String, Float, Date, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

class DailyPrice(Base):
    __tablename__ = 'daily_price'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('stock_id', 'date', name='uq_stock_date'),
    )

def get_engine(db_path=None):
    if db_path is None:
        # 預設儲存在專案根目錄的 data/tw_finlab.db
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.path.join(project_root, 'data')
        os.makedirs(db_dir, exist_ok=True)
        db_path = f"sqlite:///{os.path.join(db_dir, 'tw_finlab.db')}"
    return create_engine(db_path)

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
