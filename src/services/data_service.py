from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from src.data.models import DailyPrice
import pandas as pd
import numpy as np
import datetime

class DataService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_stock_data_df(self, stock_id: str, start_date: str = None, end_date: str = None, interval: str = '1d') -> pd.DataFrame:
        stmt = select(DailyPrice).where(
            and_(
                DailyPrice.stock_id == stock_id,
                DailyPrice.interval == interval
            )
        )
        
        if start_date:
            stmt = stmt.where(DailyPrice.date >= start_date)
        if end_date:
            stmt = stmt.where(DailyPrice.date <= end_date)
            
        stmt = stmt.order_by(DailyPrice.date.asc())
        
        result = self.db.execute(stmt)
        data = result.scalars().all()
        
        if not data:
            return pd.DataFrame()
            
        df_data = []
        for row in data:
            df_data.append({
                "date": row.date,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume
            })
            
        df = pd.DataFrame(df_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df

    def save_stock_data(self, df: pd.DataFrame, stock_id: str, interval: str = '1d'):
        if df.empty:
            return

        # 預先抓取所有已存在的日期，優化效能
        existing_rows = self.db.query(DailyPrice.date).filter(
            DailyPrice.stock_id == stock_id,
            DailyPrice.interval == interval
        ).all()
        existing_dates = {row[0] for row in existing_rows}

        for index, row in df.iterrows():
            # 1. 處理日期索引
            if isinstance(index, (datetime.datetime, datetime.date, pd.Timestamp)):
                dt = index
                if hasattr(dt, 'to_pydatetime'):
                    dt = dt.to_pydatetime()
            elif isinstance(index, (int, float, np.integer)):
                if index > 100000000:
                    dt = datetime.datetime.fromtimestamp(index)
                else:
                    if 'date' in row:
                        dt = row['date']
                        if hasattr(dt, 'to_pydatetime'):
                            dt = dt.to_pydatetime()
                        elif isinstance(dt, str):
                            dt = pd.to_datetime(dt).to_pydatetime()
                    else:
                        continue
            else:
                try:
                    dt = pd.to_datetime(index).to_pydatetime()
                except:
                    continue
            
            # 2. 格式化日期符合 SQLite 儲存規範
            if interval in ['1d', '1w', '1m', '1wk', '1mo']:
                dt = datetime.datetime(dt.year, dt.month, dt.day)
            else:
                if hasattr(dt, 'replace') and dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)

            # 3. 判斷是更新還是新增
            if dt in existing_dates:
                # 這裡為了簡單，重複資料不再重複 update 欄位，除非資料量極小
                # 或者如果你需要強制更新，可以改回原來的邏輯，但建議大量資料時只 insert new
                continue
            else:
                price = DailyPrice(
                    stock_id=stock_id,
                    interval=interval,
                    date=dt,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                )
                self.db.add(price)
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Error during commit for {stock_id}: {e}")
