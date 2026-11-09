import copy
import fcntl
import hashlib
import json
import os
import tempfile
import threading
from typing import Any, Callable, Dict, Optional

from loguru import logger
from pydantic import ValidationError

from src.domain.ledger import validate_trades
from src.schemas.state import AppState

DEFAULT_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "app_state.json")
REQUIRED_KEYS = ("trades", "cash", "watchlist")


class StateLoadError(RuntimeError):
    """app_state.json exists but cannot be trusted; the server must not overwrite or export it."""


class StateLockedError(RuntimeError):
    """Another process already owns this state file."""


class StateConflictError(RuntimeError):
    """The file on disk is no longer the version this process loaded or last wrote."""


def parse_state(raw) -> Dict[str, Any]:
    """Schema + semantic validation shared by load, save and migration: core keys present,
    then the ledger must replay (no orphan sells, no duplicate broker executions)."""
    if not isinstance(raw, dict) or any(k not in raw for k in REQUIRED_KEYS):
        raise ValueError(f"state must contain {', '.join(REQUIRED_KEYS)}")
    state = AppState.model_validate(raw).model_dump(mode="json")
    err = validate_trades(state["trades"])
    if err:
        raise ValueError(err)
    return state


def acquire_lock(path: str) -> int:
    """Exclusive owner lock for a state file, shared by the server and offline tools."""
    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise StateLockedError(f"{path} is in use by another tw_finlab process")
    return fd


def atomic_write(path: str, state: Dict[str, Any]) -> str:
    """Write + fsync a temp file and rename it over `path`. The rename is the commit point:
    an exception before it leaves `path` untouched; nothing after it raises. Returns the
    sha256 of the bytes written."""
    data = (json.dumps(state, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".app_state.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as e:
        logger.warning(f"Directory fsync after saving {path} failed (data is written): {e}")
    return hashlib.sha256(data).hexdigest()


class StateStore:
    """
    Single owner of app_state.json. Writing the file while the server runs is not supported:
    stop the server, edit / git pull / migrate, then start it again.

    - The owner lock (`<file>.lock`) is taken before anything else, including the git pull
      passed as `before_load`, so a second server cannot touch the file at all.
    - A missing file yields a fresh default state (`is_fresh`), which is never exported.
      A corrupt, incomplete or non-replayable file raises StateLoadError.
    - `mutate()` applies a change to a copy and validates it. Before writing it checks that
      the file still has the bytes this process loaded or last wrote; if not (external edit,
      pull, deletion) it raises StateConflictError and writes nothing. After the rename the
      save is committed: memory and `revision` are updated and the post-save hook is called
      under the lock, so hooks see saves in commit order.
    """

    @staticmethod
    def default_path() -> str:
        return os.environ.get("TW_FINLAB_STATE_FILE") or DEFAULT_STATE_FILE

    def __init__(self, path: str = None, on_saved: Callable[[int, Dict[str, Any]], None] = None,
                 before_load: Optional[Callable[[], None]] = None):
        self.path = path or self.default_path()
        self._on_saved = on_saved
        self._lock = threading.RLock()
        self._lock_fd = acquire_lock(self.path)
        try:
            if before_load:
                before_load()
            self.is_fresh = False
            self.revision = 0
            self._disk_digest = None
            self._state = self._load()
        except BaseException:
            self.close()
            raise

    def close(self):
        if getattr(self, "_lock_fd", None) is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            logger.warning(f"State file {self.path} not found; starting from an empty default state.")
            self.is_fresh = True
            return AppState().model_dump(mode="json")
        try:
            with open(self.path, "rb") as f:
                data = f.read()
            state = parse_state(json.loads(data))
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as e:
            raise StateLoadError(f"Refusing to start: {self.path} is unreadable or invalid: {e}") from e
        self._disk_digest = hashlib.sha256(data).hexdigest()
        return state

    def _check_disk_unchanged(self):
        try:
            with open(self.path, "rb") as f:
                current = hashlib.sha256(f.read()).hexdigest()
        except FileNotFoundError:
            current = None
        if current != self._disk_digest:
            raise StateConflictError(
                f"{self.path} was changed outside this server since it was loaded; "
                "restart the server to load the new version (nothing was saved)")

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def mutate(self, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        with self._lock:
            draft = copy.deepcopy(self._state)
            result = fn(draft)
            validated = parse_state(draft)
            self._check_disk_unchanged()
            digest = atomic_write(self.path, validated)
            # Committed from here on; nothing below may raise into the caller.
            self._disk_digest = digest
            self._state = validated
            self.is_fresh = False
            self.revision += 1
            if self._on_saved:
                try:
                    self._on_saved(self.revision, copy.deepcopy(validated))
                except Exception as e:
                    logger.error(f"Post-save hook failed (state is saved locally): {e}")
        return result
