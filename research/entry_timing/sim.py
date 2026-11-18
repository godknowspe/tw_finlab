"""Entry timing for money that is not invested yet: lump sum vs spreading it out vs waiting
for drawdowns. Pure functions over a price (or total-return) series.

Every strategy starts with 1.0 of cash on day i and is valued at day i+H. Windows start every
`step` sessions, so neighbouring windows overlap heavily: the number of windows overstates the
evidence; `span / horizon` is closer to the number of independent looks.

Idealisations: a drawdown tranche buys at the close of the day the drawdown from the running
peak (since the window start) is first reached; there are no trading costs; idle cash earns the
given annual rate; tranches never triggered stay cash until the end of the window unless a
deadline forces them in.
"""
import numpy as np

SESSIONS_PER_MONTH = 21
YEAR = 252
LEVELS = np.round(np.arange(0.05, 0.80001, 0.05), 2)
_LEVEL_IDX = {float(l): i for i, l in enumerate(LEVELS)}


def windows(px: np.ndarray, horizon: int, step: int = 5):
    """Start indexes and, per start, the session offset at which each drawdown level is first
    reached (-1 if it never is within the horizon)."""
    starts = np.arange(0, len(px) - horizon, step)
    first = np.full((len(starts), len(LEVELS)), -1, dtype=int)
    for w, i in enumerate(starts):
        seg = px[i:i + horizon + 1]
        worst = np.maximum.accumulate(1 - seg / np.maximum.accumulate(seg))
        idx = np.searchsorted(worst, LEVELS - 1e-12, side="left")
        first[w] = np.where(idx < len(seg), idx, -1)
    return starts, first


def lump(px, starts, horizon):
    return px[starts + horizon] / px[starts]


def spread(px, starts, horizon, months: int, rate: float = 0.0):
    """Equal parts on day 0, 21, 42, ...; the rest waits as cash."""
    if SESSIONS_PER_MONTH * (months - 1) > horizon:
        raise ValueError(f"spreading over {months} months does not fit in a {horizon}-session horizon")
    end = px[starts + horizon]
    total = np.zeros(len(starts))
    for k in range(months):
        t = SESSIONS_PER_MONTH * k
        total += (1 / months) * (1 + rate) ** (t / YEAR) * end / px[starts + t]
    return total


def dip(px, first, starts, horizon, upfront: float, step: float, tranches: int, deadline_months: int = 0, rate: float = 0.0):
    """`upfront` of the money buys on day 0; the rest is split into `tranches`, tranche k
    buying when the drawdown from the running peak first reaches step*k. With a deadline,
    whatever has not triggered by then is bought on that day."""
    end = px[starts + horizon]
    per = (1 - upfront) / tranches
    total = upfront * end / px[starts]
    for k in range(1, tranches + 1):
        rel = first[:, _LEVEL_IDX[round(step * k, 2)]].copy()
        if deadline_months:
            d = min(SESSIONS_PER_MONTH * deadline_months, horizon)
            rel = np.where((rel < 0) | (rel > d), d, rel)
        bought = rel >= 0
        t = np.where(bought, rel, 0)
        total = total + np.where(bought, per * (1 + rate) ** (t / YEAR) * end / px[starts + t], per * (1 + rate) ** (horizon / YEAR))
    return total


def compare(final: np.ndarray, base: np.ndarray) -> dict:
    diff = final / base - 1
    up = base > 1
    q = lambda a, p: float(np.percentile(a, p)) if len(a) else None
    return {"windows": int(len(diff)), "win": float(np.mean(diff > 0)),
            "median": q(diff, 50), "mean": float(diff.mean()), "worst": float(diff.min()), "best": float(diff.max()),
            "p5": q(final, 5), "p50": q(final, 50), "p95": q(final, 95),
            "win_when_up": float(np.mean(diff[up] > 0)) if up.any() else None, "n_up": int(up.sum()),
            "win_when_down": float(np.mean(diff[~up] > 0)) if (~up).any() else None, "n_down": int((~up).sum())}
