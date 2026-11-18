"""Performance and trade-episode statistics.

Win rate counts finished episodes only: flat -> invested -> flat again. Strategies that never
go flat (buy and hold, volatility targeting that always holds something) have no natural
episode, so their win rate is None, never 0% or 100%. An episode still open at the end is marked
to market in equity but is not counted in the win rate.
"""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ANNUAL = 252


def episodes(equity: pd.Series, weight: pd.Series, fills: List[dict], eps: float = 1e-9) -> List[dict]:
    """One row per flat->invested->flat stretch, using the actual fills. Return is the change in
    equity from the session before entry (after the fill) to the session of the exit."""
    out, start, entry_eq, entry_fill = [], None, None, None
    fills_by_day = {}
    for f in fills:
        fills_by_day.setdefault(f["date"], []).append(f)
    idx = list(equity.index)
    held = False
    for i, day in enumerate(idx):
        w = weight.iloc[i]
        prev_w = weight.iloc[i - 1] if i else 0.0
        day_fills = fills_by_day.get(day, [])
        if not held and any(f["side"] == "BUY" for f in day_fills):
            held, start, entry_fill = True, day, next(f for f in day_fills if f["side"] == "BUY")
            entry_eq = equity.iloc[i - 1] if i else 1.0
        if held and w <= eps and any(f["side"] == "SELL" for f in day_fills):
            exit_fill = [f for f in day_fills if f["side"] == "SELL"][-1]
            out.append({"entry": start, "exit": day, "entry_price": entry_fill["price"], "exit_price": exit_fill["price"],
                        "ret": float(equity.iloc[i] / entry_eq - 1), "sessions": i - idx.index(start) + 1, "closed": True})
            held = False
    if held:
        out.append({"entry": start, "exit": idx[-1], "entry_price": entry_fill["price"], "exit_price": None,
                    "ret": float(equity.iloc[-1] / entry_eq - 1), "sessions": len(idx) - idx.index(start), "closed": False})
    return out


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def _longest_underwater(equity: pd.Series) -> int:
    under = (equity < equity.cummax()).astype(int)
    best = run = 0
    for v in under:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def summarize(res: dict, rf: float = 0.0) -> Dict:
    eq, w = res["equity"], res["weight"]
    ret = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else None
    vol = float(ret.std() * np.sqrt(ANNUAL)) if len(ret) > 1 else None
    excess = ret - rf / ANNUAL
    sharpe = float(excess.mean() / ret.std() * np.sqrt(ANNUAL)) if ret.std() and ret.std() > 0 else None
    mdd = float(drawdown(eq).min())
    eps = episodes(eq, w, res["fills"])
    closed = [e for e in eps if e["closed"]]
    wins, losses = [e["ret"] for e in closed if e["ret"] > 0], [e["ret"] for e in closed if e["ret"] < 0]
    gain, loss = sum(wins), -sum(losses)
    avg_win = float(np.mean(wins)) if wins else None
    avg_loss = float(np.mean(losses)) if losses else None
    return {
        "final": float(eq.iloc[-1]), "cagr": cagr, "vol": vol, "sharpe": sharpe, "max_drawdown": mdd,
        "calmar": (cagr / abs(mdd)) if cagr is not None and mdd < 0 else None,
        "longest_underwater_sessions": _longest_underwater(eq),
        "exposure_avg": float(w.mean()), "invested_share": float((w > 1e-9).mean()),
        "fills": len(res["fills"]), "costs_paid": res["costs_paid"],
        "episodes_closed": len(closed), "episodes_open": len(eps) - len(closed),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "payoff": (avg_win / abs(avg_loss)) if avg_win is not None and avg_loss else None,
        "profit_factor": (gain / loss) if loss > 0 else None,
        "avg_sessions": float(np.mean([e["sessions"] for e in closed])) if closed else None,
        "best_episode_share": (max(wins) / gain) if gain > 0 else None,
    }


def paired_block_bootstrap(returns: pd.DataFrame, base: str, block: int = 120, n: int = 2000, seed: int = 11) -> Dict[str, dict]:
    """Resample the SAME sessions for every strategy (columns = daily net returns) in moving
    blocks and report each strategy's difference to `base` in CAGR and max drawdown, as a 5-95%
    range. It measures how unsure the observed sample leaves us; it does not create new market
    history, and drawdown intervals in particular are not a bound on future losses."""
    rng = np.random.default_rng(seed)
    arr = returns.to_numpy()
    T = len(arr)
    starts_max = T - block
    cols = list(returns.columns)
    d_cagr = {c: [] for c in cols}
    d_mdd = {c: [] for c in cols}
    for _ in range(n):
        picks = []
        while sum(len(p) for p in picks) < T:
            s = int(rng.integers(0, starts_max + 1))
            picks.append(np.arange(s, s + block))
        idx = np.concatenate(picks)[:T]
        path = np.cumprod(1 + arr[idx], axis=0)
        years = T / ANNUAL
        cagr = path[-1] ** (1 / years) - 1
        mdd = (path / np.maximum.accumulate(path, axis=0) - 1).min(axis=0)
        b = cols.index(base)
        for j, c in enumerate(cols):
            d_cagr[c].append(cagr[j] - cagr[b])
            d_mdd[c].append(mdd[j] - mdd[b])
    q = lambda v: [float(np.percentile(v, 5)), float(np.percentile(v, 50)), float(np.percentile(v, 95))]
    return {c: {"d_cagr": q(d_cagr[c]), "d_mdd": q(d_mdd[c]), "p_better_cagr": float(np.mean(np.array(d_cagr[c]) > 0))} for c in cols if c != base}
