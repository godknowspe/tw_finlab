"""Frozen research data: ^TWII (signal, price index) and 0050 (tradable, with dividends).

Everything is fetched once, cleaned, and written to a parquet/CSV snapshot with the fetch time,
so every strategy and every re-run sees the same sessions. The live price cache of the dashboard
is deliberately not used: it falls back between providers and price bases.

0050 needs care. Yahoo reports its prices split-adjusted only in `Adj Close`; `Close` still
shows the 1:4 split of 2014-01-02 as a -75% day. We rebuild split-adjusted OHLC ourselves (so
costs, lots and dividends stay separate from price) and keep cash dividends as their own column,
in per-share amounts of the units the prices are quoted in.
"""
import datetime
import json
from pathlib import Path

import pandas as pd

SNAP = Path(__file__).parent / "snapshot"
SPLITS = {"0050.TW": [(pd.Timestamp("2014-01-02"), 4.0)]}      # (first session at the new price, ratio)
WARMUP_START = "1997-01-01"      # ^TWII goes back to 1997-07; 0050 only to 2009


def split_adjust(df: pd.DataFrame, splits) -> pd.DataFrame:
    """Divide prices before each split by its ratio and multiply volume, dividends likewise, so
    all history is in today's share units."""
    out = df.copy()
    for day, ratio in splits:
        before = out.index < day
        for col in ("open", "high", "low", "close"):
            out.loc[before, col] = out.loc[before, col] / ratio
        out.loc[before, "volume"] = out.loc[before, "volume"] * ratio
        if "dividend" in out:
            out.loc[before, "dividend"] = out.loc[before, "dividend"] / ratio
    return out


def clean_bars(df: pd.DataFrame, today: pd.Timestamp = None) -> pd.DataFrame:
    """Drop ghost sessions (no volume and a flat bar) and any bar not yet finished today. A flat
    zero-volume bar is a closed session that the provider padded; it is removed, never
    forward-filled, so 200/252-session windows count real sessions only."""
    df = df.dropna(subset=["open", "high", "low", "close"])
    ghost = (df["volume"] == 0) & (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    df = df[~ghost]
    if today is not None:
        df = df[df.index < today.normalize()]
    return df


def _download(symbol: str) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.Ticker(symbol).history(start=WARMUP_START, interval="1d", auto_adjust=False, actions=True)
    raw.index = raw.index.tz_localize(None).normalize()
    df = raw.rename(columns=str.lower).rename(columns={"dividends": "dividend"})
    keep = ["open", "high", "low", "close", "volume"] + (["dividend"] if "dividend" in df else [])
    df = df[keep]
    if "dividend" in df:
        df["dividend"] = df["dividend"].fillna(0.0)
    return df


def fetch(symbols=("^TWII", "0050.TW"), today: pd.Timestamp = None) -> dict:
    today = today if today is not None else pd.Timestamp(datetime.date.today())
    out = {}
    for s in symbols:
        df = clean_bars(_download(s), today)
        out[s] = split_adjust(df, SPLITS.get(s, []))
    return out


def freeze(data: dict, path: Path = SNAP) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    meta = {"fetched_at": datetime.datetime.now().isoformat(timespec="seconds"), "symbols": {}}
    for s, df in data.items():
        df.to_csv(path / f"{s.replace('^', '')}.csv", index_label="date")
        meta["symbols"][s] = {"first": df.index[0].strftime("%Y-%m-%d"), "last": df.index[-1].strftime("%Y-%m-%d"), "bars": int(len(df)),
                              "dividends": int((df["dividend"] > 0).sum()) if "dividend" in df else 0}
    (path / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def load(path: Path = SNAP) -> dict:
    meta = json.loads((path / "meta.json").read_text())
    data = {s: pd.read_csv(path / f"{s.replace('^', '')}.csv", index_col="date", parse_dates=True) for s in meta["symbols"]}
    return {"meta": meta, "data": data}
