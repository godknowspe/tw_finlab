import numpy as np
import pandas as pd
import pytest

from src.domain import regime


def bars_from(closes, spread=0.01):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"open": closes, "high": closes * (1 + spread), "low": closes * (1 - spread), "close": closes, "volume": 1.0}, index=idx)


def trending(n, drift, noise=0.004, seed=1, start=100.0):
    rng = np.random.default_rng(seed)
    return start * np.cumprod(1 + drift + rng.normal(0, noise, n))


def test_steady_uptrend_is_up_and_steady_downtrend_is_down():
    up = regime.describe(bars_from(trending(400, 0.002)))
    down = regime.describe(bars_from(trending(400, -0.002)))
    assert up["trend"] == "up" and up["strength"] == "strong" and up["trend_label"] == "多頭"
    assert down["trend"] == "down" and down["trend_label"] == "空頭"


def test_flat_noise_is_not_called_a_trend():
    rng = np.random.default_rng(3)
    sideways = 100 + np.cumsum(rng.normal(0, 0.3, 400)) * 0
    sideways = 100 + 3 * np.sin(np.linspace(0, 40 * np.pi, 400)) + rng.normal(0, 0.2, 400)
    d = regime.describe(bars_from(sideways))
    assert d["trend"] == "mixed" and d["trend_label"] == "多空不明"


def test_volatility_is_ranked_against_the_instruments_own_history():
    calm = trending(500, 0.0005, noise=0.003)
    wild_tail = np.concatenate([calm, calm[-1] * np.cumprod(1 + np.random.default_rng(5).normal(0, 0.03, 30))])
    b = bars_from(wild_tail)
    b["high"], b["low"] = b["close"] * 1.03, b["close"] * 0.97
    b.iloc[:500, b.columns.get_loc("high")] = b["close"].iloc[:500] * 1.003
    b.iloc[:500, b.columns.get_loc("low")] = b["close"].iloc[:500] * 0.997
    assert regime.describe(b)["vol"] == "wild"
    assert regime.describe(bars_from(calm))["vol"] in ("calm", "normal")


def test_a_new_label_needs_confirm_days_in_a_row():
    seq = ["up"] * 5 + ["mixed", "mixed", "up", "up", "up"]          # two stray days do not flip it
    assert regime._confirm(seq)[-1] == "up" and set(regime._confirm(seq)) == {"up"}
    seq = ["up"] * 5 + ["down"] * regime.CONFIRM_DAYS
    out = regime._confirm(seq)
    assert out[4] == "up" and out[-1] == "down" and out[-2] == "up"      # flips on the CONFIRM_DAYS-th day
    seq = ["up"] * 3 + ["down", "mixed", "down", "mixed", "down"]       # alternating candidates reset the run
    assert set(regime._confirm(seq)) == {"up"}


def test_pending_note_appears_while_the_raw_reading_disagrees():
    closes = np.concatenate([trending(400, 0.002), [0.0]])
    closes[-1] = closes[-2] * 0.9                                       # one hard down day under the 50-day line
    d = regime.describe(bars_from(closes))
    assert d["trend"] == "up" and d["pending"] and "連續" in d["pending"]


def test_too_little_history_gives_no_verdict():
    assert regime.describe(bars_from(trending(regime.MIN_BARS - 1, 0.001))) is None
    assert regime.forward_stats(bars_from(trending(120, 0.001))) == {}


def test_forward_stats_use_confirmed_labels_and_report_the_baseline():
    st = regime.forward_stats(bars_from(trending(900, 0.001, noise=0.01, seed=7)), horizon=20)
    assert st["all"]["days"] > 0 and st["all"]["episodes"] == 1
    assert st["trend:up"]["days"] + st["trend:down"]["days"] + st["trend:mixed"]["days"] == st["all"]["days"]
    assert 0 <= st["all"]["win_rate"] <= 1


def test_mixed_state_says_which_way_the_disagreement_goes():
    pullback = np.concatenate([trending(420, 0.002), trending(1, 0, start=0)[:0], np.linspace(0, 0, 0)])
    closes = np.concatenate([trending(400, 0.002), 0.85 * trending(400, 0.002)[-1] * np.ones(15)])
    d = regime.describe(bars_from(closes))
    assert d["trend"] == "mixed" and d["phase"] == "長期向上、短期回檔"


def test_trips_are_grouped_by_the_state_on_the_day_of_the_first_sale():
    h = regime.history(bars_from(np.concatenate([trending(400, 0.002), 0.8 * trending(400, 0.002)[-1] * np.ones(40)])))
    early, late = h.index[300].strftime("%Y-%m-%d"), h.index[-1].strftime("%Y-%m-%d")
    trips = [{"symbol": "X", "start": early, "status": "closed", "currency": "TWD", "vs_hold": 100.0},
             {"symbol": "X", "start": late, "status": "closed", "currency": "TWD", "vs_hold": -40.0},
             {"symbol": "X", "start": late, "status": "open", "currency": "TWD", "vs_hold": 999.0},
             {"symbol": "Y", "start": late, "status": "closed", "currency": "USD", "vs_hold": 5.0}]   # no history for Y
    out = regime.trips_by_state(trips, {"X": h})
    by = {(g["trend"], g["vol"]): g for g in out["groups"]}
    assert sum(c["trips"] for g in out["groups"] for c in g["currencies"].values()) == 2          # open and unknown-symbol trips left out
    assert out["trips"][3]["state"] is None
    assert {k[0] for k in by} == {out["trips"][0]["state"]["trend"], out["trips"][1]["state"]["trend"]}
    assert out["trips"][0]["state"]["trend"] == "up" and out["trips"][1]["state"]["trend"] != "up"
