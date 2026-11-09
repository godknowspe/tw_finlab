import asyncio
import datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.data.models import get_engine, get_session
from src.domain.symbols import canonical_symbol
from src.domain.bars import bar_ends
from src.domain.valuation import bar_pnl
from src.engine.backtest import BacktestEngine
from src.engine.strategies import STRATEGIES
from src.services.config_service import ConfigService
from src.services.indicator_service import IndicatorService
from src.services.market_data import INTRADAY, MarketDataService
from src.services.quote_service import get_quotes, shioaji_api_if_enabled
from src.web import deps

router = APIRouter(prefix="/api")

SECRET_KEYS = {"shioaji_api_key", "shioaji_api_secret", "shioaji_person_id", "shioaji_password"}
INTERVALS = {"15m", "30m", "60m", "1h", "1d", "1wk", "1mo"}


class ConfigUpdate(BaseModel):
    kline: str
    realtime: str
    # Empty secret fields mean "keep the stored value"; the UI never receives them back.
    shioaji_api_key: str = ""
    shioaji_api_secret: str = ""
    shioaji_person_id: str = ""
    shioaji_password: str = ""


def _num(v):
    return float(v) if v is not None and not (pd.isna(v) or np.isinf(v)) else None


def _chart_time(ts, intraday: bool):
    # Intraday bars are exchange wall-clock time; send them as if UTC so the chart prints
    # the exchange time unchanged regardless of the browser's timezone.
    ts = pd.Timestamp(ts)
    return int(ts.tz_localize("UTC").timestamp()) if intraday else ts.strftime("%Y-%m-%d")


@router.get("/config")
def get_config(db: Session = Depends(deps.get_db)):
    cfg = {k[3:]: v for k, v in ConfigService(db).get_all_configs().items() if k.startswith("ds_")}
    out = {k: v for k, v in cfg.items() if k not in SECRET_KEYS}
    out.update({f"{k}_set": bool(cfg.get(k)) for k in SECRET_KEYS})
    return out


@router.post("/config")
def update_config(config: ConfigUpdate, db: Session = Depends(deps.get_db)):
    svc = ConfigService(db)
    for k, v in config.model_dump().items():
        if k in SECRET_KEYS and not v:
            continue
        svc.set_config(f"ds_{k}", v)
    return {"status": "success", "message": "Configuration updated in database."}


@router.get("/kbars/{stock_id}")
def get_kbars(stock_id: str, interval: str = "1d", db: Session = Depends(deps.get_db)):
    if interval not in INTERVALS:
        raise HTTPException(status_code=422, detail=f"unsupported interval {interval}")
    sym = canonical_symbol(stock_id)
    df = MarketDataService(db).get_bars(sym, interval)
    if df.empty:
        return []
    df = IndicatorService.add_all_indicators(df)
    intraday = interval in INTRADAY

    trades = [t for t in deps.state().snapshot()["trades"] if t["symbol"] == sym]
    pnl = bar_pnl(trades, df.index, df["close"], interval) if trades else [{"total_pnl": None, "pnl_pct": None}] * len(df)
    ends = bar_ends(df.index, interval)

    result = []
    for (ts, row), p, end in zip(df.iterrows(), pnl, ends):
        result.append({
            "time": _chart_time(ts, intraday),
            # Exclusive end of the bar period, same pseudo-UTC seconds as intraday `time`;
            # the chart uses it to place trade markers on the bar that contains them.
            "end": int(end.tz_localize("UTC").timestamp()),
            "open": _num(row["open"]), "high": _num(row["high"]), "low": _num(row["low"]), "close": _num(row["close"]),
            "value": _num(row["volume"]),
            **{k: _num(row.get(k)) for k in ("sma5", "sma10", "sma20", "macd", "signal", "histogram", "rsi", "bb_up", "bb_mid", "bb_low", "k", "d")},
            "total_pnl": _num(p["total_pnl"]), "pnl_pct": _num(p["pnl_pct"]),
        })
    return result


@router.get("/backtest/{symbol}")
def run_backtest(symbol: str, strategies: str = "RSI", interval: str = "1d", db: Session = Depends(deps.get_db)):
    sym = canonical_symbol(symbol)
    df = MarketDataService(db).get_bars(sym, interval)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available for backtest")
    df["stock_id"] = sym
    intraday = interval in INTRADAY
    results = {}
    for name in strategies.split(","):
        if name not in STRATEGIES:
            continue
        res = BacktestEngine(df.copy()).run(STRATEGIES[name])
        results[name] = {
            "symbol": sym, "interval": interval, "strategy": name,
            "total_return_pct": round(res["total_return"] * 100, 2),
            "max_drawdown_pct": round(res["max_drawdown"] * 100, 2),
            "final_equity": int(res["final_equity"]),
            "chart_data": [{"time": _chart_time(r["date"], intraday), "value": round(r["total_equity"], 2)}
                           for _, r in res["equity_curve"].iterrows()],
            "trades": [{"time": _chart_time(t["date"], intraday), "side": t["side"], "price": t["price"], "size": t["size"]}
                       for t in res["trades"]],
        }
    return results


@router.websocket("/ws/watchlist")
async def websocket_watchlist(websocket: WebSocket):
    await websocket.accept()
    db = get_session(get_engine())
    try:
        shioaji_api = shioaji_api_if_enabled(ConfigService(db))
    finally:
        db.close()

    async def detect_close():
        # The client never sends anything; receive() returns when it disconnects.
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                return

    closed = asyncio.create_task(detect_close())
    last = {}
    try:
        while not closed.done():
            symbols = [w["symbol"] for w in deps.state().snapshot()["watchlist"]]
            try:
                quotes = await asyncio.wait_for(asyncio.to_thread(get_quotes, symbols, shioaji_api), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("Quote refresh timed out; skipping this tick")
                quotes = {}
            now = datetime.datetime.now().strftime("%H:%M:%S")
            updates = []
            for sym, (price, _prev) in quotes.items():
                if price != last.get(sym):
                    last[sym] = price
                    updates.append({"symbol": sym, "price": round(price, 2), "time": now})
            if updates:
                await websocket.send_json({"type": "updates", "data": updates})
            await asyncio.wait({closed}, timeout=30)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        closed.cancel()
        logger.info("WebSocket client disconnected")
