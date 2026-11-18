"""Target-weight signals from a signal series' bars. Each value is decided at that date's close.

All parameters are the textbook values, fixed before seeing results. They are not tuned.
"""
import numpy as np
import pandas as pd

from src.domain import regime

SLOW, FAST, MOM = 200, 50, 252
VOL_WINDOW, VOL_TARGET, ANNUAL = 20, 0.10, 252


def buy_hold(bars: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=bars.index)


def cash_only(bars: pd.DataFrame) -> pd.Series:
    return pd.Series(0.0, index=bars.index)


def half_half(bars: pd.DataFrame) -> pd.Series:
    return pd.Series(0.5, index=bars.index)


def above_ma(bars: pd.DataFrame, n: int = SLOW) -> pd.Series:
    """B: hold while the close is above its n-session average."""
    c = bars["close"]
    return (c > c.rolling(n).mean()).astype(float).where(c.rolling(n).count() == n, 0.0)


def golden_cross(bars: pd.DataFrame, fast: int = FAST, slow: int = SLOW) -> pd.Series:
    """C: hold while the fast average is above the slow one (state, not the crossing event, so a
    start inside an uptrend is already invested)."""
    c = bars["close"]
    f, s = c.rolling(fast).mean(), c.rolling(slow).mean()
    return (f > s).astype(float).where(s.notna(), 0.0)


def momentum(bars: pd.DataFrame, n: int = MOM) -> pd.Series:
    """D: hold while the return over the last n sessions is positive."""
    c = bars["close"]
    return (c / c.shift(n) - 1 > 0).astype(float).where(c.shift(n).notna(), 0.0)


def vol_target(bars: pd.DataFrame, target: float = VOL_TARGET, window: int = VOL_WINDOW) -> pd.Series:
    """E: scale exposure so the recent realised volatility would equal `target` a year, capped
    at 100% (no leverage). Realised volatility is the standard deviation of daily returns, in
    annual terms; ATR is a range measure and is not used here."""
    r = bars["close"].pct_change(fill_method=None)
    sigma = r.rolling(window).std() * np.sqrt(ANNUAL)
    return (target / sigma).clip(upper=1.0).where(sigma > 0, 1.0).where(sigma.notna(), 0.0)


def regime_up(bars: pd.DataFrame) -> pd.Series:
    """F: the dashboard's existing trend label, frozen as it is (not edited for this study)."""
    h = regime.history(bars)
    return (h["trend"] == "up").astype(float)


STRATEGIES = {
    "A 買進持有": buy_hold,
    "B 站上200日線": above_ma,
    "C 50/200黃金交叉": golden_cross,
    "D 12個月動能": momentum,
    "E 波動目標10%": vol_target,
    "F 現有趨勢標籤": regime_up,
    "G 現金": cash_only,
    "H 50%持有+50%現金": half_half,
}
