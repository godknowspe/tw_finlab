# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Personal Taiwan + US stock dashboard: a FastAPI server that tracks a manually-entered (or Shioaji-synced) trade ledger, draws K-line charts with indicators and per-bar PnL, runs simple backtests, and pushes current holdings to an external notifier. README and many comments are in Chinese.

## Commands

All Python runs from the repo root as `src.*` packages (no `setup.py`), so tests need `PYTHONPATH=.`.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./server_start.sh            # sources .env, runs uvicorn on 127.0.0.1:8000 under nohup -> nohup_uvicorn.log
./server_start.sh --reload   # extra args go to uvicorn; every reload re-runs the startup export

PYTHONPATH=. .venv/bin/pytest tests/
PYTHONPATH=. .venv/bin/pytest tests/test_ledger.py::test_moving_average_with_fees

cd frontend && npm install && npm run build   # Vue 3 + Vite + Pinia + Tailwind + lightweight-charts 3.8
npm run dev                                    # Vite dev server, proxies /api -> localhost:8000
```

The server serves `frontend/dist` (git-ignored) and checks for it once at import, so restart after the first build. There is no linter config.

`tests/conftest.py` strips `PORTFOLIO_EXPORT_*` and blocks `requests.patch/put` for every test. Keep it: env vars override test settings, and without it an exporter test once pushed fake holdings to the live Gist.

## Configuration (`.env`, git-ignored)

| Variable | Purpose |
|---|---|
| `TW_FINLAB_STATE_FILE` | path to `app_state.json`; on this host it lives in the private data repo clone `~/code/tw_finlab-data` |
| `PORTFOLIO_EXPORT_METHODS` / `_GIST_ID` / `_GITHUB_TOKEN` | holdings export targets (`gist`, `local`, `github_repo`); env overrides `settings.portfolio_export` |
| `TW_FINLAB_EXPORT` | `1` on exactly one host: the only one that exports holdings when git sync is on |
| `TW_FINLAB_SYNC_SECONDS` | background git sync interval (default 60) |
| `TW_FINLAB_HOST` / `TW_FINLAB_PORT` | bind address; default loopback because the API has no authentication |
| `TW_FINLAB_DB_URL` | SQLite URL for the price cache (tests use it to isolate) |

## Architecture

### Source of truth: `app_state.json`, owned by `StateStore`
Trades, watchlist, cash and settings live in one JSON file, validated by `src/schemas/state.py` (Pydantic, unknown keys preserved). It is JSON rather than SQLite on purpose: it is synced between hosts through the private git repo `godknowspe/tw_finlab-data`, and JSON diffs and merges in git.

`src/services/state_store.py` is the only writer of the file: the API through `mutate()`, the git sync through `exclusive()` + `adopt()`. Editing it by hand while the server runs is not supported.
- An `flock` on `app_state.json.lock` is taken before anything else (including the startup fast-forward, passed as `before_load`), so a second server on the *same clone* cannot start. Offline tools use the same `acquire_lock` + `atomic_write`.
- A missing file gives a fresh default state that is never exported. An existing file must have `trades`/`cash`/`watchlist`, pass the schema and replay through the ledger (`parse_state`, used on load, save, merge and migration); otherwise `StateLoadError` and the server refuses to start.
- `mutate(fn)` runs `fn` on a copy and validates, checks the file still has the exact bytes this process loaded or last wrote (else `StateConflictError` -> HTTP 409, nothing written), then `atomic_write`, whose rename is the commit point. After it memory, `revision` and the post-save hook (called inside the lock, so in commit order) are updated and nothing raises.
- Old ledgers (string `sj_` ids, `.TW` symbols) go through `python -m src.tools.migrate_state <file>` (dry run by default; `--write` needs the server stopped and never invents missing core data).

### Multi-host sync (several servers running at once)
`src/services/state_sync.py` (opt-in: `TW_FINLAB_STATE_FILE` set and not inside this code repo). One worker runs a cycle after each save and every `TW_FINLAB_SYNC_SECONDS` (60): `fetch` outside the store lock; then under `store.exclusive()` commit only the state file (`commit --only`), fast-forward if only the remote moved, or three-way merge if both did; then `push`, refetching and retrying if rejected. The merge (`src/domain/merge.py`) is semantic, against `git merge-base`, on validated documents only: trades are matched by `uid` (UUID minted at creation; legacy trades get a deterministic uuid5 from their fields), never by content or `id`. `id` is a display number and same-minute tiebreak, may repeat across hosts and is never renumbered; ordering is `(timestamp, id, uid)` so every host replays identically. The API deletes by uid. A broker execution synced on both hosts is kept once by `(source, source_trade_id)`; watchlist merges by symbol; other keys per field. Conflict reasons name fields, never values. The merge refuses if files other than the state file changed (`-s ours` would drop them). Edits to the same element on both sides, or a merged ledger that does not replay (e.g. both hosts sold the same shares), are a conflict: syncing stops, local saves still commit locally, status shows the reasons, and it is resolved by hand in the data repo then restart. Git records the merge with `-s ours --no-commit` and the semantic result written on top, so git's text merge never touches the JSON.

Only one host publishes holdings (`TW_FINLAB_EXPORT=1`): two hosts PATCHing one Gist cannot be ordered, so a slow old export could land after a newer one. The publisher exports only while `sync.in_sync` (HEAD == remote, store == HEAD, cleared by every local save); the newest snapshot waits for the next successful sync. It also drops older revisions, dedups on (holdings, target identity), and retries with backoff. The frontend polls `/api/revision` (`<boot epoch>:<revision>`, taken with the snapshot in one lock) every 30 s and refetches when another host's changes arrive.

Both report through `sync` in `/api/portfolio`. The export JSON `{"portfolio": [{symbol, market, quantity, cost_basis}]}` is read by `~/code/portfolio_notify.py`, so its shape is a contract.

### One ledger for every number
`src/domain/ledger.py` `replay()` is the only trade accounting: moving-average cost, fees capitalised into buy cost, sell fee/tax reducing realised PnL, oversell raises. `validate_trades()` runs it on every add/delete/sync, so the stored ledger is always replayable. `src/domain/valuation.py` builds on it: current account equity (`value_positions`), invested-capital ROI history (`historical_roi`, the Equity chart), and per-bar chart PnL (`bar_pnl`). Bar periods come from `src/domain/bars.py` (`[start, bar_end(start, interval))`, never "until the next bar"); `/api/kbars` returns that `end` and the chart's `barFor` uses it, so trades after the last bar or inside a session gap get no marker. A missing or non-positive/non-finite price is valued at cost and listed in `estimated_prices`/`estimated`, never at 0. `/api/analysis` (`src/web/analysis.py`) is deliberately different: FIFO per-lot review with MAE/MFE.

### Symbols and time
`src/domain/symbols.py`: TW listed codes are stored bare (`2330`, `00631L`), OTC keeps `.TWO`, `.TW` is added only for yfinance. Market and currency derive from the symbol; the schema rejects a trade whose currency disagrees. Trade timestamps are naive exchange-local time normalised to `YYYY-MM-DDTHH:MM[:SS]`, sorted by `(timestamp, id)`. Cached intraday bars are also exchange wall-clock time; the API sends them to the chart as if UTC, and the frontend parses trade timestamps the same way, so both line up without timezone maths.

### Market data
`MarketDataService` (`src/services/market_data.py`) reads the SQLite cache through `DataService`, refetches when empty/short/stale or on an old price basis, and falls back to yfinance when the configured provider errors *or* returns nothing. Providers come from `ProviderFactory` with lazy imports, so shioaji/FinMind are only needed when selected. Prices are stored with `auto_adjust=False` (`price_basis='raw'`): not dividend-adjusted, matching trade prices, but Yahoo still split-adjusts them and the ledger has no split events, so a future split of a held stock needs a manual ledger adjustment. Saves are upserts. Freshness is one rule: refetch when the cache is short, otherwise at most once per throttle window (5-10 min intraday, 15 min daily+), since only the provider knows whether the last bar changed or a newer one exists. `drop_bad_bars` only drops ^TWII holiday ghost bars (zero volume, flat OHLC); no price-threshold filtering, because it cascades and cannot tell glitches from real moves. Quotes for the portfolio and WebSocket go through `src/services/quote_service.py` (Shioaji snapshots for TW when `ds_realtime == "Shioaji"`, else yfinance, 20 s cache).

Shioaji (`src/api/shioaji_api.py`) targets SDK 1.7.x: fills are `trade.status.deals`, deal quantity is lots for Common orders and shares for odd lots, positions are fetched with `unit=Share`. Synced trades carry `source_trade_id` for dedup.

### Backtest
`src/engine/backtest.py`: single-symbol, long-only; a signal on bar i fills at bar i+1 open; TW costs (0.1425% min NT$20, 0.3% tax / 0.1% for `00*` ETFs, 1000-share lots, NT$1M) vs US (no costs, 1-share lots, US$30k); returns are measured from initial cash. Strategies register by name in `STRATEGIES` in `src/engine/strategies.py`.

### Frontend
`frontend/src`: the backtest result carries `symbol`/`interval` and is cleared when either or the strategy changes; chart fetches and backtests use a generation counter to drop stale responses. Markers go on the bar that contains the trade (`barFor`), never the nearest. lightweight-charts 3.8 has no `autoSize`, hence the `ResizeObserver`.

## Deployment notes
`MIGRATION_GUIDE.md` is the original macOS->Linux guide. For a new host: clone this repo and `tw_finlab-data`, create `.env` as above, build the frontend, run `./server_start.sh`. Hosts may run at the same time; see Multi-host sync for what needs manual resolution.
