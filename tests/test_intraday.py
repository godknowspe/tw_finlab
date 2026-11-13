import datetime

import pandas as pd
import pytest

from src.services.intraday import CallGate, IntradayBars, RateLimited, bars_from_kbars, resample


def kb(rows):
    cols = list(zip(*rows))
    return {"ts": [pd.Timestamp(t) for t in cols[0]], "Open": cols[1], "High": cols[2], "Low": cols[3], "Close": cols[4], "Volume": cols[5]}


def test_kbars_are_relabelled_to_minute_start_in_shares_and_idle_minutes_dropped():
    bars = bars_from_kbars(kb([("2026-11-13 09:01:00", 102.85, 103.2, 102.85, 103.1, 5579),
                               ("2026-11-13 09:02:00", 103.1, 103.1, 103.1, 103.1, 0),
                               ("2026-11-13 09:03:00", 103.05, 103.3, 103.0, 103.3, 1704)]))
    assert list(bars) == [pd.Timestamp("2026-11-13 09:00"), pd.Timestamp("2026-11-13 09:02")]
    first = bars[pd.Timestamp("2026-11-13 09:00")]
    assert first["volume"] == 5_579_000 and first["open"] == 102.85 and first["close"] == 103.1


def test_ticks_build_a_minute_bar_and_ignore_simulated_and_off_session_ticks():
    b = IntradayBars()
    b.add_tick("2026-11-13 09:00:05", 100.0, 3)
    b.add_tick("2026-11-13 09:00:40", 101.0, 2)
    b.add_tick("2026-11-13 09:00:50", 99.5, 1)
    b.add_tick("2026-11-13 08:59:59", 50.0, 9, simtrade=True)     # pre-open simulated match
    b.add_tick("2026-11-13 08:59:59", 50.0, 9)                    # before the session
    b.add_tick("2026-11-13 13:31:00", 50.0, 9)                    # after the closing auction
    df = b.frame()
    assert len(df) == 1
    assert df.iloc[0].to_dict() == {"open": 100.0, "high": 101.0, "low": 99.5, "close": 99.5, "volume": 6000.0}


def test_ticks_seen_while_the_backfill_was_in_flight_survive_it():
    b = IntradayBars()
    b.add_tick("2026-11-13 09:05:10", 101.0, 1)                   # arrives before the response lands
    backfill = bars_from_kbars(kb([("2026-11-13 09:01:00", 100, 100, 100, 100, 5),
                                   ("2026-11-13 09:02:00", 100, 100, 100, 100, 5)]))
    b.reset(datetime.date(2026, 11, 13), backfill)
    assert [t.strftime("%H:%M") for t in b.frame().index] == ["09:00", "09:01", "09:05"]
    b.add_tick("2026-11-14 09:00:00", 1.0, 1)                     # another day is not mixed in
    assert len(b.frame()) == 3


def test_resample_anchors_at_the_open():
    b = IntradayBars()
    for m, p in [("09:00", 100), ("09:04", 102), ("09:05", 101), ("09:09", 99)]:
        b.add_tick(f"2026-11-13 {m}:10", p, 1)
    out = resample(b.frame(), 5)
    assert [t.strftime("%H:%M") for t in out.index] == ["09:00", "09:05"]
    assert out.iloc[0]["high"] == 102 and out.iloc[1]["close"] == 99


def test_gate_refuses_a_burst_then_recovers_and_caps_kbars_per_day():
    now = [0.0]
    day = [datetime.date(2026, 11, 13)]
    g = CallGate(budget=3, window=10, daily=2, clock=lambda: now[0], today=lambda: day[0])
    g.acquire("kbars"); g.acquire("kbars"); g.acquire("snap")
    with pytest.raises(RateLimited):
        g.acquire("snap")                                          # 4th call inside the window
    now[0] = 11
    with pytest.raises(RateLimited):
        g.acquire("kbars")                                         # window is free but 2 kbars used today
    g.acquire("snap")
    day[0] = datetime.date(2026, 11, 14)
    g.acquire("kbars")                                             # new day, new allowance


class FakeApi:
    def __init__(self):
        self.kbars_calls, self.subscribed, self.unsubscribed, self.callback = 0, [], [], None
        self.Contracts = type("C", (), {"Stocks": {c: c for c in ("0050", "2330", *[f"{n:04d}" for n in range(1101, 1115)])}})()

    def set_on_tick_stk_v1_callback(self, cb):
        self.callback = cb

    def subscribe(self, contract, **_):
        self.subscribed.append(contract)

    def unsubscribe(self, contract, **_):
        self.unsubscribed.append(contract)

    def kbars(self, contract, start, end):
        self.kbars_calls += 1
        return kb([(f"{start} 09:01:00", 100, 101, 99, 100.5, 10)])


def test_service_backfills_once_per_symbol_per_day_and_streams_ticks_into_the_bars():
    from src.services.intraday import IntradayService
    day = [datetime.date(2026, 11, 13)]
    api = FakeApi()
    svc = IntradayService(api, today=lambda: day[0])
    for _ in range(50):
        bars = svc.get("0050")                                    # 50 chart refreshes
    assert api.kbars_calls == 1 and api.subscribed == ["0050"]

    tick = type("T", (), {"code": "0050", "datetime": datetime.datetime(2026, 11, 13, 9, 1, 30), "close": 102.0, "volume": 4, "simtrade": 0})()
    api.callback("TWSE", tick)
    assert bars.frame().iloc[-1].to_dict() == {"open": 102.0, "high": 102.0, "low": 102.0, "close": 102.0, "volume": 4000.0}

    day[0] = datetime.date(2026, 11, 14)
    svc.get("0050")                                               # next trading day: one more backfill
    assert api.kbars_calls == 2


def test_service_caps_subscriptions_and_drops_the_oldest():
    from src.services.intraday import MAX_SUBSCRIPTIONS, IntradayService
    api = FakeApi()
    svc = IntradayService(api, gate=CallGate(budget=1000, daily=1000), today=lambda: datetime.date(2026, 11, 13))
    codes = [f"{n:04d}" for n in range(1101, 1101 + MAX_SUBSCRIPTIONS + 2)]
    for c in codes:
        svc.get(c)
    assert api.unsubscribed == codes[:2] and len(svc._symbols) == MAX_SUBSCRIPTIONS
