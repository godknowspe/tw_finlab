import pandas as pd
from sqlalchemy import text
from src.data.models import get_engine

def get_stock_data_df(stock_id: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    engine = get_engine()

    conditions = ["stock_id = :stock_id"]
    params = {"stock_id": stock_id}

    if start_date:
        conditions.append("date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("date <= :end_date")
        params["end_date"] = end_date

    query = text(
        "SELECT * FROM daily_price WHERE " + " AND ".join(conditions) + " ORDER BY date ASC"
    )

    df = pd.read_sql_query(query, engine, params=params)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    return df
