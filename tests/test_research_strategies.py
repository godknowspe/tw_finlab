import numpy as np
import pandas as pd
import pytest

from research.twii_regime import strategies as S
from research.twii_regime.engine import Costs, run
from research.twii_regime.metrics import episodes, paired_block_bootstrap, summarize

NO_COST = Costs(fee=0.0, tax=0.0, slippage=0.0, cash_rate=0.0)


def walk(n, drift=0.0004, noise=0.01, seed=2, start="2015-01-02"):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + drift + rng.normal(0, noise, n))
    idx = pd.bdate_range(start, periods=n)
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
    df = pd.DataFrame({"open": o, "close": c}, index=idx)
    df["high"], df["low"] = df[["open", "close"]].max(axis=1) * 1.003, df[["open", "close"]].min(axis=1) * 0.997
    df["volume"], df["dividend"] = 1.0, 0.0
    return df


@pytest.mark.parametrize("name", [k for k in S.STRATEGIES if k[0] in "BCDEF"])
def test_signals_are_prefix_invariant_so_they_cannot_see_the_future(name):
    df = walk(700)
    full = S.STRATEGIES[name](df)
    cut = 500
    part = S.STRATEGIES[name](df.iloc[:cut])
    pd.testing.assert_series_equal(full.iloc[:cut], part, check_names=False)


def test_signals_stay_flat_until_the_window_is_full():
    df = walk(300)
    assert S.above_ma(df).iloc[:199].eq(0).all() and S.momentum(df).iloc[:252].eq(0).all()
    assert S.golden_cross(df).iloc[:199].eq(0).all()


def test_vol_target_never_exceeds_one_and_shrinks_when_volatility_rises():
    calm, wild = walk(300, noise=0.004), walk(300, noise=0.03)
    assert S.vol_target(calm).dropna().max() <= 1.0
    assert S.vol_target(wild).iloc[-1] < S.vol_target(calm).iloc[-1]


def test_buy_and_hold_and_always_invested_strategies_have_no_win_rate():
    df = walk(400)
    res = run(df, S.buy_hold(df), NO_COST, start=df.index[0])
    s = summarize(res)
    assert s["win_rate"] is None and s["episodes_closed"] == 0 and s["episodes_open"] == 1
    v = summarize(run(df, S.vol_target(df).clip(lower=0.2), NO_COST, start=df.index[260], rebalance_every=5))
    assert v["win_rate"] is None


def test_win_rate_counts_only_closed_flat_invested_flat_episodes():
    df = bars = walk(10, drift=0, noise=0)
    px = [100, 100, 110, 110, 100, 100, 90, 100, 100, 100]
    df["open"] = df["close"] = px
    df["high"] = df["low"] = px
    sig = pd.Series([0, 1, 1, 0, 0, 1, 1, 0, 1, 1], index=df.index, dtype=float)
    res = run(df, sig, NO_COST, start=df.index[0])
    s = summarize(res)
    eps = episodes(res["equity"], res["weight"], res["fills"])
    assert [e["closed"] for e in eps] == [True, True, False]            # the last stretch is still open
    assert s["episodes_closed"] == 2 and s["episodes_open"] == 1
    assert s["win_rate"] == pytest.approx(0.5)                          # first episode wins, second loses
    assert s["avg_win"] > 0 > s["avg_loss"] and s["payoff"] == pytest.approx(s["avg_win"] / abs(s["avg_loss"]))


def test_cash_only_has_no_risk_and_no_sharpe():
    df = walk(300)
    s = summarize(run(df, S.cash_only(df), NO_COST, start=df.index[0]))
    assert s["vol"] == 0 and s["sharpe"] is None and s["max_drawdown"] == 0 and s["calmar"] is None


def test_bootstrap_compares_the_same_sessions_for_every_strategy():
    df = walk(900, seed=4)
    rets = {}
    for k in ("A 買進持有", "B 站上200日線", "G 現金"):
        res = run(df, S.STRATEGIES[k](df), NO_COST, start=df.index[260])
        rets[k] = res["equity"].pct_change().fillna(0)
    out = paired_block_bootstrap(pd.DataFrame(rets), base="A 買進持有", block=60, n=200)
    assert set(out) == {"B 站上200日線", "G 現金"}
    lo, mid, hi = out["G 現金"]["d_mdd"]
    assert lo <= mid <= hi and mid >= 0                                  # holding nothing never draws down more than buy-and-hold
