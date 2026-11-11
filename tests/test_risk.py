import pandas as pd
import pytest

from src.domain.dip_buying import compare
from src.domain.risk import REBUY_WINDOW, round_trips, trade_cost, trailing_stop


def bars(closes, spread=1.0):
    idx = pd.bdate_range("2026-01-05", periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c + spread, "low": c - spread, "close": c, "volume": 1.0})


def t(i, action, shares, price, day, sym="VTI", **kw):
    return {"uid": f"u{i}", "id": i, "symbol": sym, "action": action, "shares": shares, "price": price,
            "timestamp": f"{day}T10:00", "currency": "TWD" if sym[0].isdigit() else "USD", "fee": 0.0, "tax": 0.0, **kw}


# ---- trailing stops -------------------------------------------------------------------------

def test_stop_trails_the_recent_high_by_a_multiple_of_atr():
    b = bars([100.0] * 30, spread=1.0)          # true range 2 -> ATR 2% of 100
    s = trailing_stop(b, is_etf=False)
    assert s["suggested_pct"] == pytest.approx(5.0)          # 2.5 x 2%
    assert s["stop_price"] == pytest.approx(95.0) and s["kind"] == "stop_loss" and not s["triggered"]


def test_etf_gets_a_warning_and_live_price_triggers_it():
    b = bars([100.0] * 30)
    s = trailing_stop(b, is_etf=True, live_price=94.0)
    assert s["kind"] == "warning" and s["triggered"] and s["distance_pct"] < 0


def test_custom_percentage_overrides_volatility_and_stop_rises_with_price():
    rising = bars([100.0] * 20 + [120.0] * 10)
    s = trailing_stop(rising, is_etf=False, custom_pct=10)
    assert s["custom"] and s["stop_pct"] == 10 and s["stop_price"] == pytest.approx(108.0)


def test_not_enough_history_means_no_stop():
    assert trailing_stop(bars([100.0] * 5), is_etf=False) is None


# ---- round trips ----------------------------------------------------------------------------

CLOSES = {"VTI": pd.Series([100.0] * 200, index=pd.bdate_range("2026-01-01", periods=200))}


def test_partial_sell_and_rebuy_is_one_trip_measured_against_holding():
    trips = round_trips([t(1, "BUY", 20, 10, "2026-01-02"), t(2, "SELL", 10, 18, "2026-02-02"),
                         t(3, "BUY", 10, 12, "2026-03-02")], CLOSES)
    (r,) = trips
    assert r["status"] == "closed" and r["start"] == "2026-02-02" and r["end"] == "2026-03-02"
    assert r["vs_hold"] == pytest.approx((18 - 12) * 10)      # the user's 10/20/18/12 example


def test_several_sells_and_buys_accumulate_and_extra_shares_are_a_new_buy():
    trips = round_trips([t(1, "BUY", 30, 10, "2026-01-02"), t(2, "SELL", 10, 20, "2026-02-02"),
                         t(3, "SELL", 10, 18, "2026-02-03"), t(4, "BUY", 5, 15, "2026-02-10"),
                         t(5, "BUY", 25, 14, "2026-02-11")], CLOSES)
    (r,) = trips
    assert r["shares_sold"] == 20 and r["shares_rebought"] == 20
    assert r["vs_hold"] == pytest.approx(10 * 20 + 10 * 18 - (5 * 15 + 15 * 14))


def test_not_rebought_within_the_window_is_a_reduction_and_unfinished_is_open():
    late = pd.bdate_range("2026-02-02", periods=REBUY_WINDOW + 5)[-1].strftime("%Y-%m-%d")
    trips = round_trips([t(1, "BUY", 20, 10, "2026-01-02"), t(2, "SELL", 10, 18, "2026-02-02"),
                         t(3, "BUY", 10, 12, late)], CLOSES)
    assert [r["status"] for r in trips] == ["reduction"]
    (r,) = round_trips([t(1, "BUY", 20, 10, "2026-09-01"), t(2, "SELL", 10, 18, "2026-09-02")],
                       {"VTI": pd.Series([16.0], index=[pd.Timestamp("2026-09-03")])})
    assert r["status"] == "open" and r["vs_hold"] == pytest.approx((18 - 16) * 10)


def test_tw_trip_includes_estimated_fees_and_tax_when_none_were_entered():
    trips = round_trips([t(1, "BUY", 2000, 100, "2026-01-02", sym="0050"), t(2, "SELL", 1000, 110, "2026-02-02", sym="0050"),
                         t(3, "BUY", 1000, 100, "2026-02-09", sym="0050")],
                        {"0050": pd.Series([100.0] * 50, index=pd.bdate_range("2026-01-01", periods=50))})
    fees = 110_000 * (0.001425 + 0.001) + 100_000 * 0.001425
    assert trips[0]["fees"] == pytest.approx(fees) and trips[0]["vs_hold"] == pytest.approx(10_000 - fees)
    assert trade_cost(t(9, "SELL", 1, 100, "2026-01-01", sym="2330")) == pytest.approx(100 * (0.001425 + 0.003))


# ---- dip buying -----------------------------------------------------------------------------

def test_dip_buying_uses_the_same_money_and_reports_both_baselines():
    idx = pd.bdate_range("2020-01-01", periods=500)
    px = pd.Series([100 * (1.0004 ** i) * (0.85 if 200 <= i < 260 else 1.0) for i in range(500)], index=idx)
    r = compare(px, monthly=1000, reserve=200, trigger=0.10, add_frac=None)
    s = r["strategies"]
    assert s["invest_now"]["deposited"] == s["dip"]["deposited"] == s["idle_cash"]["deposited"]
    assert s["dip"]["adds"] and s["dip"]["final"] > s["idle_cash"]["final"]
