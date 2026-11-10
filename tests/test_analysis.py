import pandas as pd
import pytest

from src.domain.ledger import replay
from src.domain.valuation import value_positions
from src.web.analysis import calculate_trade_analysis

DAYS = pd.date_range("2026-01-05", periods=12, freq="B")
CLOSE = [10, 12, 15, 18, 20, 21, 22, 19, 17, 15, 15, 15]
BARS = pd.DataFrame({"open": CLOSE, "close": CLOSE,
                     "high": [c + 0.5 for c in CLOSE[:-1]] + [15.5],
                     "low": [9, 10, 12, 15, 18.5, 20, 21, 18, 16, 14.5, 14.8, 14.8], "volume": 1}, index=DAYS)


def t(i, action, price, day, shares=1000, **kw):
    return {"id": i, "uid": f"u{i}", "symbol": "2330", "action": action, "shares": shares, "price": price,
            "timestamp": DAYS[day].strftime("%Y-%m-%dT09:00"), "currency": "TWD", "fee": 0.0, "tax": 0.0, **kw}


def by_price(out):
    return {r["buy_price"]: r for r in out["buys"]}


def test_sell_is_shared_by_open_buys_and_sums_to_the_position():
    trades = [t(1, "BUY", 10.0, 0), t(2, "BUY", 20.0, 4), t(3, "SELL", 15.0, 9)]
    rows = by_price(calculate_trade_analysis(trades, lambda s: BARS))
    assert rows[10.0]["total_pnl"] == 5000 and rows[10.0]["return_pct"] == 50.0
    assert rows[20.0]["total_pnl"] == -5000 and rows[20.0]["return_pct"] == -25.0
    assert rows[10.0]["remaining"] == rows[20.0]["remaining"] == 500
    assert rows[20.0]["avg_cost_before"] == 10.0 and rows[20.0]["avg_cost_after"] == 15.0
    # Same totals as the Positions page.
    ledger = replay(trades)
    pos = value_positions(ledger, {"2330": 15.0}, 32.5)["positions"][0]
    assert sum(r["realized"] for r in rows.values()) == pytest.approx(ledger.realized_pnl["TWD"])
    assert sum(r["unrealized"] for r in rows.values()) == pytest.approx(pos["unrealized"])


def test_timing_ignores_later_trades():
    alone = by_price(calculate_trade_analysis([t(1, "BUY", 10.0, 0)], lambda s: BARS))[10.0]
    with_more = by_price(calculate_trade_analysis(
        [t(1, "BUY", 10.0, 0), t(2, "BUY", 20.0, 4), t(3, "SELL", 15.0, 9, shares=2000)], lambda s: BARS))[10.0]
    for k in ("ret_5d", "ret_20d", "mae_pct", "mfe_pct", "days_observed"):
        assert alone[k] == with_more[k]
    assert alone["ret_5d"] == 110.0                  # close 5 sessions later = 21
    assert alone["ret_20d"] is None and alone["days_observed"] == 11


def test_fees_are_in_cost_and_return():
    rows = by_price(calculate_trade_analysis([t(1, "BUY", 10.0, 0, fee=20.0), t(2, "SELL", 15.0, 9, fee=21.0, tax=45.0)],
                                             lambda s: BARS))
    r = rows[10.0]
    assert r["status"] == "CLOSED" and r["realized"] == pytest.approx(15000 - 66 - 10020)
    assert r["return_pct"] == pytest.approx((15000 - 66 - 10020) / 10020 * 100, abs=0.01)


def test_missing_prices_flag_open_lots():
    rows = calculate_trade_analysis([t(1, "BUY", 10.0, 0)], lambda s: pd.DataFrame())["buys"]
    assert rows[0]["price_estimated"] and rows[0]["unrealized"] == 0 and rows[0]["ret_5d"] is None
