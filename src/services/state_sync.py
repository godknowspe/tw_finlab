"""
Git sync of app_state.json through a private data repo (e.g. tw_finlab-data), so several hosts
can run the server at the same time.

Opt-in: enabled only when TW_FINLAB_STATE_FILE is set explicitly and points inside a git work
tree that is not this code repo.

One worker thread runs a sync cycle after every local save and every TW_FINLAB_SYNC_SECONDS
(default 60):

1. fetch (network, outside the store lock)
2. under the store lock: commit the state file if it changed, then
   - remote has nothing new          -> nothing to do
   - only remote moved               -> fast-forward and load it
   - both moved                      -> three-way merge (domain/merge.py) against the
                                         merge-base, written as a merge commit, and load it
3. push (network, outside the lock); if rejected because the remote moved again, repeat

Only the state file is ever committed. A semantic conflict (both hosts edited the same thing,
or the merged ledger would oversell) stops syncing: local saves keep working and stay
committed locally, status shows the reasons, and the export is held until it is resolved by
hand in the data repo (then restart).

`in_sync` is True when local HEAD equals the remote branch: only then are both hosts known to
hold the same ledger, so only then may holdings be exported.
"""
import json
import os
import socket
import subprocess
import threading
import time

from loguru import logger
from pydantic import ValidationError

from src.domain.merge import MergeConflict, merge_states
from src.services.state_store import atomic_write, parse_state

CODE_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYNC_SECONDS = int(os.environ.get("TW_FINLAB_SYNC_SECONDS", "60"))
MAX_PUSH_ATTEMPTS = 3


def _git(repo: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout)


def repo_root(path: str):
    try:
        r = _git(os.path.dirname(os.path.abspath(path)), "rev-parse", "--show-toplevel", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


class SyncError(RuntimeError):
    pass


class GitStateSync:
    def __init__(self, state_path: str, explicit: bool, interval: int = SYNC_SECONDS):
        self.path = os.path.abspath(state_path)
        root = repo_root(self.path) if explicit else None
        if root and root == os.path.realpath(CODE_REPO):
            logger.error("TW_FINLAB_STATE_FILE is inside the tw_finlab code repo; git sync disabled.")
            root = None
        self.repo = root
        self.rel = os.path.relpath(self.path, self.repo) if self.repo else None
        self.interval = interval
        self.store = None
        self.on_synced = None           # called after each successful sync (export may proceed)
        self.in_sync = not self.repo    # without git there is nothing to disagree with
        self.status = {"enabled": bool(self.repo), "state": "idle", "error": None, "last_sync": None}
        self._cond = threading.Condition()
        self._wake = False
        self._conflict = None

    # ---- lifecycle -------------------------------------------------------------------------

    def startup_pull(self):
        """Before the store loads (runs under the owner lock): fast-forward if possible.
        A diverged or offline repo is left as is; the first sync cycle merges it."""
        if not self.repo:
            return
        try:
            self._fetch()
            self._run_git("merge", "--ff-only", "-q", "@{upstream}")
        except (SyncError, OSError, subprocess.SubprocessError) as e:
            logger.warning(f"Startup fast-forward skipped, the sync loop will reconcile: {e}")

    def start(self, store):
        self.store = store
        if self.repo:
            threading.Thread(target=self._loop, name="state-git-sync", daemon=True).start()

    def schedule(self, *_):
        """Called after every save. A local save is not yet on the remote, so this host is no
        longer known to agree with the other one until the next successful sync."""
        if self.repo:
            self.in_sync = False
        with self._cond:
            self._wake = True
            self._cond.notify()

    # ---- worker ----------------------------------------------------------------------------

    def _loop(self):
        while True:
            try:
                self.sync_once()
            except Exception as e:
                self.in_sync = False
                self.status.update(state="error", error=str(e))
                logger.error(f"State sync error: {e}")
            with self._cond:
                if not self._wake:
                    self._cond.wait(timeout=self.interval)
                self._wake = False

    def sync_once(self):
        if self._conflict:
            # Do not keep merging on top of an unresolved conflict; local saves still commit.
            with self.store.exclusive():
                self._commit_local()
            return
        for _ in range(MAX_PUSH_ATTEMPTS):
            self._fetch()
            with self.store.exclusive():
                self._commit_local()
                try:
                    self._integrate_remote()
                except MergeConflict as e:
                    self._conflict = e.reasons
                    self.in_sync = False
                    self.status.update(state="conflict", error="; ".join(e.reasons))
                    logger.error(f"State sync conflict, syncing stopped: {e}")
                    return
                if self._ahead() == 0 and not self._dirty() and self._store_matches_head():
                    self._mark_synced()
                    return
            r = _git(self.repo, "push", "-q")
            if r.returncode == 0:
                # An API save may have landed while pushing (outside the lock); only call this
                # host in sync if, under the lock, there is nothing left unpushed or uncommitted.
                with self.store.exclusive():
                    if self._ahead() == 0 and not self._dirty() and self._store_matches_head():
                        self._mark_synced()
                        return
                continue
            logger.warning(f"Push rejected, retrying after fetch: {r.stderr.strip()}")
        self.in_sync = False
        self.status.update(state="push_failed", error="remote kept moving or is unreachable; will retry")

    # ---- steps -----------------------------------------------------------------------------

    def _run_git(self, *args, timeout=60) -> str:
        r = _git(self.repo, *args, timeout=timeout)
        if r.returncode != 0:
            raise SyncError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout

    def _fetch(self):
        try:
            self._run_git("fetch", "-q")
        except SyncError as e:
            self.in_sync = False
            self.status.update(state="offline", error=str(e))
            raise

    def _ahead(self) -> int:
        return int(self._run_git("rev-list", "--count", "@{upstream}..HEAD").strip() or 0)

    def _behind(self) -> int:
        return int(self._run_git("rev-list", "--count", "HEAD..@{upstream}").strip() or 0)

    def _store_matches_head(self) -> bool:
        """In sync means the server's loaded state is the committed one, not just that git is clean
        (a failed adopt after a fast-forward would otherwise look synced)."""
        try:
            committed = parse_state(json.loads(self._run_git("show", f"HEAD:{self.rel}")))
        except (ValueError, json.JSONDecodeError):
            return False
        return committed == self.store.snapshot()

    def _dirty(self) -> bool:
        return bool(self._run_git("status", "--porcelain", "--", self.rel).strip())

    def _commit_local(self):
        if not self._dirty():
            return
        msg = f"Update app_state from {socket.gethostname()}"
        r = _git(self.repo, "commit", "-q", "--only", "-m", msg, "--", self.rel)
        if r.returncode != 0:
            self._run_git("add", "--", self.rel)
            self._run_git("commit", "-q", "--only", "-m", msg, "--", self.rel)

    def _read_rev(self, rev: str) -> dict:
        """A committed version of the state, validated like a load. An invalid remote version
        (e.g. a hand-edited recovery) is a conflict, never read as 'everything was deleted'."""
        try:
            return parse_state(json.loads(self._run_git("show", f"{rev}:{self.rel}")))
        except ValidationError as e:
            # loc + type only: the error text includes input values, which may be private.
            where = ", ".join(f"{'.'.join(map(str, err['loc']))} ({err['type']})" for err in e.errors()[:5])
            raise MergeConflict([f"state at {rev[:12]} is invalid: {where}"])
        except (ValueError, json.JSONDecodeError) as e:
            raise MergeConflict([f"state at {rev[:12]} is invalid: {type(e).__name__}: {str(e)[:120]}"])

    def _other_paths_changed(self, base_rev: str) -> list:
        changed = set()
        for side in ("HEAD", "@{upstream}"):
            changed |= set(self._run_git("diff", "--name-only", base_rev, side).split())
        return sorted(changed - {self.rel})

    def _integrate_remote(self):
        behind = self._behind()
        if behind == 0:
            return
        if self._ahead() == 0:
            self._read_rev("@{upstream}")          # validate before moving HEAD onto it
            self._run_git("merge", "--ff-only", "-q", "@{upstream}")
            self._load_from_disk()
            logger.info(f"Loaded {behind} remote state update(s)")
            return
        base_rev = self._run_git("merge-base", "HEAD", "@{upstream}").strip()
        others = self._other_paths_changed(base_rev)
        if others:
            # `-s ours` below keeps our whole tree; it must not silently drop other files.
            raise MergeConflict([f"files other than {self.rel} changed in the data repo: {', '.join(others)}"])
        merged = parse_state(merge_states(self._read_rev(base_rev), self._read_rev("HEAD"), self._read_rev("@{upstream}")))
        # Record the merge without letting git touch the file: start a no-commit merge that
        # keeps our side, then overwrite the file with the semantic merge and commit.
        self._run_git("merge", "--no-commit", "--no-ff", "-q", "-s", "ours", "@{upstream}")
        try:
            atomic_write(self.path, merged)
            self._run_git("add", "--", self.rel)
            self._run_git("commit", "-q", "-m", f"Merge app_state from remote on {socket.gethostname()}")
        except BaseException:
            # Never leave the data repo mid-merge: restore HEAD's state file and abort.
            _git(self.repo, "merge", "--abort")
            _git(self.repo, "checkout", "HEAD", "--", self.rel)
            raise
        self._load_from_disk()
        logger.info("Merged concurrent state changes from another host")

    def _load_from_disk(self):
        with open(self.path, "rb") as f:
            data = f.read()
        self.store.adopt(json.loads(data), data)

    def _mark_synced(self):
        self.in_sync = True
        self.status.update(state="ok", error=None, last_sync=time.strftime("%H:%M:%S"))
        if self.on_synced:
            self.on_synced()
