"""Run the study and write results.json.   python -m research.twii_regime.run [--refresh]

Two experiments, never ranked against each other:
  mechanism   signal ^TWII, trade ^TWII itself (a price index: no dividends, not directly tradable)
  investment  signal ^TWII, trade 0050 with its dividends and realistic costs, from 2014
Every strategy of an experiment shares the same start, bars, costs and cash rule.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from research.twii_regime import data as D
from research.twii_regime import strategies as S
from research.twii_regime.engine import Costs, run
from research.twii_regime.metrics import drawdown, episodes, paired_block_bootstrap, summarize

OUT = Path(__file__).parent / "results.json"
EXPERIMENTS = {
    "mechanism": {"signal": "^TWII", "trade": "^TWII", "start": "1999-01-04", "label": "機制實驗：^TWII 價格指數（不含息，不可直接交易）"},
    "investment": {"signal": "^TWII", "trade": "0050.TW", "start": "2014-01-02", "label": "投資實驗：^TWII 出訊號，交易 0050（含息）"},
}
COST_SCENARIOS = {
    "無成本": Costs(fee=0.0, tax=0.0, slippage=0.0, cash_rate=0.0),
    "含成本": Costs(fee=0.001425, tax=0.001, slippage=0.0005, cash_rate=0.0),
    "含成本+現金1%": Costs(fee=0.001425, tax=0.001, slippage=0.0005, cash_rate=0.01),
}
MAIN_SCENARIO = "含成本"
SENSITIVITY = {"B 站上200日線": [150, 200, 250]}
# Weight drifts with prices; trade only when it is 5 points off target (and weekly at most), so
# sizing strategies are not charged for daily micro-adjustments they would not make.
BAND = {"rebalance_every": 5, "rebalance_band": 0.05}
REBALANCE = {"E 波動目標10%": BAND, "H 50%持有+50%現金": BAND}


def _line(series: pd.Series, normalise_to=1.0):
    return [[d.strftime("%Y-%m-%d"), round(float(v), 6)] for d, v in series.items()]


def run_experiment(name: str, cfg: dict, data: dict) -> dict:
    sig_bars, trade_bars = data[cfg["signal"]], data[cfg["trade"]]
    start = pd.Timestamp(cfg["start"])
    first_ok = max(sig_bars.index[S.MOM], trade_bars.index[0])      # 252 sessions of signal history, and a price to trade
    start = max(start, first_ok)
    # Signals are computed on the signal series with its full pre-history, then aligned to the
    # sessions the trade instrument actually has.
    signals = {k: fn(sig_bars) for k, fn in S.STRATEGIES.items()}
    out = {"label": cfg["label"], "start": str(start.date()), "end": str(trade_bars.index[-1].date()), "scenarios": {}, "sensitivity": {}}
    results_main = {}
    for scen, costs in COST_SCENARIOS.items():
        rows = {}
        for k in S.STRATEGIES:
            kw = REBALANCE.get(k, {})
            res = run(trade_bars, signals[k], costs, start=start, **kw)
            rows[k] = (res, summarize(res, rf=0.0))
        out["scenarios"][scen] = {k: v[1] for k, v in rows.items()}
        if scen == MAIN_SCENARIO:
            results_main = {k: v[0] for k, v in rows.items()}
    out["curves"] = {k: {"equity": _line(r["equity"]), "drawdown": _line(drawdown(r["equity"])), "weight": _line(r["weight"])} for k, r in results_main.items()}
    out["episodes"] = {k: [{**e, "entry": e["entry"].strftime("%Y-%m-%d"), "exit": e["exit"].strftime("%Y-%m-%d")} for e in episodes(r["equity"], r["weight"], r["fills"])]
                       for k, r in results_main.items()}
    out["fills"] = {k: [{**f, "date": f["date"].strftime("%Y-%m-%d")} for f in r["fills"]] for k, r in results_main.items()}

    for strat, windows in SENSITIVITY.items():
        out["sensitivity"][strat] = {}
        for n in windows:
            res = run(trade_bars, S.above_ma(sig_bars, n), COST_SCENARIOS[MAIN_SCENARIO], start=start)
            s = summarize(res)
            out["sensitivity"][strat][str(n)] = {k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "win_rate", "fills", "episodes_closed")}

    rets = pd.DataFrame({k: r["equity"].pct_change().fillna(0.0) for k, r in results_main.items()})
    out["bootstrap"] = {"base": "A 買進持有", "block": 120, "n": 2000,
                        "result": paired_block_bootstrap(rets, base="A 買進持有", block=120, n=2000)}
    out["halves"] = halves(trade_bars, signals, start)
    return out


def halves(trade_bars, signals, start):
    """Same rules, first vs second half of the sample (exploratory: the whole sample has been seen)."""
    idx = trade_bars.index[trade_bars.index >= start]
    mid = idx[len(idx) // 2]
    out = {}
    for label, a in (("前半", start), ("後半", mid)):
        out[label] = {}
        for k in S.STRATEGIES:
            r = run(trade_bars, signals[k], COST_SCENARIOS[MAIN_SCENARIO], start=a, **REBALANCE.get(k, {}))
            s = summarize(r)
            out[label][k] = {x: s[x] for x in ("cagr", "max_drawdown", "sharpe", "win_rate", "episodes_closed")}
        out[label]["_from"] = str(pd.Timestamp(a).date())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="download and freeze fresh data first")
    args = ap.parse_args(argv)
    if args.refresh or not (D.SNAP / "meta.json").exists():
        meta = D.freeze(D.fetch())
        print("frozen:", json.dumps(meta["symbols"], ensure_ascii=False), file=sys.stderr)
    loaded = D.load()
    result = {"data": loaded["meta"], "experiments": {n: run_experiment(n, c, loaded["data"]) for n, c in EXPERIMENTS.items()},
              "bars": {s: [[d.strftime("%Y-%m-%d"), round(float(r.open), 4), round(float(r.high), 4), round(float(r.low), 4), round(float(r.close), 4)]
                           for d, r in df.iterrows()] for s, df in loaded["data"].items()}}
    OUT.write_text(json.dumps(result, ensure_ascii=False))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
