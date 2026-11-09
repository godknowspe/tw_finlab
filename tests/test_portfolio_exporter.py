import os
import json
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from src.services.portfolio_exporter import trigger_portfolio_export

def test_portfolio_export_local():
    # Setup test app state with mock trades
    app_state = {
        "cash": {"TWD": 500000.0, "USD": 20000.0},
        "settings": {
            "usd_twd_rate": 32.5,
            "portfolio_export": {
                "methods": ["local"]
            }
        },
        "trades": [
            {
                "id": 1,
                "symbol": "0050",
                "action": "BUY",
                "shares": 1000,
                "price": 100.0,
                "timestamp": "2026-06-01T10:00",
                "currency": "TWD"
            },
            {
                "id": 2,
                "symbol": "AAPL",
                "action": "BUY",
                "shares": 10,
                "price": 150.0,
                "timestamp": "2026-06-01T10:30",
                "currency": "USD"
            },
            {
                "id": 3,
                "symbol": "AAPL",
                "action": "SELL",
                "shares": 10,
                "price": 160.0,
                "timestamp": "2026-06-01T11:00",
                "currency": "USD"
            }
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "portfolio.json")
        app_state["settings"]["portfolio_export"]["local_path"] = local_path
        
        # Trigger export
        trigger_portfolio_export(app_state)
        
        # Verify local file exists and contains correct data
        assert os.path.exists(local_path)
        with open(local_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        assert "portfolio" in data
        portfolio = data["portfolio"]
        
        # AAPL should be filtered out because net shares is 0
        # 0050 should be included with .TW appended
        assert len(portfolio) == 1
        item = portfolio[0]
        assert item["symbol"] == "0050.TW"
        assert item["market"] == "TW"
        assert item["quantity"] == 1000
        assert item["cost_basis"] == 100.0

@patch("src.services.portfolio_exporter.requests.patch")
def test_portfolio_export_gist(mock_patch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_patch.return_value = mock_response
    
    app_state = {
        "cash": {"TWD": 1000000.0, "USD": 50000.0},
        "settings": {
            "portfolio_export": {
                "methods": ["gist"],
                "github_token": "fake_token",
                "gist_id": "fake_gist_id"
            }
        },
        "trades": [
            {
                "id": 1,
                "symbol": "VTI",
                "action": "BUY",
                "shares": 5,
                "price": 300.0,
                "timestamp": "2026-06-01T10:00",
                "currency": "USD"
            }
        ]
    }
    
    # Trigger export
    trigger_portfolio_export(app_state)
    
    # Verify patch API was called
    mock_patch.assert_called_once()
    args, kwargs = mock_patch.call_args
    assert args[0] == "https://api.github.com/gists/fake_gist_id"
    assert kwargs["headers"]["Authorization"] == "token fake_token"
    
    payload = kwargs["json"]
    assert "files" in payload
    assert "portfolio.json" in payload["files"]
    content = json.loads(payload["files"]["portfolio.json"]["content"])
    
    assert len(content["portfolio"]) == 1
    assert content["portfolio"][0]["symbol"] == "VTI"
    assert content["portfolio"][0]["market"] == "US"
    assert content["portfolio"][0]["quantity"] == 5
    assert content["portfolio"][0]["cost_basis"] == 300.0


def _worker_state(n, methods=("gist",)):
    return {"settings": {"portfolio_export": {"methods": list(methods), "gist_id": "g", "github_token": "t"}},
            "trades": [{"id": i, "symbol": "VTI", "action": "BUY", "shares": 1, "price": 1.0,
                        "timestamp": f"2026-01-0{i}T00:00", "currency": "USD"} for i in range(1, n + 1)]}


def _drain(w, timeout=2.0):
    import time
    end = time.time() + timeout
    while time.time() < end and (w._pending is not None or w.status["state"] == "running"):
        time.sleep(0.02)
    time.sleep(0.05)


def test_export_worker_drops_older_revision_and_skips_unchanged():
    import threading
    from src.services.portfolio_exporter import ExportWorker
    sent, gate = [], threading.Event()

    def fake_export(state):
        gate.wait(2)
        sent.append(len(state["trades"]))
        return True

    w = ExportWorker(fake_export)
    w.submit(1, _worker_state(1))
    import time; time.sleep(0.1)       # revision 1 is in flight
    w.submit(3, _worker_state(3))
    w.submit(2, _worker_state(2))      # arrives late with an older revision: dropped
    gate.set()
    _drain(w)
    w.submit(4, _worker_state(3))      # same holdings and targets: not re-sent
    _drain(w)
    assert sent == [1, 3]
    assert w.status["state"] == "ok" and w.status["revision"] == 4


def test_export_worker_delivers_to_new_target_and_retries_failures():
    from src.services.portfolio_exporter import ExportWorker
    calls = []

    def flaky(state):
        calls.append(state["settings"]["portfolio_export"]["methods"])
        return len(calls) != 2          # second delivery fails once

    w = ExportWorker(flaky, retry_base=0.05)
    w.submit(1, _worker_state(1, methods=()))
    _drain(w)
    assert calls == [] and w.status["state"] == "disabled"
    w.submit(2, _worker_state(1, methods=("gist",)))
    _drain(w)
    w.submit(3, _worker_state(1, methods=("local",)))
    _drain(w, timeout=3)
    assert calls == [["gist"], ["local"], ["local"]]
    assert w.status["state"] == "ok"


def test_export_worker_hold_blocks_delivery():
    from src.services.portfolio_exporter import ExportWorker
    calls = []
    w = ExportWorker(lambda s: calls.append(1) or True)
    w.hold("pull failed")
    w.submit(1, _worker_state(1))
    _drain(w)
    assert calls == [] and w.status["state"] == "held"
