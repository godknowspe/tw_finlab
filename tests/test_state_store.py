import json

import pytest

from src.services.state_store import StateLoadError, StateStore

TRADE = {"id": 1, "symbol": "0050", "action": "BUY", "shares": 1000, "price": 100.0,
         "timestamp": "2026-06-01T10:00", "currency": "TWD"}


def write(path, data):
    path.write_text(json.dumps({"cash": {"TWD": 1e6, "USD": 0}, "watchlist": [], "trades": [], **data}), encoding="utf-8")


def test_missing_file_is_fresh_and_not_saved(tmp_path):
    store = StateStore(str(tmp_path / "app_state.json"))
    assert store.is_fresh
    assert not (tmp_path / "app_state.json").exists()


ORPHAN_SELL = {**TRADE, "action": "SELL"}


@pytest.mark.parametrize("content", [
    "{not json",
    json.dumps({"trades": [{"id": 1}]}),
    "{}",                                                                    # parses, but no ledger in it
    json.dumps({"trades": [ORPHAN_SELL], "cash": {}, "watchlist": []}),      # does not replay
    json.dumps({"trades": [], "cash": {"TWD": float("nan")}, "watchlist": []}),
    json.dumps({"trades": [TRADE, {**TRADE, "id": 2}], "cash": {}, "watchlist": []}).replace(
        '"currency": "TWD"}', '"currency": "TWD", "source": "Shioaji", "source_trade_id": "X"}'),
])
def test_corrupt_or_invalid_file_refuses_to_load(tmp_path, content):
    (tmp_path / "app_state.json").write_text(content, encoding="utf-8")
    with pytest.raises(StateLoadError):
        StateStore(str(tmp_path / "app_state.json"))


def test_unknown_fields_round_trip(tmp_path):
    p = tmp_path / "app_state.json"
    write(p, {"trades": [TRADE], "agent_state": {"halted": False}, "data_sources": {"kline": "yfinance"}})
    store = StateStore(str(p))
    store.mutate(lambda s: s["watchlist"].append({"symbol": "VTI"}))
    saved = json.loads(p.read_text())
    assert saved["agent_state"] == {"halted": False} and saved["data_sources"] == {"kline": "yfinance"}
    assert saved["watchlist"][0]["market"] == "US"


def test_failed_write_leaves_disk_and_memory_unchanged(tmp_path, monkeypatch):
    p = tmp_path / "app_state.json"
    write(p, {"trades": [TRADE]})
    store = StateStore(str(p))
    before = p.read_text()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr("src.services.state_store.os.replace", boom)
    with pytest.raises(OSError):
        store.mutate(lambda s: s["trades"].clear())
    assert p.read_text() == before
    assert len(store.snapshot()["trades"]) == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_mutation_is_rejected(tmp_path):
    p = tmp_path / "app_state.json"
    write(p, {"trades": [TRADE]})
    store = StateStore(str(p))
    with pytest.raises(Exception):
        store.mutate(lambda s: s["trades"].append({**TRADE, "id": 2, "shares": -5}))
    assert len(store.snapshot()["trades"]) == 1


def test_saved_hook_failure_does_not_undo_save(tmp_path):
    p = tmp_path / "app_state.json"
    write(p, {"trades": []})

    def hook(revision, state):
        raise RuntimeError("network down")
    store = StateStore(str(p), on_saved=hook)
    store.mutate(lambda s: s["trades"].append(TRADE))
    assert len(json.loads(p.read_text())["trades"]) == 1


def test_second_store_on_same_file_is_refused(tmp_path):
    from src.services.state_store import StateLockedError
    p = tmp_path / "app_state.json"
    write(p, {})
    first = StateStore(str(p))
    with pytest.raises(StateLockedError):
        StateStore(str(p))
    first.close()


def test_external_change_or_delete_is_refused_not_overwritten(tmp_path):
    from src.services.state_store import StateConflictError
    p = tmp_path / "app_state.json"
    write(p, {})
    store = StateStore(str(p))
    write(p, {"trades": [TRADE]})               # e.g. a git pull while the server runs
    with pytest.raises(StateConflictError):
        store.mutate(lambda s: s["watchlist"].append({"symbol": "VTI"}))
    assert len(json.loads(p.read_text())["trades"]) == 1
    p.unlink()
    with pytest.raises(StateConflictError):
        store.mutate(lambda s: s["watchlist"].append({"symbol": "VTI"}))
    assert not p.exists()


def test_digest_comes_from_the_bytes_that_were_parsed(tmp_path, monkeypatch):
    """Replacing the file right after it was read must be detected on the next save."""
    from src.services import state_store as ss
    from src.services.state_store import StateConflictError
    p = tmp_path / "app_state.json"
    write(p, {})
    real_loads = json.loads

    def loads_then_replace(data):
        result = real_loads(data)
        write(p, {"trades": [TRADE]})
        return result
    monkeypatch.setattr(ss.json, "loads", loads_then_replace)
    store = StateStore(str(p))
    monkeypatch.setattr(ss.json, "loads", real_loads)
    with pytest.raises(StateConflictError):
        store.mutate(lambda s: s["watchlist"].append({"symbol": "VTI"}))
    assert len(json.loads(p.read_text())["trades"]) == 1


def test_failure_after_rename_still_commits(tmp_path, monkeypatch):
    p = tmp_path / "app_state.json"
    write(p, {})
    seen = []
    store = StateStore(str(p), on_saved=lambda rev, s: seen.append(rev))
    real_fsync = __import__("os").fsync
    calls = {"n": 0}

    def fsync_dir_fails(fd):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("directory fsync unsupported")
        return real_fsync(fd)
    monkeypatch.setattr("src.services.state_store.os.fsync", fsync_dir_fails)
    store.mutate(lambda s: s["trades"].append(TRADE))      # must not raise
    assert len(store.snapshot()["trades"]) == 1 and store.revision == 1 and seen == [1]
    store.mutate(lambda s: s["watchlist"].append({"symbol": "VTI"}))   # and the next save is not a conflict


def test_failed_load_releases_lock(tmp_path):
    p = tmp_path / "app_state.json"
    p.write_text("{}")
    with pytest.raises(StateLoadError):
        StateStore(str(p))
    write(p, {})
    StateStore(str(p)).close()


def test_pull_runs_under_the_lock(tmp_path):
    from src.services.state_store import StateLockedError
    p = tmp_path / "app_state.json"
    write(p, {})
    owner = StateStore(str(p))
    pulled = []
    with pytest.raises(StateLockedError):
        StateStore(str(p), before_load=lambda: pulled.append(1))
    assert pulled == []
    owner.close()


def test_hooks_see_saves_in_commit_order(tmp_path):
    import threading
    p = tmp_path / "app_state.json"
    write(p, {})
    seen = []
    store = StateStore(str(p), on_saved=lambda rev, s: seen.append((rev, len(s["watchlist"]))))
    threads = [threading.Thread(target=lambda i=i: store.mutate(lambda s: s["watchlist"].append({"symbol": f"T{i}"})))
               for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert seen == [(i + 1, i + 1) for i in range(20)]
