import datetime

import pandas as pd
import pytest

from src.domain.ledger import replay, validate_trades
from src.domain.symbols import canonical_symbol, currency_of, yf_ticker
from src.domain.valuation import bar_pnl, historical_roi, value_positions


def t(id, sym, action, shares, price, ts, **kw):
    return {"id": id, "symbol": sym, "action": action, "shares": shares, "price": price,
            "timestamp": ts, "currency": currency_of(sym), **kw}


def test_moving_average_with_fees():
    L = replay([
        t(1, "2330", "BUY", 1000, 100.0, "2026-01-02T09:00", fee=142),
        t(2, "2330", "BUY", 1000, 200.0, "2026-01-03T09:00", fee=285),
        t(3, "2330", "SELL", 1000, 200.0, "2026-01-04T09:00", fee=285, tax=600),
    ], cash_twd=1_000_000)
    pos = L.positions["2330"]
    assert pos.shares == 1000
    assert pos.avg_cost == pytest.approx((100_142 + 200_285) / 2000)
    assert L.realized_pnl["TWD"] == pytest.approx(200_000 - 885 - 150_213.5)
    assert L.cash["TWD"] == pytest.approx(1_000_000 - 100_142 - 200_285 + 200_000 - 885)


def test_same_minute_buy_then_sell_ordered_by_id():
    L = replay([
        t(2, "VTI", "SELL", 10, 110.0, "2026-06-01T09:00"),
        t(1, "VTI", "BUY", 10, 100.0, "2026-06-01T09:00"),
    ])
    assert L.positions["VTI"].shares == 0
    assert L.realized_pnl["USD"] == pytest.approx(100.0)


def test_oversell_is_rejected():
    err = validate_trades([t(1, "VTI", "BUY", 5, 100.0, "2026-06-01T09:00"), t(2, "VTI", "SELL", 6, 100.0, "2026-06-02T09:00")])
    assert "only 5 held" in err


def test_symbol_rules():
    assert canonical_symbol(" 2330.tw ") == "2330"
    assert canonical_symbol("00631L.TW") == "00631L"
    assert yf_ticker("2330") == "2330.TW" and yf_ticker("6488.TWO") == "6488.TWO" and yf_ticker("AAPL") == "AAPL"
    assert currency_of("AAPL") == "USD" and currency_of("0050") == "TWD"


def test_missing_price_is_valued_at_cost_not_zero():
    L = replay([t(1, "2454", "BUY", 10, 4220.0, "2026-10-15T14:40")], cash_twd=100_000)
    v = value_positions(L, {}, 32.5)
    assert v["positions"][0]["market_value"] == pytest.approx(42_200)
    assert v["summary"]["estimated_prices"] == ["2454"]


def test_historical_roi_holds_unpriced_position_at_cost():
    trades = [t(1, "0050", "BUY", 1000, 100.0, "2026-10-12T09:00"), t(2, "2454", "BUY", 10, 4000.0, "2026-10-14T09:00")]
    closes = pd.DataFrame({"0050": [100.0, 110.0, 110.0]}, index=pd.to_datetime(["2026-10-12", "2026-10-13", "2026-10-14"]))
    out = historical_roi(trades, closes, 32.5, today=datetime.date(2026, 10, 14))
    # 0050 +10k on 100k invested; 2454 bought on 10/14 at cost must not drag ROI to a loss.
    assert out["tw"][-1]["value"] == pytest.approx(10_000 / 140_000 * 100, abs=0.01)
    assert out["estimated"] == ["2454"]


def test_bar_pnl_uses_interval_end_not_next_bar():
    # 15m bars with a session gap: 13:00 bar ends 13:15, so a 14:10 fill belongs to no bar until 15:00.
    idx = pd.to_datetime(["2026-06-01 09:00", "2026-06-01 13:00", "2026-06-01 15:00"])
    closes = pd.Series([100.0, 100.0, 110.0], index=idx)
    pnl = bar_pnl([t(1, "2330", "BUY", 1000, 100.0, "2026-06-01T14:10")], idx, closes, "15m")
    assert [p["total_pnl"] for p in pnl] == [None, None, pytest.approx(10_000)]


def test_bar_pnl_ignores_trades_after_last_bar():
    idx = pd.to_datetime(["2026-06-01 09:00", "2026-06-01 09:15"])
    pnl = bar_pnl([t(1, "2330", "BUY", 1, 100.0, "2026-06-02T09:00")], idx, pd.Series([100.0, 110.0], index=idx), "15m")
    assert [p["total_pnl"] for p in pnl] == [None, None]


def test_bar_pnl_weekly_bar_includes_trades_through_week_end():
    idx = pd.to_datetime(["2026-06-01", "2026-06-08"])
    pnl = bar_pnl([t(1, "2330", "BUY", 1000, 100.0, "2026-06-05T10:00")], idx, pd.Series([110.0, 120.0], index=idx), "1wk")
    assert [p["total_pnl"] for p in pnl] == [pytest.approx(10_000), pytest.approx(20_000)]


def test_historical_roi_seeds_price_from_before_first_trade_and_rejects_bad_prices():
    closes = pd.DataFrame({"VTI": [120.0, 0.0, float("inf")]}, index=pd.to_datetime(["2026-05-29", "2026-06-01", "2026-06-02"]))
    out = historical_roi([t(1, "VTI", "BUY", 1, 100.0, "2026-06-01T10:00")], closes, 32.5, today=datetime.date(2026, 6, 2))
    assert [p["value"] for p in out["us"]] == [20.0, 20.0]
    assert out["estimated"] == []
