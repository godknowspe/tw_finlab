import json

import pytest

from src.services.state_store import StateStore
from src.tools.migrate_state import main, migrate

OLD = {
    "cash": {"TWD": 1000, "USD": 0},
    "watchlist": [{"symbol": "2330.TW"}, {"symbol": "2330"}],
    "trades": [
        {"id": 1, "symbol": "2330.TW", "action": "BUY", "shares": 1, "price": 10.0, "timestamp": "2026-05-03 10:23:45.123", "currency": "TWD"},
        {"id": "sj_abc", "symbol": "2330", "action": "SELL", "shares": 1, "price": 11.0, "timestamp": "2026-05-04 09:00:00", "currency": "TWD"},
    ],
}


def test_converts_old_ids_symbols_and_timestamps():
    state, notes, blockers = migrate(OLD)
    assert blockers == []
    assert [t["id"] for t in state["trades"]] == [1, 2]
    assert state["trades"][1]["source_trade_id"] == "abc" and state["trades"][1]["source"] == "Shioaji"
    assert state["trades"][0]["symbol"] == "2330" and state["trades"][0]["timestamp"] == "2026-05-03T10:23:45"
    assert [w["symbol"] for w in state["watchlist"]] == ["2330"]


@pytest.mark.parametrize("raw", [{}, {"trades": []}, {"trades": [], "watchlist": []}])
def test_missing_core_data_is_not_invented(raw):
    _, _, blockers = migrate(raw)
    assert blockers and "missing" in blockers[0]


def test_currency_mismatch_blocks():
    bad = json.loads(json.dumps(OLD))
    bad["trades"][0]["currency"] = "USD"
    assert migrate(bad)[2]


def test_write_refuses_while_server_owns_file_and_writes_atomically_otherwise(tmp_path):
    p = tmp_path / "app_state.json"
    p.write_text(json.dumps(OLD))
    from src.services.state_store import acquire_lock
    fd = acquire_lock(str(p))
    assert main([str(p), "--write"]) == 1
    assert json.loads(p.read_text())["trades"][1]["id"] == "sj_abc"
    import os; os.close(fd)
    assert main([str(p), "--write"]) == 0
    StateStore(str(p)).close()                           # migrated file loads
    assert len(list(tmp_path.glob("app_state.json.bak-*"))) == 1


def test_persisted_uids_match_what_the_server_derives(tmp_path):
    from src.services.state_store import parse_state
    current = {"cash": {"TWD": 1000, "USD": 0}, "watchlist": [],
               "trades": [{"id": 1, "symbol": "2330", "action": "BUY", "shares": 1, "price": 10.0,
                           "timestamp": "2026-05-03T10:23", "currency": "TWD"}]}
    derived = parse_state(current)["trades"][0]["uid"]
    migrated, notes, blockers = migrate(current)
    assert not blockers and migrated["trades"][0]["uid"] == derived
    assert any("uid assigned" in n for n in notes)
