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
