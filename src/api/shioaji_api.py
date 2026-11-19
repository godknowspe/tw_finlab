import datetime
import threading
import time
import zoneinfo
import shioaji as sj
import pandas as pd
from typing import Optional

TAIPEI = zoneinfo.ZoneInfo("Asia/Taipei")

RELOGIN_COOLDOWN_S = 30      # Shioaji allows 1000 logins a day and may suspend clients that hammer it


class ShioajiCoolingDown(RuntimeError):
    """A new login was attempted too soon after the last one."""


class ShioajiClient:
    """Process-wide logged-in session. Only published after a successful login, rebuilt when the
    credentials change, and dropped by `reset()` when a call shows the session has died (it
    expires overnight; without this the dead object was handed out forever)."""
    _instance = None
    _lock = threading.Lock()
    _clock = staticmethod(time.monotonic)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShioajiClient, cls).__new__(cls)
            cls._instance._api = None
            cls._instance._creds = None
            cls._instance._last_login = None
        return cls._instance

    def reset(self, api=None):
        """Forget the session so the next `get_api` logs in again. `api` is the object the caller
        saw fail; if a newer session has replaced it meanwhile, leave the new one alone."""
        with self._lock:
            if self._api is None or (api is not None and api is not self._api):
                return
            try:
                self._api.logout()
            except Exception:
                pass
            self._api = None

    def get_api(self, api_key: str = "", api_secret: str = ""):
        if not (api_key and api_secret):
            raise RuntimeError("Shioaji API key/secret are not configured")
        with self._lock:
            if self._api is not None and self._creds == (api_key, api_secret):
                return self._api
            if self._api is not None:
                try:
                    self._api.logout()
                except Exception:
                    pass
                self._api = None
            if self._last_login is not None and self._clock() - self._last_login < RELOGIN_COOLDOWN_S:
                raise ShioajiCoolingDown(f"last login was {self._clock() - self._last_login:.0f}s ago; retry in a moment")
            self._last_login = self._clock()
            api = sj.Shioaji()
            api.login(api_key=api_key, secret_key=api_secret)
            self._api, self._creds = api, (api_key, api_secret)
            return api

def fetch_shioaji_positions(api) -> list:
    """
    獲取 Shioaji 真實帳戶庫存明細
    """
    # unit=Share makes quantity a share count regardless of board lot vs odd lot.
    positions = api.list_positions(api.stock_account, unit=sj.Unit.Share)
    return [{
        "symbol": p.code,
        "shares": int(p.quantity),
        "avg_cost": float(p.price),
        "last_price": float(p.last_price),
        "broker_pnl": float(p.pnl),
    } for p in positions]


def fetch_shioaji_trades(api) -> list:
    """
    Today's executions, one entry per deal. Includes partial fills and orders cancelled after
    a partial fill. Raises on SDK errors so the caller can report a failed sync.
    shioaji 1.7.x: fills live in trade.status.deals (Deal: seq, price, quantity, ts, datetime);
    quantity is in lots (1000 shares) for Common orders and in shares for odd-lot orders.
    """
    api.update_status(api.stock_account)
    results = []
    for t in api.list_trades():
        lot = getattr(t.order, "order_lot", None)
        if lot is None:
            continue  # futures/options orders carry no stock order lot
        multiplier = 1000 if lot == sj.StockOrderLot.Common else 1
        for deal in t.status.deals:
            if deal.datetime is not None:
                dt = deal.datetime.astimezone(TAIPEI)
            elif deal.ts:
                dt = datetime.datetime.fromtimestamp(deal.ts, TAIPEI)
            else:
                raise ValueError(f"deal {t.order.ordno}:{deal.seq} has no timestamp")
            results.append({
                "symbol": t.contract.code,
                "action": "BUY" if t.order.action == sj.Action.Buy else "SELL",
                "shares": int(deal.quantity) * multiplier,
                "price": float(deal.price),
                "timestamp": dt.replace(tzinfo=None).isoformat(timespec="seconds"),
                "currency": "TWD",
                "source": "Shioaji",
                "source_trade_id": f"{t.order.ordno}:{deal.seq}",
            })
    return results

def fetch_shioaji_kbars(api, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Daily OHLCV built from Shioaji 1-minute kbars (the SDK has no daily endpoint).
    Volume is in lots as reported by the SDK."""
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return pd.DataFrame()
    kbars = api.kbars(contract=contract, start=start_date, end=end_date)
    df = pd.DataFrame({**kbars})
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").rename(columns=str.lower)
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    daily = daily.dropna(subset=["close"])
    daily.index.name = "date"
    return daily

def fetch_shioaji_quote(api, stock_id: str) -> Optional[float]:
    """
    獲取 Shioaji 即時報價 (快照)
    """
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return None
    
    # 訂閱或直接抓快照
    snapshot = api.snapshots([contract])
    if snapshot:
        return float(snapshot[0].close)
    return None
