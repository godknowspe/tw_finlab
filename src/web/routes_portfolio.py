import datetime
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.domain.dip_buying import compare
from src.domain.ledger import replay, trade_sort_key, validate_trades
from src.domain.risk import REBUY_WINDOW, round_trips, trailing_stop
from src.domain.symbols import canonical_symbol, currency_of, market_of
from src.domain.valuation import historical_roi, value_positions
from src.schemas.state import normalize_timestamp
from src.services.config_service import ConfigService
from src.services.fx_service import FX_SYMBOL, get_usd_twd
from src.services.instrument_service import adjusted_closes, is_etf
from src.services.market_data import MarketDataService
from src.services.quote_service import get_quotes, shioaji_api_if_enabled
from src.services.state_store import StateConflictError
from src.web import deps
from src.web.analysis import calculate_trade_analysis

router = APIRouter(prefix="/api")


class WatchlistIn(BaseModel):
    symbol: str = Field(min_length=1)
    name: str = ""


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1)
    action: Literal["BUY", "SELL"]
    shares: int = Field(gt=0)
    price: float = Field(gt=0, allow_inf_nan=False)
    timestamp: str
    fee: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    tax: float = Field(default=0.0, ge=0, allow_inf_nan=False)


def _configured_fx(snapshot) -> float:
    return float(snapshot["settings"].get("usd_twd_rate", 32.5))


def mutate(fn):
    try:
        return deps.state().mutate(fn)
    except StateConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _commit_trades(mutator):
    """Apply a change to the trade list, rejecting it if the result would oversell."""
    def apply(s):
        result = mutator(s)
        err = validate_trades(s["trades"])
        if err:
            raise HTTPException(status_code=422, detail=err)
        return result
    return mutate(apply)


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(deps.get_db)):
    version, s = deps.state().versioned_snapshot()
    # Cash is derived from trades (shortfalls count as deposits); state["cash"] is not used.
    ledger = replay(s["trades"])
    symbols = set(ledger.open_positions()) | {w["symbol"] for w in s["watchlist"]}
    quotes = get_quotes(symbols, shioaji_api_if_enabled(ConfigService(db)))
    fx, fx_live = get_usd_twd(_configured_fx(s))
    valued = value_positions(ledger, {k: v[0] for k, v in quotes.items()}, fx)
    valued["summary"]["usd_twd_live"] = fx_live
    attach_stops(valued["positions"], s, MarketDataService(db), ConfigService(db))

    watchlist = []
    for item in s["watchlist"]:
        last, prev = quotes.get(item["symbol"], (None, None))
        chg = (last - prev) / prev * 100 if last and prev else None
        watchlist.append({
            "symbol": item["symbol"], "name": item.get("name", ""), "market": item["market"],
            "last": round(last, 2) if last else None, "ref_price": prev,
            "chg_pct": None if chg is None else f"{'+' if chg > 0 else ''}{chg:.2f}%",
        })
    return {
        "watchlist": watchlist,
        "positions": valued["positions"],
        "summary": valued["summary"],
        "trades": sorted(s["trades"], key=trade_sort_key, reverse=True),
        "settings": {"usd_twd_rate": _configured_fx(s)},
        "sync": deps.sync_status(),
        "revision": version,
    }


def attach_stops(positions, state, market, config):
    """Add a trailing stop to each position: a stop-loss for stocks, a warning for ETFs."""
    custom = state["settings"].get("stop_pct", {})
    for p in positions:
        try:
            bars = market.get_bars(p["symbol"], "1d")
            p["stop"] = trailing_stop(bars, is_etf(p["symbol"], config), custom.get(p["symbol"]),
                                      None if p["price_estimated"] else p["last_price"]) if not bars.empty else None
        except Exception as e:
            logger.warning(f"Stop for {p['symbol']} unavailable: {e}")
            p["stop"] = None


class StopIn(BaseModel):
    pct: Optional[float] = Field(default=None, gt=0, lt=100)   # None = back to the volatility default


@router.put("/stops/{symbol}")
def set_stop(symbol: str, item: StopIn):
    sym = canonical_symbol(symbol)

    def apply(s):
        stops = dict(s["settings"].get("stop_pct", {}))
        if item.pct is None:
            stops.pop(sym, None)
        else:
            stops[sym] = item.pct
        s["settings"]["stop_pct"] = stops
    mutate(apply)
    return {"status": "success"}


@router.get("/round-trips")
def get_round_trips(db: Session = Depends(deps.get_db)):
    s = deps.state().snapshot()
    market = MarketDataService(db)
    syms = {t["symbol"] for t in s["trades"] if t["action"] == "SELL"}
    closes = {sym: market.get_bars(sym, "1d")["close"] for sym in syms}
    trips = round_trips(s["trades"], closes)
    totals = {}
    for r in trips:
        if r["status"] == "closed":
            tot = totals.setdefault(r["currency"], {"closed": 0, "won": 0, "vs_hold": 0.0, "fees": 0.0})
            tot["closed"] += 1
            tot["won"] += r["vs_hold"] > 0
            tot["vs_hold"] = round(tot["vs_hold"] + r["vs_hold"], 2)
            tot["fees"] = round(tot["fees"] + r["fees"], 2)
    return {"window": REBUY_WINDOW, "trips": trips, "totals": totals}


@router.get("/dip-backtest/{symbol}")
def dip_backtest(symbol: str, trigger_pct: float = 10.0, add_pct: Optional[float] = 10.0,
                 monthly: float = 12000, reserve: float = 2000, years: int = 10):
    """add_pct: share of current holdings value to add per trigger; omit or 0 = use the whole reserve."""
    if not (0 < trigger_pct < 100) or not (0 <= reserve <= monthly) or monthly <= 0 or not (1 <= years <= 30):
        raise HTTPException(status_code=422, detail="trigger 0-100%, 0 <= reserve <= monthly, years 1-30")
    start = (datetime.date.today() - datetime.timedelta(days=int(365.25 * years))).isoformat()
    px = adjusted_closes(canonical_symbol(symbol), start)
    if px is None or len(px) < 60:
        raise HTTPException(status_code=404, detail="not enough price history")
    return compare(px, monthly, reserve, trigger_pct / 100, (add_pct / 100) if add_pct else None)


@router.get("/revision")
def get_revision():
    """Cheap poll target: the frontend refetches when this changes (e.g. trades synced from another host)."""
    version, _ = deps.state().versioned_snapshot()
    return {"revision": version, "sync": deps.sync_status()}


@router.post("/watchlist")
def add_watchlist(item: WatchlistIn):
    sym = canonical_symbol(item.symbol)

    def apply(s):
        if not any(w["symbol"] == sym for w in s["watchlist"]):
            s["watchlist"].append({"symbol": sym, "name": item.name, "ref_price": 0.0, "market": market_of(sym)})
    mutate(apply)
    return {"status": "success"}


@router.delete("/watchlist/{symbol}")
def del_watchlist(symbol: str):
    sym = canonical_symbol(symbol)
    mutate(lambda s: s.update(watchlist=[w for w in s["watchlist"] if w["symbol"] != sym]))
    return {"status": "success"}


@router.post("/trades")
def add_trade(item: TradeIn):
    sym = canonical_symbol(item.symbol)
    try:
        ts = normalize_timestamp(item.timestamp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"invalid timestamp: {e}")

    def apply(s):
        trade = item.model_dump()
        trade.update(symbol=sym, timestamp=ts, currency=currency_of(sym), uid=str(uuid.uuid4()),
                     id=max([t["id"] for t in s["trades"]], default=0) + 1)
        s["trades"].append(trade)
    _commit_trades(apply)
    return {"status": "success"}


@router.delete("/trades/{uid}")
def del_trade(uid: str):
    # By uid: `id` numbers can repeat after another host's trades are merged in, so deleting
    # by number from a page that has not refreshed could remove a different trade.
    def apply(s):
        before = len(s["trades"])
        s["trades"] = [t for t in s["trades"] if t["uid"] != uid]
        if len(s["trades"]) == before:
            raise HTTPException(status_code=404, detail="trade not found (it may have been deleted on another host)")
    _commit_trades(apply)
    return {"status": "success"}


@router.post("/sync/trades")
def sync_trades(db: Session = Depends(deps.get_db)):
    api = shioaji_api_if_enabled(ConfigService(db))
    if api is None:
        raise HTTPException(status_code=400, detail="Realtime source is not Shioaji, or Shioaji login failed.")
    from src.api.shioaji_api import fetch_shioaji_trades
    try:
        fills = fetch_shioaji_trades(api)
    except Exception as e:
        logger.error(f"Shioaji trade sync failed: {e}")
        raise HTTPException(status_code=502, detail=f"Shioaji trade sync failed: {e}")

    def apply(s):
        seen = {(t.get("source"), t.get("source_trade_id")) for t in s["trades"] if t.get("source_trade_id")}
        next_id = max([t["id"] for t in s["trades"]], default=0) + 1
        added = 0
        for f in fills:
            key = (f["source"], f["source_trade_id"])
            if key in seen:
                continue
            seen.add(key)
            s["trades"].append({**f, "id": next_id, "uid": str(uuid.uuid4())})
            next_id += 1
            added += 1
        return added
    added = _commit_trades(apply)
    return {"status": "success", "message": f"Synced {added} new trades from Shioaji."}


@router.get("/equity")
def get_equity(db: Session = Depends(deps.get_db)):
    s = deps.state().snapshot()
    market = MarketDataService(db)
    closes = market.daily_closes(t["symbol"] for t in s["trades"])
    fx_bars = market.get_bars(FX_SYMBOL, "1d") if any(t["currency"] == "USD" for t in s["trades"]) else None
    fx = fx_bars["close"] if fx_bars is not None and not fx_bars.empty else None
    return historical_roi(s["trades"], closes, fx, _configured_fx(s))


@router.get("/analysis")
def get_trade_analysis(db: Session = Depends(deps.get_db)):
    s = deps.state().snapshot()
    market = MarketDataService(db)
    return calculate_trade_analysis(s["trades"], lambda sym: market.get_bars(sym, "1d"))
