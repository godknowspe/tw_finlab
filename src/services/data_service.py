from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from src.data.models import DailyPrice, PRICE_BASIS
from src.domain.symbols import canonical_symbol
from loguru import logger
import pandas as pd
import datetime

DAILY_INTERVALS = {'1d', '1w', '1wk', '1m', '1mo'}


class DataService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_stock_data_df(self, stock_id: str, start_date: str = None, end_date: str = None, interval: str = '1d') -> pd.DataFrame:
        stock_id = canonical_symbol(stock_id)
        stmt = select(DailyPrice).where(
            DailyPrice.stock_id == stock_id,
            DailyPrice.interval == interval,
            DailyPrice.price_basis == PRICE_BASIS,
        )
        if start_date:
            stmt = stmt.where(DailyPrice.date >= start_date)
        if end_date:
            stmt = stmt.where(DailyPrice.date <= end_date)
        rows = self.db.execute(stmt.order_by(DailyPrice.date.asc())).scalars().all()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([{
            "date": r.date, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume
        } for r in rows])
        df['date'] = pd.to_datetime(df['date'])
        return df.set_index('date')

    def has_stale_basis(self, stock_id: str, interval: str) -> bool:
        stmt = select(DailyPrice.id).where(
            DailyPrice.stock_id == canonical_symbol(stock_id),
            DailyPrice.interval == interval,
            DailyPrice.price_basis != PRICE_BASIS,
        ).limit(1)
        return self.db.execute(stmt).first() is not None

    def save_stock_data(self, df: pd.DataFrame, stock_id: str, interval: str = '1d') -> int:
        """Upsert bars (an in-progress bar re-fetched later must overwrite the earlier snapshot).
        Rows on another price basis for this symbol/interval are discarded first, since mixing
        adjusted and raw prices in one series is meaningless. Raises on DB failure."""
        if df.empty:
            return 0
        stock_id = canonical_symbol(stock_id)
        records = {}
        for ts, row in df.iterrows():
            dt = pd.Timestamp(ts).to_pydatetime()
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            if interval in DAILY_INTERVALS:
                dt = datetime.datetime(dt.year, dt.month, dt.day)
            records[dt] = {
                "stock_id": stock_id, "interval": interval, "date": dt, "price_basis": PRICE_BASIS,
                "open": float(row['open']), "high": float(row['high']), "low": float(row['low']),
                "close": float(row['close']), "volume": float(row['volume']),
            }
        try:
            self.db.execute(delete(DailyPrice).where(
                DailyPrice.stock_id == stock_id,
                DailyPrice.interval == interval,
                DailyPrice.price_basis != PRICE_BASIS,
            ))
            stmt = sqlite_insert(DailyPrice).values(list(records.values()))
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_id", "date", "interval"],
                set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume", "price_basis")},
            )
            self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        logger.info(f"Upserted {len(records)} bars for {stock_id} ({interval})")
        return len(records)
