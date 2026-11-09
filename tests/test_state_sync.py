"""Two hosts, each with its own clone, StateStore and GitStateSync, against a local bare remote."""
import json
import subprocess
import uuid

import pytest

from src.services import state_sync
from src.services.state_store import StateStore
from src.services.state_sync import GitStateSync

STATE = {"schema_version": 1, "settings": {"usd_twd_rate": 32.5}, "cash": {"TWD": 1000000.0, "USD": 50000.0},
         "watchlist": [], "trades": []}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def clone(remote, path):
    subprocess.run(["git", "clone", "-q", str(remote), str(path)], check=True, capture_output=True)
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    return path


@pytest.fixture
def remote(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    seed = clone(remote, tmp_path / "seed")
    (seed / "app_state.json").write_text(json.dumps(STATE, indent=4) + "\n")
    git(seed, "add", "app_state.json")
    git(seed, "commit", "-qm", "init")
    git(seed, "push", "-qu", "origin", "main")
    return remote


class Host:
    def __init__(self, remote, path):
        self.dir = clone(remote, path)
        self.sync = GitStateSync(str(self.dir / "app_state.json"), explicit=True)
        self.store = StateStore(str(self.dir / "app_state.json"), before_load=self.sync.startup_pull)
        self.sync.store = self.store       # driven synchronously by the test, no thread

    def add_trade(self, symbol, ts, action="BUY", shares=1, price=100.0):
        def apply(s):
            s["trades"].append({"uid": str(uuid.uuid4()), "id": max([t["id"] for t in s["trades"]], default=0) + 1, "symbol": symbol,
                                "action": action, "shares": shares, "price": price, "timestamp": ts,
                                "currency": "TWD" if symbol.isdigit() else "USD"})
        self.store.mutate(apply)

    def trades(self):
        return [(t["id"], t["symbol"]) for t in self.store.snapshot()["trades"]]


@pytest.fixture
def hosts(remote, tmp_path):
    a, b = Host(remote, tmp_path / "a"), Host(remote, tmp_path / "b")
    yield a, b
    a.store.close()
    b.store.close()


def test_save_on_one_host_reaches_the_other(hosts):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once()
    b.sync.sync_once()
    assert b.trades() == [(1, "VTI")]
    assert a.sync.in_sync and b.sync.in_sync


def test_concurrent_trades_on_both_hosts_merge(hosts):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    b.add_trade("0050", "2026-06-01T09:30")          # both hosts allocate id 1
    a.sync.sync_once()
    b.sync.sync_once()                               # b diverged: merges, pushes
    a.sync.sync_once()                               # a fast-forwards to the merge
    assert sorted(s for _, s in a.trades()) == ["0050", "VTI"]
    assert a.trades() == b.trades()
    assert sorted(i for i, _ in a.trades()) == [1, 1]           # ids are never renumbered
    assert git(a.dir, "rev-parse", "HEAD") == git(b.dir, "rev-parse", "HEAD")
    # The API keeps saving on top of the merged state without a conflict error.
    b.add_trade("QQQ", "2026-06-02T10:00")
    b.sync.sync_once()
    a.sync.sync_once()
    assert [s for _, s in a.trades()][-1] == "QQQ"


def test_conflict_stops_sync_but_local_saves_still_work(hosts):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once()
    b.sync.sync_once()
    a.add_trade("VTI", "2026-06-02T10:00", action="SELL")
    b.add_trade("VTI", "2026-06-02T11:00", action="SELL")   # together they oversell
    a.sync.sync_once()
    b.sync.sync_once()
    assert b.sync.status["state"] == "conflict" and not b.sync.in_sync
    assert "does not replay" in b.sync.status["error"]
    b.add_trade("QQQ", "2026-06-03T10:00")                   # still possible, committed locally
    b.sync.sync_once()
    assert "QQQ" in git(b.dir, "show", "HEAD:app_state.json")
    assert a.sync.in_sync                                   # the other host is unaffected


def test_only_the_state_file_is_committed(hosts):
    a, _ = hosts
    (a.dir / "notes.txt").write_text("x")
    git(a.dir, "add", "notes.txt")
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once()
    assert git(a.dir, "show", "--name-only", "--format=", "HEAD").split() == ["app_state.json"]
    assert "A  notes.txt" in git(a.dir, "status", "--porcelain")


def test_offline_host_is_not_in_sync_and_retries(hosts, monkeypatch):
    a, _ = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    real = state_sync._git
    monkeypatch.setattr(state_sync, "_git", lambda repo, *args, **k: subprocess.CompletedProcess(args, 1, "", "offline")
                        if args[0] in ("fetch", "push") else real(repo, *args, **k))
    with pytest.raises(state_sync.SyncError):
        a.sync.sync_once()
    assert not a.sync.in_sync and a.sync.status["state"] == "offline"
    monkeypatch.setattr(state_sync, "_git", real)
    a.sync.sync_once()
    assert a.sync.in_sync and git(a.dir, "rev-list", "--count", "@{upstream}..HEAD").strip() == "0"


def test_disabled_unless_explicit_and_never_on_the_code_repo(tmp_path):
    assert not GitStateSync(str(tmp_path / "app_state.json"), explicit=False).repo
    assert not GitStateSync(state_sync.CODE_REPO + "/src/web/app_state.json", explicit=True).repo


def test_local_save_is_not_exportable_until_synced(hosts):
    a, _ = hosts
    a.sync.sync_once()
    assert a.sync.in_sync
    a.store._on_saved = lambda rev, s: a.sync.schedule()
    a.add_trade("VTI", "2026-06-01T10:00")
    assert not a.sync.in_sync                     # export gate closed right after the save
    a.sync.sync_once()
    assert a.sync.in_sync


def test_save_during_push_keeps_host_out_of_sync(hosts, monkeypatch):
    a, _ = hosts
    a.store._on_saved = lambda rev, s: a.sync.schedule()
    a.add_trade("VTI", "2026-06-01T10:00")
    real = state_sync._git
    saved = []

    def push_then_save(repo, *args, **k):
        r = real(repo, *args, **k)
        if args[0] == "push" and not saved:
            saved.append(1)
            a.add_trade("QQQ", "2026-06-02T10:00")      # API save lands while pushing
            assert not a.sync.in_sync
        return r
    monkeypatch.setattr(state_sync, "_git", push_then_save)
    a.sync.sync_once()
    monkeypatch.setattr(state_sync, "_git", real)
    pushed = git(a.dir, "show", "@{upstream}:app_state.json")
    assert "QQQ" in pushed                           # the loop went round again and pushed it
    assert a.sync.in_sync


def test_failed_merge_write_leaves_repo_clean(hosts, monkeypatch):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    b.add_trade("0050", "2026-06-01T09:30")
    a.sync.sync_once()

    def boom(*args, **k):
        raise OSError("disk full")
    monkeypatch.setattr(state_sync, "atomic_write", boom)
    with pytest.raises(OSError):
        b.sync.sync_once()
    assert not (b.dir / ".git" / "MERGE_HEAD").exists()
    assert git(b.dir, "status", "--porcelain", "--", "app_state.json") == ""
    monkeypatch.undo()
    b.sync.sync_once()
    assert sorted(s for _, s in b.trades()) == ["0050", "VTI"]


def test_delete_by_uid_after_merge_removes_the_right_trade(hosts):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    b.add_trade("QQQ", "2026-06-01T10:00")               # both id 1
    a.sync.sync_once(); b.sync.sync_once(); a.sync.sync_once()
    vti_uid = next(t["uid"] for t in a.store.snapshot()["trades"] if t["symbol"] == "VTI")
    a.store.mutate(lambda s: s.update(trades=[t for t in s["trades"] if t["uid"] != vti_uid]))
    a.sync.sync_once(); b.sync.sync_once()
    assert [s for _, s in b.trades()] == ["QQQ"]


def test_invalid_remote_version_is_a_conflict_and_never_marked_synced(hosts, tmp_path):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once()
    b.sync.sync_once()
    (a.dir / "app_state.json").write_text("{}")         # a broken hand edit pushed by someone
    git(a.dir, "commit", "-qam", "broken")
    git(a.dir, "push", "-q")
    b.sync.sync_once()                                  # fast-forward path
    assert b.sync.status["state"] == "conflict" and "invalid" in b.sync.status["error"]
    assert not b.sync.in_sync and [s for _, s in b.trades()] == ["VTI"]
    b.sync.sync_once()
    assert not b.sync.in_sync


def test_merge_refuses_when_other_files_changed(hosts):
    a, b = hosts
    (a.dir / "notes.txt").write_text("x")
    git(a.dir, "add", "notes.txt")
    git(a.dir, "commit", "-qm", "notes")
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once()
    b.add_trade("QQQ", "2026-06-01T10:00")
    b.sync.sync_once()
    assert b.sync.status["state"] == "conflict" and "notes.txt" in b.sync.status["error"]
    assert not (b.dir / ".git" / "MERGE_HEAD").exists()


def test_invalid_remote_reason_never_contains_input_values(hosts):
    a, b = hosts
    a.add_trade("VTI", "2026-06-01T10:00")
    a.sync.sync_once(); b.sync.sync_once()
    secret = "ghp_" + "y" * 30
    broken = json.loads((a.dir / "app_state.json").read_text())
    broken["settings"]["usd_twd_rate"] = {"token": secret}
    (a.dir / "app_state.json").write_text(json.dumps(broken))
    git(a.dir, "commit", "-qam", "broken")
    git(a.dir, "push", "-q")
    b.sync.sync_once()
    assert b.sync.status["state"] == "conflict"
    assert secret not in b.sync.status["error"] and "settings.usd_twd_rate" in b.sync.status["error"]
