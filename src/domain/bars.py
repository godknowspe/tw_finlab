"""Bar period boundaries. A bar labelled `start` covers [start, bar_end(start, interval))."""
import pandas as pd

INTRADAY_MINUTES = {"15m": 15, "30m": 30, "60m": 60, "1h": 60}


def bar_end(start: pd.Timestamp, interval: str) -> pd.Timestamp:
    start = pd.Timestamp(start)
    if interval in INTRADAY_MINUTES:
        return start + pd.DateOffset(minutes=INTRADAY_MINUTES[interval])
    day = start.normalize()
    if interval in ("1w", "1wk"):
        return day + pd.DateOffset(days=7)
    if interval in ("1m", "1mo"):
        return day + pd.offsets.MonthBegin(1)
    return day + pd.DateOffset(days=1)


def bar_ends(index, interval: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([bar_end(pd.Timestamp(ts), interval) for ts in pd.DatetimeIndex(index)])
