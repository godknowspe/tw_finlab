"""
Optional git sync of app_state.json through a private data repo (e.g. tw_finlab-data).

Opt-in: enabled only when TW_FINLAB_STATE_FILE is set explicitly and points inside a git work
tree that is not this code repo. The server pulls (fast-forward only) before loading; after each
save a background thread commits *only the state file* and pushes, and keeps retrying the push
while the branch is ahead. Conflicts are never auto-resolved.

`trusted` is False when the startup pull failed: the local copy may be older than what another
host already published, so the server must not overwrite remote holdings until it is resolved.
"""
import os
import socket
import subprocess
import threading

from loguru import logger

CODE_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETRY_SECONDS = 300


def _git(repo: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout)


def repo_root(path: str):
    try:
        r = _git(os.path.dirname(os.path.abspath(path)), "rev-parse", "--show-toplevel", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


class GitStateSync:
    def __init__(self, state_path: str, explicit: bool):
        self.path = os.path.abspath(state_path)
        root = repo_root(self.path) if explicit else None
        if root and root == os.path.realpath(CODE_REPO):
            logger.error("TW_FINLAB_STATE_FILE is inside the tw_finlab code repo; git sync disabled.")
            root = None
        self.repo = root
        self.trusted = True
        self.status = {"enabled": bool(self.repo), "state": "idle", "error": None}
        self._cond = threading.Condition()
        self._dirty = False
        if self.repo:
            threading.Thread(target=self._run, name="state-git-sync", daemon=True).start()

    def pull(self):
        if not self.repo:
            return
        try:
            r = _git(self.repo, "pull", "--ff-only", "--quiet")
            ok, err = r.returncode == 0, r.stderr.strip()
        except (OSError, subprocess.SubprocessError) as e:
            ok, err = False, str(e)
        if ok:
            logger.info(f"State repo {self.repo} is up to date")
            return
        self.trusted = False
        self.status.update(state="pull_failed", error=err)
        logger.error(f"State repo pull failed; using the local copy and holding remote exports: {err}")

    def schedule_push(self, *_):
        if not self.repo:
            return
        with self._cond:
            self._dirty = True
            self._cond.notify()

    def _run(self):
        while True:
            with self._cond:
                if not self._dirty:
                    # Wake periodically so an earlier failed push is retried without a new save.
                    self._cond.wait(timeout=RETRY_SECONDS)
                self._dirty = False
            try:
                self._commit_and_push()
            except Exception as e:
                self.status.update(state="error", error=str(e))
                logger.error(f"State git sync error: {e}")

    def _commit_and_push(self):
        rel = os.path.relpath(self.path, self.repo)
        if _git(self.repo, "status", "--porcelain", "--", rel).stdout.strip():
            # Commit only the state file, whatever else is staged in this repo.
            msg = f"Update app_state from {socket.gethostname()}"
            r = _git(self.repo, "commit", "-q", "--only", "-m", msg, "--", rel)
            if r.returncode != 0:
                r = _git(self.repo, "add", "--", rel)
                if r.returncode == 0:
                    r = _git(self.repo, "commit", "-q", "--only", "-m", msg, "--", rel)
            if r.returncode != 0:
                self.status.update(state="commit_failed", error=r.stderr.strip())
                logger.error(f"State commit failed: {r.stderr.strip()}")
                return
        ahead = _git(self.repo, "rev-list", "--count", "@{upstream}..HEAD")
        if ahead.returncode != 0:
            self.status.update(state="no_upstream", error=ahead.stderr.strip())
            return
        if int(ahead.stdout.strip() or 0) == 0:
            if self.status["state"] != "pull_failed":
                self.status.update(state="ok", error=None)
            return
        r = _git(self.repo, "push", "-q")
        if r.returncode != 0:
            self.status.update(state="push_failed", error=r.stderr.strip())
            logger.error(f"State push failed (commit kept locally, will retry): {r.stderr.strip()}")
        else:
            self.status.update(state="ok", error=None)
