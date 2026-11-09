import os
import tempfile

import yfinance as yf
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.log")
logger.add(LOG_FILE, rotation="10 MB", retention="10 days", level="INFO")

# yfinance leaks file descriptors through its sqlite tz cache unless it has a stable location.
yf_cache_dir = os.path.join(tempfile.gettempdir(), "yfinance_cache")
os.makedirs(yf_cache_dir, exist_ok=True)
yf.set_tz_cache_location(yf_cache_dir)

from src.services.portfolio_exporter import ExportWorker
from src.services.state_store import StateStore
from src.services.state_sync import GitStateSync
from src.web import deps
from src.web.routes_market import router as market_router
from src.web.routes_portfolio import router as portfolio_router

FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))


def _build_state() -> StateStore:
    """Pull the data repo (if configured), load and validate state, and wire the post-save hooks.
    A corrupt state file raises StateLoadError here and the server refuses to start."""
    explicit = os.environ.get("TW_FINLAB_STATE_FILE") or None
    sync = GitStateSync(explicit or StateStore.default_path(), explicit=bool(explicit))
    exporter = ExportWorker()

    def on_saved(revision, state):
        sync.schedule_push()
        exporter.submit(revision, state)

    # The store takes the owner lock first, then runs the pull, then loads.
    store = StateStore(explicit, on_saved=on_saved, before_load=sync.pull)
    if not sync.trusted:
        # The local copy may be older than what another host already published.
        exporter.hold("state repo pull failed; resolve it and restart before exports resume")
    deps._status.update(git=lambda: sync.status, export=lambda: exporter.status)
    if store.is_fresh:
        # A default state must never replace the remote holdings backup.
        logger.warning("Skipping startup export: no saved state yet.")
    else:
        exporter.submit(0, store.snapshot())
    return store


app = FastAPI(title="TW FinLab Quant Dashboard")
deps._state = _build_state()
app.include_router(portfolio_router)
app.include_router(market_router)

if os.path.exists(FRONTEND_DIST):
    logger.info(f"Serving modern frontend from {FRONTEND_DIST}")
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
else:
    logger.warning(f"Frontend not built at {FRONTEND_DIST}; run `npm run build` in frontend/ and restart.")


@app.get("/")
async def root():
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return PlainTextResponse("Frontend not built: cd frontend && npm install && npm run build, then restart.", status_code=503)
