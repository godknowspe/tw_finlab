import copy
import uuid

import pytest

from src.domain.merge import MergeConflict, merge_states
from src.schemas.state import AppState


def tr(id, sym="VTI", action="BUY", shares=1, price=100.0, ts="2026-06-01T10:00", **kw):
    return {"uid": kw.pop("uid", str(uuid.uuid4())), "id": id, "symbol": sym, "action": action, "shares": shares,
            "price": price, "timestamp": ts, "currency": "TWD" if sym.isdigit() else "USD", **kw}


def doc(**kw):
    base = {"cash": {"TWD": 1000000.0, "USD": 50000.0}, "watchlist": [{"symbol": "VTI"}], "trades": [],
            "agent_state": {"halted": False}}
    base.update(kw)
    return AppState.model_validate(base).model_dump(mode="json")


T1 = tr(1)
BASE = doc(trades=[T1])


def with_trades(*extra, base=BASE):
    return doc(trades=copy.deepcopy(base["trades"]) + list(extra))


def symbols(state):
    return sorted(t["symbol"] for t in state["trades"])


def test_concurrent_additions_with_same_id_both_survive():
    m = merge_states(BASE, with_trades(tr(2, "QQQ", ts="2026-06-02T10:00")), with_trades(tr(2, "0050", shares=1000, price=90.0)))
    assert symbols(m) == ["0050", "QQQ", "VTI"]
    assert sorted(t["id"] for t in m["trades"]) == [1, 2, 2]       # ids are never renumbered


def test_identical_real_trades_are_never_collapsed():
    """Two separate fills with identical fields stay two, on one side, in base, or across hosts."""
    twin_a, twin_b = tr(2, ts="2026-06-02T10:00"), tr(3, ts="2026-06-02T10:00")
    assert len(merge_states(BASE, with_trades(twin_a, twin_b), doc(trades=[T1], watchlist=[]))["trades"]) == 3
    base2 = with_trades(twin_a, twin_b)
    assert len(merge_states(base2, with_trades(tr(4, "QQQ"), base=base2), doc(trades=base2["trades"], watchlist=[]))["trades"]) == 4
    assert len(merge_states(BASE, with_trades(tr(2, ts="2026-06-02T10:00")), with_trades(tr(2, ts="2026-06-02T10:00")))["trades"]) == 3


def test_edit_conflicts_are_detected_by_identity():
    edited_here = doc(trades=[{**T1, "price": 101.0}])
    edited_there = doc(trades=[{**T1, "price": 102.0}])
    with pytest.raises(MergeConflict, match="changed on both hosts"):
        merge_states(BASE, edited_here, edited_there)
    with pytest.raises(MergeConflict):
        merge_states(BASE, doc(trades=[]), edited_there)              # deleted here, edited there
    m = merge_states(BASE, doc(trades=[]), with_trades(tr(2, "QQQ")))  # deleted here, untouched there
    assert symbols(m) == ["QQQ"]


def test_same_broker_execution_merges_once_or_conflicts_if_it_differs():
    fill = dict(sym="2330", shares=1000, price=500.0, ts="2026-06-02T09:01:00", source="Shioaji", source_trade_id="A:1")
    m = merge_states(BASE, with_trades(tr(2, **fill)), with_trades(tr(2, **fill)))      # different uids
    assert symbols(m) == ["2330", "VTI"]
    with pytest.raises(MergeConflict, match="broker execution"):
        merge_states(BASE, with_trades(tr(2, **fill)), with_trades(tr(2, **{**fill, "shares": 2000})))


def test_same_symbol_added_on_both_with_different_metadata_conflicts():
    a = doc(trades=[T1], watchlist=[{"symbol": "VTI"}, {"symbol": "2330", "name": "TSMC"}])
    b = doc(trades=[T1], watchlist=[{"symbol": "VTI"}, {"symbol": "2330", "name": "台積電"}])
    with pytest.raises(MergeConflict):
        merge_states(BASE, a, b)


def test_watchlist_and_settings_merge_per_element():
    ours = doc(trades=[T1], watchlist=[{"symbol": "VTI"}, {"symbol": "2330"}])
    theirs = doc(trades=[T1], watchlist=[], settings={"usd_twd_rate": 31.0})
    m = merge_states(BASE, ours, theirs)
    assert [w["symbol"] for w in m["watchlist"]] == ["2330"]
    assert m["settings"]["usd_twd_rate"] == 31.0 and m["agent_state"] == {"halted": False}


def test_merge_that_would_oversell_is_a_conflict():
    with pytest.raises(MergeConflict, match="does not replay"):
        merge_states(BASE, with_trades(tr(2, action="SELL", ts="2026-06-02T10:00")),
                     with_trades(tr(3, action="SELL", ts="2026-06-02T11:00")))


def test_conflict_reasons_never_contain_values():
    secret = "ghp_" + "x" * 30
    ours = doc(trades=[T1], settings={"portfolio_export": {"github_token": secret + "1"}})
    theirs = doc(trades=[T1], settings={"portfolio_export": {"github_token": secret + "2"}})
    with pytest.raises(MergeConflict) as e:
        merge_states(BASE, ours, theirs)
    assert secret not in str(e.value) and "settings.portfolio_export" in str(e.value)


def test_legacy_trades_get_the_same_uid_on_every_host():
    legacy = {"id": 7, "symbol": "VTI", "action": "BUY", "shares": 1, "price": 1.0, "timestamp": "2026-01-01T00:00", "currency": "USD"}
    one = doc(trades=[legacy])["trades"][0]["uid"]
    two = doc(trades=[dict(legacy)])["trades"][0]["uid"]
    assert one == two


def test_same_broker_execution_with_different_fees_conflicts():
    fill = dict(sym="2330", shares=1000, price=500.0, ts="2026-06-02T09:01:00", source="Shioaji", source_trade_id="A:1")
    with pytest.raises(MergeConflict, match="broker execution"):
        merge_states(BASE, with_trades(tr(2, **fill)), with_trades(tr(2, fee=157.0, tax=330.0, **fill)))
