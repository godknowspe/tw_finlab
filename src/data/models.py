from sqlalchemy import Column, Integer, String, Float, Date, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

class DailyPrice(Base):
    __tablename__ = 'daily_price'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(String(20), nullable=False, index=True)
    interval = Column(String(10), nullable=False, default='1d', index=True) # 新增 interval 欄位
    date = Column(Date, nullable=False, index=True)
    # 為了支援分 K，將 date 改為 DateTime 或改名為 timestamp
    # 這裡我們維持叫 date 但儲存 ISO 字串或 DateTime 對象
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('stock_id', 'date', 'interval', name='uq_stock_date_interval'),
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
