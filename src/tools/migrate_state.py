"""
Migrate an app_state.json written by the pre-StateStore server so it loads under the current schema.

    PYTHONPATH=. .venv/bin/python -m src.tools.migrate_state path/to/app_state.json          # dry run
    PYTHONPATH=. .venv/bin/python -m src.tools.migrate_state path/to/app_state.json --write  # backup + write

What it changes, and reports:
- string ids such as 'sj_<broker id>' get a new integer id; the old value moves to
  source_trade_id with source='Shioaji'
- symbols are canonicalised (2330.TW -> 2330); watchlist duplicates that collapse are merged
- timestamps are normalised ('2026-05-03 10:23:45.123' -> '2026-05-03T10:23:45')
- a trade whose currency disagrees with its symbol is NOT rewritten (its price may really be
  in the other currency); it is listed and the migration refuses to write until it is fixed by hand
- missing trades / cash / watchlist are NOT invented; the migration refuses instead
The result must pass the same validation the server applies on load, or nothing is written.
--write takes the server's owner lock (so the server must be stopped) and writes atomically.
"""
import argparse
import json
import os
import sys
import time

from src.domain.symbols import canonical_symbol, currency_of, market_of
from src.schemas.state import normalize_timestamp
from src.services.state_store import REQUIRED_KEYS, StateLockedError, acquire_lock, atomic_write, parse_state


def migrate(raw: dict):
    state = json.loads(json.dumps(raw))
    notes, blockers = [], []
    missing = [k for k in REQUIRED_KEYS if k not in state]
    if missing:
        return state, notes, [f"missing {', '.join(missing)}: not an app_state file this tool can convert"]

    int_ids = [t["id"] for t in state["trades"] if isinstance(t.get("id"), int)]
    next_id = max(int_ids, default=0) + 1
    for t in state["trades"]:
        if not isinstance(t.get("id"), int):
            old = str(t.get("id"))
            t.setdefault("source", "Shioaji" if old.startswith("sj_") else "import")
            t.setdefault("source_trade_id", old[3:] if old.startswith("sj_") else old)
            t["id"] = next_id
            notes.append(f"trade {old!r} -> id {next_id}")
            next_id += 1
        sym = canonical_symbol(str(t["symbol"]))
        if sym != t["symbol"]:
            notes.append(f"trade {t['id']}: symbol {t['symbol']!r} -> {sym!r}")
            t["symbol"] = sym
        ts = normalize_timestamp(t["timestamp"])
        if ts != t["timestamp"]:
            notes.append(f"trade {t['id']}: timestamp {t['timestamp']!r} -> {ts!r}")
            t["timestamp"] = ts
        expected = currency_of(sym)
        if "currency" not in t:
            t["currency"] = expected
            notes.append(f"trade {t['id']}: currency set to {expected}")
        elif t["currency"] != expected:
            blockers.append(f"trade {t['id']} {sym}: currency {t['currency']} but {sym} trades in {expected}; fix price/currency by hand")

    merged = {}
    for w in state["watchlist"]:
        sym = canonical_symbol(str(w["symbol"]))
        if sym in merged:
            notes.append(f"watchlist: merged duplicate {w['symbol']!r} into {sym!r}")
            continue
        merged[sym] = {**w, "symbol": sym, "market": market_of(sym)}
    state["watchlist"] = list(merged.values())
    return state, notes, blockers


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--write", action="store_true", help="back up the original and write the migrated file")
    args = ap.parse_args(argv)

    with open(args.path, "rb") as f:
        original = f.read()
    raw = json.loads(original)
    state, notes, blockers = migrate(raw)
    for n in notes:
        print("  " + n)
    for b in blockers:
        print("  BLOCKED: " + b)
    if blockers:
        print("Not written: resolve the blocked trades first.")
        return 1
    try:
        validated = parse_state(state)
    except Exception as e:
        print(f"Not written: migrated state still fails validation: {e}")
        return 1
    print(f"{len(validated['trades'])} trades, {len(validated['watchlist'])} watchlist items validate and replay.")
    if not args.write:
        print("Dry run; pass --write to apply.")
        return 0
    try:
        lock_fd = acquire_lock(args.path)
    except StateLockedError as e:
        print(f"Not written: {e}. Stop the server first.")
        return 1
    try:
        with open(args.path, "rb") as f:
            if f.read() != original:
                print("Not written: the file changed while migrating; run again.")
                return 1
        backup = f"{args.path}.bak-{time.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
        with open(backup, "xb") as f:
            f.write(original)
        atomic_write(args.path, validated)
    finally:
        os.close(lock_fd)
    print(f"Written. Original saved as {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
