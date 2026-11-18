"""Compute the strategy grid and write results.json.   python -m research.entry_timing.run"""
import itertools
import json
from pathlib import Path

import numpy as np

from research.entry_timing import sim
from research.twii_regime import data as D

OUT = Path(__file__).parent / "results.json"
HORIZONS = {"1年": 252, "3年": 252 * 3, "5年": 252 * 5}
SPREADS = [3, 6, 12]
UPFRONT = [0.0, 0.5, 0.7]
STEPS = [0.05, 0.10, 0.15, 0.20, 0.30]
TRANCHES = [2, 3]
DEADLINES = [0, 12]
RATES = {"現金0%": 0.0, "現金1%": 0.01}


def total_return_index(df):
    """Dividends reinvested at the close of the ex-date."""
    r = (df["close"] + df["dividend"]) / df["close"].shift()
    return r.fillna(1.0).cumprod()


def series_for(loaded):
    d = loaded["data"]
    return {"0050": total_return_index(d["0050.TW"].loc["2014-01-02":]), "^TWII": d["^TWII"]["close"].loc["1999-01-04":]}


def strategy_key(kind, **p):
    return json.dumps({"kind": kind, **p}, sort_keys=True, ensure_ascii=False)


def run():
    loaded = D.load()
    out = {"data": loaded["meta"], "horizons": list(HORIZONS), "rates": list(RATES), "symbols": {}}
    for sym, s in series_for(loaded).items():
        px = s.to_numpy()
        years = (s.index[-1] - s.index[0]).days / 365.25
        out["symbols"][sym] = {"first": str(s.index[0].date()), "last": str(s.index[-1].date()), "years": round(years, 1), "horizons": {}}
        for hn, H in HORIZONS.items():
            if len(px) <= H + 252:
                continue
            starts, first = sim.windows(px, H)
            base = sim.lump(px, starts, H)
            rows = {}
            # Per-window results for a few reference strategies, so the page can draw the spread of
            # outcomes (each point = one start date). Rounded to keep the file small.
            ref_fin = {"分12個月平均買": sim.spread(px, starts, H, 12, 0.0) if sim.SESSIONS_PER_MONTH * 11 <= H else None,
                       "全部等回撤（每跌10%加碼×3）": sim.dip(px, first, starts, H, 0.0, 0.10, 3),
                       "先買一半＋每跌10%加碼×2": sim.dip(px, first, starts, H, 0.5, 0.10, 2)}
            paths = {name: [round(float(x), 3) for x in (f / base - 1)] for name, f in ref_fin.items() if f is not None}
            for rn, rate in RATES.items():
                cell = {}
                for m in SPREADS:
                    if sim.SESSIONS_PER_MONTH * (m - 1) <= H:
                        cell[strategy_key("spread", months=m)] = sim.compare(sim.spread(px, starts, H, m, rate), base)
                for up, st, tr, dl in itertools.product(UPFRONT, STEPS, TRANCHES, DEADLINES):
                    if round(st * tr, 2) > 0.80:
                        continue
                    fin = sim.dip(px, first, starts, H, up, st, tr, deadline_months=dl, rate=rate)
                    c = sim.compare(fin, base)
                    c["invested_share"] = float(np.mean(first[:, [sim._LEVEL_IDX[round(st * k, 2)] for k in range(1, tr + 1)]] >= 0))
                    cell[strategy_key("dip", upfront=up, step=st, tranches=tr, deadline=dl)] = c
                rows[rn] = cell
            out["symbols"][sym]["horizons"][hn] = {"windows": int(len(starts)), "independent": round(years / (H / 252), 1),
                                                   "lump": {"median": float(np.median(base)) - 1, "p5": float(np.percentile(base, 5)) - 1,
                                                            "p95": float(np.percentile(base, 95)) - 1, "up_share": float(np.mean(base > 1))},
                                                   "rows": rows,
                                                   "paths": {"dates": [str(s.index[i].date()) for i in starts], "lump": [round(float(x) - 1, 3) for x in base], "vs_lump": paths}}
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    r = run()
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
