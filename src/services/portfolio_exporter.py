import os
import json
import base64
import threading
import requests
from loguru import logger
from src.domain.ledger import replay
from src.domain.symbols import is_tw, yf_ticker


def build_portfolio_json(app_state: dict) -> dict:
    """{"portfolio": [...]} as consumed by the external portfolio_notify.py - keep the shape."""
    ledger = replay(app_state.get("trades", []))
    items = []
    for sym, pos in ledger.open_positions().items():
        items.append({
            "symbol": yf_ticker(sym),
            "market": "TW" if is_tw(sym) else "US",
            "quantity": int(pos.shares),
            "cost_basis": round(pos.avg_cost, 2),
        })
    return {"portfolio": items}


def _resolve_targets(app_state: dict) -> dict:
    cfg = app_state.get("settings", {}).get("portfolio_export", {})
    env = os.environ.get
    methods_env = env("PORTFOLIO_EXPORT_METHODS")
    methods = [m.strip() for m in methods_env.split(",") if m.strip()] if methods_env else cfg.get("methods", [])
    return {
        "methods": methods,
        "token": env("PORTFOLIO_EXPORT_GITHUB_TOKEN") or cfg.get("github_token"),
        "gist_id": env("PORTFOLIO_EXPORT_GIST_ID") or cfg.get("gist_id"),
        "repo": env("PORTFOLIO_EXPORT_GITHUB_REPO") or cfg.get("github_repo"),
        "repo_path": env("PORTFOLIO_EXPORT_GITHUB_PATH") or cfg.get("github_path", "portfolio.json"),
        "local_path": env("PORTFOLIO_EXPORT_LOCAL_PATH") or cfg.get("local_path"),
    }


def trigger_portfolio_export(app_state: dict) -> bool:
    """Synchronously export holdings to every configured target. Returns True if all succeeded."""
    portfolio_json = build_portfolio_json(app_state)
    t = _resolve_targets(app_state)
    logger.info(f"Exporting {len(portfolio_json['portfolio'])} holdings via {t['methods']}")
    ok = True
    for method in t["methods"]:
        try:
            if method == "local":
                _export_local(portfolio_json, t["local_path"])
            elif method == "gist":
                _export_gist(portfolio_json, t["gist_id"], t["token"])
            elif method == "github_repo":
                _export_github_repo(portfolio_json, t["repo"], t["repo_path"], t["token"])
            else:
                raise ValueError(f"unknown export method {method!r}")
        except Exception as e:
            ok = False
            logger.error(f"Portfolio export via {method} failed: {e}")
    return ok


def _delivery_key(app_state: dict) -> str:
    """Holdings plus target identity (no secrets), so a new or changed target is delivered
    even when the holdings did not change."""
    t = _resolve_targets(app_state)
    targets = [t["methods"], t["gist_id"], t["repo"], t["repo_path"], t["local_path"]]
    return json.dumps([build_portfolio_json(app_state), targets], sort_keys=True)


class ExportWorker:
    """Exports the newest saved state in the background.

    Snapshots carry the StateStore revision; an older revision arriving late is dropped, so
    remote holdings can never move backwards within this process. Identical (holdings, targets)
    are not re-sent. Failures are retried with exponential backoff. `hold()` blocks delivery
    (e.g. when the git pull failed and the local state may be stale) while still recording
    what would be sent."""

    def __init__(self, export_fn=trigger_portfolio_export, retry_base=30, retry_max=1800):
        self._export_fn = export_fn
        self._cond = threading.Condition()
        self._pending = None          # (revision, state)
        self._latest_rev = -1
        self._last_key = None
        self._held = None
        self._retry_base, self._retry_max = retry_base, retry_max
        self.status = {"state": "idle", "error": None, "revision": None}
        threading.Thread(target=self._run, name="portfolio-export", daemon=True).start()

    def hold(self, reason: str):
        self._held = reason
        self.status.update(state="held", error=reason)

    def submit(self, revision: int, app_state: dict):
        with self._cond:
            if revision <= self._latest_rev:
                return
            self._latest_rev = revision
            self._pending = (revision, app_state)
            self._cond.notify()

    def _run(self):
        delay = None
        while True:
            with self._cond:
                if self._pending is None or delay:
                    self._cond.wait(timeout=delay)
                if self._pending is None:
                    delay = None
                    continue
                revision, state = self._pending
            try:
                delay = self._deliver(revision, state, delay)
            except Exception as e:
                logger.error(f"Portfolio export worker error: {e}")
                self.status.update(state="failed", error=str(e))
                delay = min((delay or self._retry_base) * 2, self._retry_max)

    def _deliver(self, revision, state, delay):
        if self._held:
            with self._cond:
                if self._pending and self._pending[0] == revision:
                    self._pending = None
            return None
        if not _resolve_targets(state)["methods"]:
            self.status.update(state="disabled", error=None, revision=revision)
            with self._cond:
                if self._pending and self._pending[0] == revision:
                    self._pending = None
            return None
        key = _delivery_key(state)
        if key != self._last_key:
            self.status.update(state="running", error=None)
            if not self._export_fn(state):
                self.status.update(state="failed", error="see server.log; retrying")
                return min((delay or self._retry_base) * 2, self._retry_max)
            self._last_key = key
        self.status.update(state="ok", error=None, revision=revision)
        with self._cond:
            if self._pending and self._pending[0] == revision:
                self._pending = None
        return None


def _export_local(portfolio_json: dict, path: str):
    if not path:
        raise ValueError("PORTFOLIO_EXPORT_LOCAL_PATH is not set")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio_json, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    logger.info(f"Exported portfolio locally to {path}")


def _export_gist(portfolio_json: dict, gist_id: str, token: str):
    if not gist_id or not token:
        raise ValueError("Gist ID or GitHub token is not configured")
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    payload = {"files": {"portfolio.json": {"content": json.dumps(portfolio_json, indent=2, ensure_ascii=False)}}}
    resp = requests.patch(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    logger.info(f"Exported portfolio to GitHub Gist {gist_id}")


def _export_github_repo(portfolio_json: dict, repo: str, path: str, token: str):
    if not repo or not token:
        raise ValueError("GitHub repo or token is not configured")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    sha = None
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        sha = resp.json().get("sha")
    elif resp.status_code != 404:
        resp.raise_for_status()
    content = base64.b64encode(json.dumps(portfolio_json, indent=2, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    payload = {"message": "Automated update of portfolio holdings from tw_finlab", "content": content}
    if sha:
        payload["sha"] = sha
    put_resp = requests.put(url, json=payload, headers=headers, timeout=10)
    put_resp.raise_for_status()
    logger.info(f"Exported portfolio to GitHub repository {repo}/{path}")
