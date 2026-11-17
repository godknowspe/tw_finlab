"""Describe the current market state of one instrument from daily bars. Pure functions, no I/O.

This DESCRIBES; it does not predict. Two independent axes:
  trend       up / down / mixed, from close vs the 50- and 200-day averages and a 200-day line
              that is actually sloping; ADX only reports how strong the move is
  volatility  calm / normal / wild, from ATR% ranked against the instrument's own last 2 years

Moving averages lag and flip around the 200-day line, so a new label only replaces the current
one after it has held for CONFIRM_DAYS sessions. `history()` replays the same rules day by day
so the statistics below use labels that were knowable at the time, never the final answer.
"""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

FAST, SLOW = 50, 200
SLOPE_DAYS = 20
ADX_PERIOD = 14
ADX_TREND = 20            # below this the market is drifting, not trending
MIN_SLOPE = 0.005         # the 200-day line must have moved 0.5% in SLOPE_DAYS: a flat line is no direction
VOL_WINDOW = 504          # ~2 years of sessions for the volatility percentile
CALM_PCT, WILD_PCT = 25, 75
CONFIRM_DAYS = 3
MIN_BARS = SLOW + SLOPE_DAYS

TREND_LABEL = {"up": "多頭", "down": "空頭", "mixed": "多空不明"}
VOL_LABEL = {"calm": "平靜", "normal": "正常", "wild": "劇烈"}


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def indicators(bars: pd.DataFrame) -> pd.DataFrame:
    c, h, l = bars["close"], bars["high"], bars["low"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    up, down = h.diff(), -l.diff()
    plus = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=bars.index)
    minus = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=bars.index)
    atr = _wilder(tr, ADX_PERIOD)
    pdi, mdi = 100 * _wilder(plus, ADX_PERIOD) / atr, 100 * _wilder(minus, ADX_PERIOD) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    out = pd.DataFrame(index=bars.index)
    out["close"] = c
    out["ma_fast"], out["ma_slow"] = c.rolling(FAST).mean(), c.rolling(SLOW).mean()
    out["slope"] = out["ma_slow"] / out["ma_slow"].shift(SLOPE_DAYS) - 1
    out["adx"] = _wilder(dx, ADX_PERIOD)
    out["atr_pct"] = atr / c
    out["vol_rank"] = out["atr_pct"].rolling(VOL_WINDOW, min_periods=120).apply(lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
    return out


def raw_trend(row) -> Optional[str]:
    if pd.isna(row["ma_slow"]) or pd.isna(row["slope"]):
        return None
    above_slow, above_fast = row["close"] > row["ma_slow"], row["close"] > row["ma_fast"]
    stacked_up, stacked_down = row["ma_fast"] > row["ma_slow"], row["ma_fast"] < row["ma_slow"]
    if above_slow and stacked_up and row["slope"] > MIN_SLOPE and above_fast:
        return "up"
    if not above_slow and stacked_down and row["slope"] < -MIN_SLOPE and not above_fast:
        return "down"
    return "mixed"


def raw_vol(row) -> Optional[str]:
    if pd.isna(row["vol_rank"]):
        return None
    return "wild" if row["vol_rank"] >= WILD_PCT else "calm" if row["vol_rank"] <= CALM_PCT else "normal"


def _confirm(raw: List[Optional[str]]) -> List[Optional[str]]:
    """A new label is adopted only after CONFIRM_DAYS identical raw labels in a row."""
    out, current, cand, run = [], None, None, 0
    for r in raw:
        if r is None:
            out.append(None)
            continue
        if current is None:
            current = r
        elif r == current:
            cand, run = None, 0
        else:
            run = run + 1 if r == cand else 1
            cand = r
            if run >= CONFIRM_DAYS:
                current, cand, run = r, None, 0
        out.append(current)
    return out


def history(bars: pd.DataFrame) -> pd.DataFrame:
    """Per-session indicators plus the confirmed `trend` and `vol` labels."""
    ind = indicators(bars)
    ind["trend"] = _confirm([raw_trend(r) for _, r in ind.iterrows()])
    ind["vol"] = _confirm([raw_vol(r) for _, r in ind.iterrows()])
    return ind


def phase(row, trend: str) -> str:
    """One-line reading that separates the long-term direction (200-day line) from the recent
    move (close vs the 50-day line), because 'mixed' alone hides which way the disagreement goes."""
    long_up, long_down = row["slope"] > MIN_SLOPE, row["slope"] < -MIN_SLOPE
    below_fast, above_fast = row["close"] < row["ma_fast"], row["close"] > row["ma_fast"]
    if trend == "up":
        return "多頭延續"
    if trend == "down":
        return "空頭延續"
    if long_up:
        return "長期向上、短期回檔" if below_fast else "長期向上、尚未站回"
    if long_down:
        return "長期向下、短期反彈" if above_fast else "長期向下、盤整"
    return "長期持平、區間震盪"


def _pct(v) -> str:
    return f"{v * 100:+.1f}%"


def describe(bars: pd.DataFrame) -> Optional[dict]:
    """Current state with the numbers behind it, or None without enough history."""
    bars = bars.dropna(subset=["close", "high", "low"])
    if len(bars) < MIN_BARS:
        return None
    h = history(bars)
    last = h.iloc[-1]
    if last["trend"] is None or pd.isna(last["trend"]):
        return None
    trend, vol = last["trend"], last["vol"] if isinstance(last["vol"], str) else "normal"
    strength = "strong" if last["adx"] >= ADX_TREND else "weak"
    facts = [
        f"收盤 {last['close']:.2f}，相對 {SLOW} 日線 {_pct(last['close'] / last['ma_slow'] - 1)}、{FAST} 日線 {_pct(last['close'] / last['ma_fast'] - 1)}",
        f"{SLOW} 日線 {SLOPE_DAYS} 日斜率 {_pct(last['slope'])}，ADX {last['adx']:.0f}（{'趨勢明確' if strength == 'strong' else '趨勢不強，偏盤整'}）",
        f"ATR {last['atr_pct'] * 100:.2f}%，落在自己近 2 年的第 {last['vol_rank']:.0f} 百分位",
    ]
    days_in_state = int((h["trend"].iloc[::-1] == trend).cumprod().sum())
    return {
        "trend": trend, "trend_label": TREND_LABEL[trend], "phase": phase(last, trend), "strength": strength,
        "vol": vol, "vol_label": VOL_LABEL[vol],
        "days_in_state": days_in_state, "facts": facts,
        "pending": _pending(h, trend),
        "numbers": {k: (None if pd.isna(last[k]) else round(float(last[k]), 4)) for k in ("close", "ma_fast", "ma_slow", "slope", "adx", "atr_pct", "vol_rank")},
    }


def _pending(h: pd.DataFrame, trend: str) -> Optional[str]:
    """Say so when the raw reading already disagrees with the confirmed label."""
    raw = raw_trend(h.iloc[-1])
    if raw is not None and raw != trend:
        return f"目前原始訊號已偏向{TREND_LABEL[raw]}，需連續 {CONFIRM_DAYS} 日才會改標籤"
    return None


def forward_stats(bars: pd.DataFrame, horizon: int = 20) -> Dict[str, dict]:
    """What followed each confirmed state: median and mean forward return over `horizon`
    sessions, win rate, and the sample count, next to the all-days baseline. Overlapping
    windows make neighbouring days highly correlated, so `days` overstates how much evidence
    there is; `episodes` counts separate stretches in the state."""
    bars = bars.dropna(subset=["close", "high", "low"])
    if len(bars) < MIN_BARS + horizon:
        return {}
    h = history(bars)
    fwd = bars["close"].shift(-horizon) / bars["close"] - 1
    df = pd.DataFrame({"trend": h["trend"], "vol": h["vol"], "fwd": fwd}).dropna()

    def summarize(mask) -> dict:
        r = df.loc[mask, "fwd"]
        runs = int((mask & ~mask.shift(fill_value=False)).sum())
        return {"days": int(len(r)), "episodes": runs, "median": round(float(r.median()), 4) if len(r) else None,
                "mean": round(float(r.mean()), 4) if len(r) else None, "win_rate": round(float((r > 0).mean()), 3) if len(r) else None}

    out = {"all": summarize(pd.Series(True, index=df.index))}
    for t in TREND_LABEL:
        out[f"trend:{t}"] = summarize(df["trend"] == t)
    for v in VOL_LABEL:
        out[f"vol:{v}"] = summarize(df["vol"] == v)
    return out


def state_on(hist: pd.DataFrame, day: str) -> Optional[dict]:
    """The confirmed labels as they stood on `day` (the last session on or before it)."""
    upto = hist.loc[: pd.Timestamp(day)]
    if upto.empty:
        return None
    row = upto.iloc[-1]
    if not isinstance(row["trend"], str):
        return None
    return {"trend": row["trend"], "vol": row["vol"] if isinstance(row["vol"], str) else "normal", "phase": phase(row, row["trend"])}


def trips_by_state(trips: List[dict], histories: Dict[str, pd.DataFrame]) -> dict:
    """Tag each finished round trip with the state of its own symbol on the day of the first
    sale, then total 'result vs holding' per state. Only closed trips count; open ones are
    still moving. Amounts stay per currency because TWD and USD must not be added."""
    tagged, groups = [], {}
    for r in trips:
        h = histories.get(r["symbol"])
        st = state_on(h, r["start"]) if h is not None else None
        tagged.append({**r, "state": st})
        if r["status"] != "closed" or st is None:
            continue
        g = groups.setdefault(f"{st['trend']}|{st['vol']}", {"trend": st["trend"], "vol": st["vol"], "currencies": {}})
        c = g["currencies"].setdefault(r["currency"], {"trips": 0, "won": 0, "vs_hold": 0.0})
        c["trips"] += 1
        c["won"] += r["vs_hold"] > 0
        c["vs_hold"] = round(c["vs_hold"] + r["vs_hold"], 2)
    return {"trips": tagged, "groups": sorted(groups.values(), key=lambda g: (g["trend"], g["vol"]))}
