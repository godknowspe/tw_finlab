import numpy as np
import pandas as pd
import pytest

from research.twii_regime.data import clean_bars, split_adjust
from research.twii_regime.engine import Costs, run

NO_COST = Costs(fee=0.0, tax=0.0, slippage=0.0, cash_rate=0.0)


def bars(rows, start="2024-01-02"):
    idx = pd.bdate_range(start, periods=len(rows))
    df = pd.DataFrame(rows, columns=["open", "close"], index=idx)
    df["high"], df["low"] = df[["open", "close"]].max(axis=1), df[["open", "close"]].min(axis=1)
    df["volume"], df["dividend"] = 1.0, 0.0
    return df


def target(df, values):
    return pd.Series(values, index=df.index, dtype=float)


def test_flat_prices_with_costs_never_profit():
    df = bars([(100, 100)] * 6)
    r = run(df, target(df, [0, 1, 1, 1, 0, 0]), Costs(fee=0.001425, tax=0.001, slippage=0.0005, cash_rate=0.0), start=df.index[0])
    assert r["equity"].iloc[-1] < 1.0 and r["equity"].iloc[0] == pytest.approx(1.0)
    assert r["costs_paid"] == pytest.approx(1.0 - r["equity"].iloc[-1], rel=1e-6)


def test_buy_signal_does_not_earn_the_gap_before_the_fill():
    # signal on day 1 close (100); day 2 opens at 110 and closes 110: bought at the open, no gain.
    df = bars([(100, 100), (100, 100), (110, 110), (110, 110)])
    r = run(df, target(df, [0, 1, 1, 1]), NO_COST, start=df.index[0])
    assert r["equity"].iloc[-1] == pytest.approx(1.0)


def test_sell_signal_still_suffers_the_gap_before_the_fill():
    # held through day 1 (close 100); sell signal at that close; day 2 opens at 90 -> -10% is taken.
    df = bars([(100, 100), (100, 100), (90, 90), (90, 90)])
    r = run(df, target(df, [1, 0, 0, 0]), NO_COST, start=df.index[0])
    assert r["equity"].iloc[-1] == pytest.approx(0.9)


def test_signal_uses_only_the_previous_close_not_the_same_day():
    df = bars([(100, 100), (100, 120), (120, 120)])
    r = run(df, target(df, [0, 1, 1]), NO_COST, start=df.index[0])    # decided at day-1 close, filled at day-2 open (120)
    assert r["equity"].iloc[-1] == pytest.approx(1.0)
    assert r["fills"][0]["date"] == df.index[2] and r["fills"][0]["price"] == pytest.approx(120)


def test_dividend_goes_to_the_holder_before_ex_date_not_the_new_buyer():
    df = bars([(100, 100)] * 5)
    df.loc[df.index[3], "dividend"] = 5.0
    held = run(df, target(df, [1, 1, 1, 1, 1]), NO_COST, start=df.index[0])
    late = run(df, target(df, [0, 0, 0, 1, 1]), NO_COST, start=df.index[0])      # first fill is the ex-date open
    assert held["equity"].iloc[-1] == pytest.approx(1.05) and late["equity"].iloc[-1] == pytest.approx(1.0)


def test_cash_earns_interest_by_calendar_days():
    df = bars([(100, 100)] * 5, start="2024-01-04")          # Thu, Fri, Mon, Tue, Wed
    r = run(df, target(df, [0] * 5), Costs(fee=0, tax=0, slippage=0, cash_rate=0.0365), start=df.index[0])
    days = (df.index[-1] - df.index[0]).days
    assert r["equity"].iloc[-1] == pytest.approx(1 + 0.0365 / 365 * days, rel=1e-6)


def test_weight_drifts_between_rebalances_and_cash_never_goes_negative():
    df = bars([(100, 100), (100, 100), (100, 150), (150, 150), (150, 150)])
    r = run(df, target(df, [0.5] * 5), NO_COST, start=df.index[0], rebalance_band=0.5)
    assert (r["cash"] >= -1e-9).all()
    assert r["weight"].iloc[-1] > 0.5 and len(r["fills"]) == 1        # only the first entry traded; drift is not undone for free


def test_split_adjustment_keeps_wealth_continuous_and_scales_dividends():
    idx = pd.bdate_range("2014-01-01", periods=4)
    df = pd.DataFrame({"open": [60.0, 60.0, 15.0, 15.0], "high": [60.0] * 2 + [15.0] * 2, "low": [60.0] * 2 + [15.0] * 2,
                       "close": [60.0, 60.0, 15.0, 15.0], "volume": [100.0] * 4, "dividend": [4.0, 0, 0, 0]}, index=idx)
    out = split_adjust(df, [(idx[2], 4.0)])
    assert out["close"].tolist() == [15.0, 15.0, 15.0, 15.0]
    assert out["dividend"].iloc[0] == pytest.approx(1.0) and out["volume"].iloc[0] == pytest.approx(400.0)


def test_clean_bars_drops_ghost_sessions_and_the_unfinished_day():
    idx = pd.bdate_range("2024-01-02", periods=4)
    df = pd.DataFrame({"open": [10, 10, 10, 11], "high": [11, 10, 12, 11], "low": [9, 10, 9, 11], "close": [10, 10, 11, 11],
                       "volume": [5, 0, 5, 5]}, index=idx)
    out = clean_bars(df, today=idx[3])
    assert list(out.index) == [idx[0], idx[2]]               # day 1 is a flat zero-volume ghost; day 3 is today (unfinished)
