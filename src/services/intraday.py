"""Same-day 1-minute bars for TW stocks from Shioaji, within its rate limits.

Shioaji caps market-data calls (snapshots/ticks/kbars) at 50 per 10 s, intraday kbars at 270
calls and 500 MB of traffic per day; polling during trading hours risks a suspension. So each
symbol is backfilled with ONE kbars call per day and then kept current from the pushed tick
stream, which does not count against the call limits. HTTP readers only see local memory.
"""
import datetime
import threading
import time
from collections import OrderedDict, deque

import pandas as pd
from loguru import logger

CALL_WINDOW_S = 10
CALL_BUDGET = 20             # of Shioaji's 50 per 10 s: leave room for the quote service
KBARS_PER_DAY = 100          # of Shioaji's 270
MAX_SUBSCRIPTIONS = 10       # of Shioaji's 200: each chart view holds one

OPEN, CLOSE = datetime.time(9, 0), datetime.time(13, 30)


class RateLimited(RuntimeError):
    pass


class CallGate:
    """Counts our own market-data calls and refuses before Shioaji would suspend the account."""

    def __init__(self, budget=CALL_BUDGET, window=CALL_WINDOW_S, daily=KBARS_PER_DAY, clock=time.monotonic, today=datetime.date.today):
        self.budget, self.window, self.daily, self.clock, self.today = budget, window, daily, clock, today
        self._calls = deque()
        self._day, self._kbars = today(), 0
        self._lock = threading.Lock()

    def acquire(self, kind: str):
        with self._lock:
            now = self.clock()
            while self._calls and now - self._calls[0] > self.window:
                self._calls.popleft()
            if self.today() != self._day:
                self._day, self._kbars = self.today(), 0
            if len(self._calls) >= self.budget:
                raise RateLimited(f"{len(self._calls)} market-data calls in the last {self.window}s")
            if kind == "kbars" and self._kbars >= self.daily:
                raise RateLimited(f"{self._kbars} kbars calls today")
            self._calls.append(now)
            if kind == "kbars":
                self._kbars += 1


def _minute(ts) -> pd.Timestamp:
    return pd.Timestamp(ts).floor("min")


def bars_from_kbars(kbars: dict) -> "OrderedDict[pd.Timestamp, dict]":
    """Shioaji stamps a kbar with the END of its minute and reports volume in lots; the chart
    wants the START of the minute and shares. Idle minutes have zero volume and are dropped."""
    out = OrderedDict()
    for ts, o, h, l, c, v in zip(kbars["ts"], kbars["Open"], kbars["High"], kbars["Low"], kbars["Close"], kbars["Volume"]):
        if not v:
            continue
        start = _minute(pd.Timestamp(ts) - pd.Timedelta(minutes=1))
        out[start] = {"open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v) * 1000}
    return out


class IntradayBars:
    """One symbol's minute bars for one trading day, built from a backfill plus ticks."""

    def __init__(self):
        self.day = None
        self.bars = OrderedDict()
        self._lock = threading.Lock()

    def reset(self, day, backfill):
        """Install the backfill. Minutes after its last bar were built from ticks that arrived
        while the request was in flight; keep those so the stream has no gap."""
        with self._lock:
            newer = [(k, v) for k, v in self.bars.items() if backfill and k > next(reversed(backfill))] if self.day is None else []
            self.day = day
            self.bars = OrderedDict(sorted([*backfill.items(), *newer]))

    def add_tick(self, ts, price: float, lots: float, simtrade: bool = False):
        """Fold one tick into its minute. Pre-open simulated matches and ticks outside the
        session never become bars."""
        ts = pd.Timestamp(ts)
        if simtrade or not (OPEN <= ts.time() <= CLOSE):
            return
        start = _minute(ts)
        with self._lock:
            if self.day is not None and ts.date() != self.day:
                return
            b = self.bars.get(start)
            if b is None:
                self.bars[start] = {"open": price, "high": price, "low": price, "close": price, "volume": lots * 1000}
            else:
                b["high"], b["low"], b["close"] = max(b["high"], price), min(b["low"], price), price
                b["volume"] += lots * 1000

    def frame(self) -> pd.DataFrame:
        with self._lock:
            if not self.bars:
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            df = pd.DataFrame.from_dict(self.bars, orient="index").sort_index()
        df.index.name = "ts"
        return df


def resample(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty or minutes == 1:
        return df
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    # 09:00-anchored buckets, so 5m bars start at 09:00, 09:05, ...
    out = df.resample(f"{minutes}min", origin=df.index[0].normalize() + pd.Timedelta(hours=9)).agg(agg)
    return out.dropna(subset=["close"])


class IntradayService:
    """Owns the Shioaji tick subscriptions. `api` is a logged-in shioaji.Shioaji."""

    def __init__(self, api, gate: CallGate = None, today=datetime.date.today):
        self.api, self.gate, self.today = api, gate or CallGate(), today
        self._symbols = OrderedDict()          # code -> IntradayBars, oldest first
        self._lock = threading.Lock()
        api.set_on_tick_stk_v1_callback(self._on_tick)

    def _on_tick(self, exchange, tick):
        bars = self._symbols.get(tick.code)
        if bars is not None:
            # Tick datetimes arrive as Taipei wall-clock, matching how the rest of the app stores bars.
            bars.add_tick(tick.datetime.replace(tzinfo=None), float(tick.close), float(tick.volume), bool(tick.simtrade))

    def get(self, code: str) -> IntradayBars:
        with self._lock:
            bars = self._symbols.get(code)
            if bars is not None and bars.day == self.today():
                self._symbols.move_to_end(code)
                return bars
            contract = self.api.Contracts.Stocks[code]
            if not contract:
                raise KeyError(code)
            bars = bars or IntradayBars()
            self._symbols[code] = bars
            # Subscribe first: ticks arriving during the backfill are merged by add_tick, so no gap.
            self._subscribe(contract)
            self.gate.acquire("kbars")
            today = self.today().isoformat()
            k = self.api.kbars(contract, start=today, end=today)
            bars.reset(self.today(), bars_from_kbars({**k}))
            while len(self._symbols) > MAX_SUBSCRIPTIONS:
                old, _ = self._symbols.popitem(last=False)
                self._unsubscribe(old)
            return bars

    def _subscribe(self, contract):
        import shioaji as sj
        self.api.subscribe(contract, quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)

    def _unsubscribe(self, code):
        import shioaji as sj
        try:
            self.api.unsubscribe(self.api.Contracts.Stocks[code], quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)
        except Exception as e:
            logger.warning(f"Shioaji unsubscribe {code} failed: {e}")
