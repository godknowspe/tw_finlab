"""
Three-way merge of two app_state versions that diverged from a common base (two hosts that
each saved before seeing the other's change).

Inputs must already be validated documents (parse_state), so a missing key never reads as
"the other side deleted everything".

Elements are matched by identity:
- trades: `uid` (UUID minted when the trade is created, never changed). Content is never used,
  so two real trades with identical fields stay two trades. A broker execution synced on both
  hosts gets different uids but the same (source, source_trade_id); it is kept once.
- watchlist: symbol
- cash / settings / other keys: per field

Per element:
- present in base, changed on one side only  -> that side
- changed identically on both                -> it
- changed differently, or deleted on one side and edited on the other -> conflict
- absent from base, added on both: identical -> once; different -> conflict
The merged ledger must still replay, otherwise it is a conflict too.

Conflict reasons name the element and field, never values (settings may hold credentials);
the replay error only names a trade id, symbol and share counts.
Trade `id`s are left as they are; equal ids from two hosts are fine (see trade_sort_key).
"""
from typing import Any, Dict, List

from src.domain.ledger import validate_trades


class MergeConflict(Exception):
    def __init__(self, reasons: List[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


_MISSING = object()


def _merge_value(name, base, ours, theirs, conflicts):
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    conflicts.append(f"{name} changed on both hosts")
    return ours


def _merge_dict(name, base, ours, theirs, conflicts):
    out = {}
    for k in sorted(set(base) | set(ours) | set(theirs), key=str):
        v = _merge_value(f"{name}.{k}", base.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING), conflicts)
        if v is not _MISSING:
            out[k] = v
    return out


def _merge_records(name, key, base, ours, theirs, conflicts):
    """Merge lists of records identified by key(record). Order: ours, then theirs' additions."""
    b = {key(x): x for x in base}
    o = {key(x): x for x in ours}
    t = {key(x): x for x in theirs}
    out = []
    for k in list(o) + [k for k in t if k not in o]:
        v = _merge_value(f"{name} {k}", b.get(k, _MISSING), o.get(k, _MISSING), t.get(k, _MISSING), conflicts)
        if v is not _MISSING:
            out.append(v)
    return out


def _dedupe_broker_fills(trades, conflicts):
    seen = {}
    out = []
    for t in trades:
        ex = (t.get("source"), t.get("source_trade_id")) if t.get("source_trade_id") else None
        if ex is None:
            out.append(t)
            continue
        if ex in seen:
            fields = ("symbol", "action", "shares", "price", "timestamp", "fee", "tax", "currency")
            if any(seen[ex].get(f) != t.get(f) for f in fields):
                conflicts.append(f"broker execution {ex[1]} differs between hosts")
            continue
        seen[ex] = t
        out.append(t)
    return out


def merge_states(base: Dict[str, Any], ours: Dict[str, Any], theirs: Dict[str, Any]) -> Dict[str, Any]:
    conflicts: List[str] = []
    trades = _merge_records("trade", lambda x: x["uid"], base["trades"], ours["trades"], theirs["trades"], conflicts)
    trades = _dedupe_broker_fills(trades, conflicts)
    watchlist = _merge_records("watchlist", lambda w: w["symbol"], base["watchlist"], ours["watchlist"], theirs["watchlist"], conflicts)

    merged = {}
    for k in sorted(set(base) | set(ours) | set(theirs)):
        if k == "trades":
            merged[k] = trades
        elif k == "watchlist":
            merged[k] = watchlist
        else:
            b, o, t = base.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING)
            if all(isinstance(x, dict) for x in (b, o, t) if x is not _MISSING):
                v = _merge_dict(k, {} if b is _MISSING else b, {} if o is _MISSING else o, {} if t is _MISSING else t, conflicts)
            else:
                v = _merge_value(k, b, o, t, conflicts)
            if v is not _MISSING:
                merged[k] = v
    if not conflicts:
        err = validate_trades(merged["trades"])
        if err:
            conflicts.append(f"merged ledger does not replay: {err}")
    if conflicts:
        raise MergeConflict(conflicts)
    return merged
