import importlib
import json

import pytest
from fastapi.testclient import TestClient

TRADES = [
    {"id": 1, "symbol": "0050", "action": "BUY", "shares": 1000, "price": 100.0, "timestamp": "2026-06-01T10:00", "currency": "TWD"},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    state = tmp_path / "app_state.json"
    state.write_text(json.dumps({"trades": TRADES, "watchlist": [{"symbol": "0050"}], "cash": {"TWD": 1000000, "USD": 0}}))
    monkeypatch.setenv("TW_FINLAB_STATE_FILE", str(state))
    monkeypatch.setenv("TW_FINLAB_DB_URL", f"sqlite:///{tmp_path / 'db.sqlite'}")
    monkeypatch.setattr("src.services.quote_service.get_quotes", lambda symbols, api=None: {"0050": (110.0, 105.0)})
    monkeypatch.setattr("src.web.routes_portfolio.get_quotes", lambda symbols, api=None: {"0050": (110.0, 105.0)})
    import sys
    if "src.web.server" in sys.modules:
        sys.modules["src.web.server"].deps._state.close()
        server = importlib.reload(sys.modules["src.web.server"])
    else:
        import src.web.server as server
    with TestClient(server.app) as c:
        c.state_path = state
        yield c
    server.deps._state.close()


def test_portfolio_values_positions(client):
    d = client.get("/api/portfolio").json()
    assert d["positions"][0]["market_value"] == 110_000
    assert d["watchlist"][0]["chg_pct"] == "+4.76%"
    # The 100,000 buy is a deposit (state cash is ignored), so no cash is left over.
    assert d["summary"]["cash_twd"] == 0 and d["summary"]["deposited_twd"] == 100_000
    assert d["summary"]["total_equity_twd"] == 110_000
    assert d["positions"][0]["break_even"] == 100.0


def test_add_trade_validates_and_persists(client):
    bad = client.post("/api/trades", json={"symbol": "0050", "action": "SELL", "shares": 5000, "price": 1, "timestamp": "2026-06-02T10:00"})
    assert bad.status_code == 422 and "only 1000 held" in bad.text
    assert client.post("/api/trades", json={"symbol": "AAPL", "action": "BUY", "shares": 0, "price": 1, "timestamp": "2026-06-02T10:00"}).status_code == 422

    ok = client.post("/api/trades", json={"symbol": "aapl", "action": "BUY", "shares": 2, "price": 150, "timestamp": "2026-06-02 22:30"})
    assert ok.status_code == 200
    saved = json.loads(client.state_path.read_text())["trades"][-1]
    assert saved["symbol"] == "AAPL" and saved["currency"] == "USD" and saved["timestamp"] == "2026-06-02T22:30" and saved["id"] == 2


def test_delete_trade_that_would_strand_a_sell_is_rejected(client):
    client.post("/api/trades", json={"symbol": "0050", "action": "SELL", "shares": 1000, "price": 120, "timestamp": "2026-06-03T10:00"})
    uid = json.loads(client.state_path.read_text())["trades"][0]["uid"]
    assert client.delete(f"/api/trades/{uid}").status_code == 422
    assert client.delete("/api/trades/not-a-uid").status_code == 404


def test_config_never_returns_secrets(client):
    client.post("/api/config", json={"kline": "yfinance", "realtime": "yfinance", "shioaji_api_key": "k", "shioaji_api_secret": "s"})
    cfg = client.get("/api/config").json()
    assert "shioaji_api_key" not in cfg and cfg["shioaji_api_key_set"] is True
    client.post("/api/config", json={"kline": "yfinance", "realtime": "yfinance"})
    assert client.get("/api/config").json()["shioaji_api_secret_set"] is True


def test_sync_trades_reports_count_and_dedups_within_batch(client, monkeypatch):
    fill = {"symbol": "0050", "action": "BUY", "shares": 1000, "price": 101.0, "timestamp": "2026-06-02T09:01:00",
            "currency": "TWD", "source": "Shioaji", "source_trade_id": "A1:1"}
    monkeypatch.setattr("src.web.routes_portfolio.shioaji_api_if_enabled", lambda cfg: object())
    monkeypatch.setattr("src.api.shioaji_api.fetch_shioaji_trades", lambda api: [fill, dict(fill)])
    r = client.post("/api/sync/trades")
    assert r.json()["message"] == "Synced 1 new trades from Shioaji."
    assert client.post("/api/sync/trades").json()["message"] == "Synced 0 new trades from Shioaji."
    assert len(json.loads(client.state_path.read_text())["trades"]) == 2


def test_kbars_reports_bar_end(client, monkeypatch):
    import pandas as pd
    idx = pd.date_range("2026-06-01", periods=3, freq="D")
    df = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": [100.0, 105.0, 110.0], "volume": 1.0}, index=idx)
    monkeypatch.setattr("src.web.routes_market.MarketDataService.get_bars", lambda self, sym, interval: df)
    bars = client.get("/api/kbars/0050?interval=1d").json()
    assert bars[0]["time"] == "2026-06-01" and bars[0]["end"] == int(pd.Timestamp("2026-06-02", tz="UTC").timestamp())
    assert bars[-1]["total_pnl"] == 10_000


def test_new_trades_get_a_uid_and_portfolio_version_matches_its_data(client):
    v1 = client.get("/api/portfolio").json()["revision"]
    client.post("/api/trades", json={"symbol": "VTI", "action": "BUY", "shares": 1, "price": 100, "timestamp": "2026-06-02T10:00"})
    d = client.get("/api/portfolio").json()
    assert d["revision"] != v1 and client.get("/api/revision").json()["revision"] == d["revision"]
    assert all(len(t["uid"]) == 36 for t in d["trades"])


@pytest.mark.parametrize("env, expected", [
    ({"TW_FINLAB_EXPORT": "0"}, "off"),          # explicit non-publisher stays off even without git
    ({}, "off"),                                 # explicit state path but no role: not a publisher
    ({"TW_FINLAB_EXPORT": "1"}, None),           # publisher: not "off"
])
def test_publisher_role_is_configuration_not_inferred(tmp_path, monkeypatch, env, expected):
    import sys
    state = tmp_path / "app_state.json"          # not in a git repo: git discovery "fails"
    state.write_text(json.dumps({"trades": [], "watchlist": [], "cash": {"TWD": 0, "USD": 0}}))
    monkeypatch.setenv("TW_FINLAB_STATE_FILE", str(state))
    monkeypatch.setenv("TW_FINLAB_DB_URL", f"sqlite:///{tmp_path / 'db.sqlite'}")
    monkeypatch.delenv("TW_FINLAB_EXPORT", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    if "src.web.server" in sys.modules:
        sys.modules["src.web.server"].deps._state.close()
        server = importlib.reload(sys.modules["src.web.server"])
    else:
        import src.web.server as server
    status = server.deps.sync_status()["export"]["state"]
    server.deps._state.close()
    assert (status == "off") if expected == "off" else (status != "off")


def test_intraday_rejects_non_tw_and_unconfigured_shioaji(client):
    assert client.get("/api/intraday/VTI").status_code == 422
    assert client.get("/api/intraday/%5EGSPC").status_code == 422
    assert client.get("/api/intraday/0050?interval=7").status_code == 422
    r = client.get("/api/intraday/0050")
    assert r.status_code == 503 and "Shioaji" in r.json()["detail"]


def test_regime_endpoints_degrade_without_history(client):
    r = client.get("/api/regime/NOPE")
    assert r.status_code == 200 and r.json()["available"] is False
    r = client.get("/api/regime-trips")
    assert r.status_code == 200 and r.json() == {"trips": [], "groups": []}


def _intraday_with(monkeypatch, services):
    """Drive /api/intraday with scripted Shioaji services: each call to the factory yields the next one."""
    from src.web import routes_market as rm
    seq = iter(services)
    resets = []

    class Fake:
        pass

    rm._intraday["service"] = rm._intraday["api"] = None
    def factory(db):
        if rm._intraday["service"] is None:
            rm._intraday["service"], rm._intraday["api"] = next(seq), Fake()
        return rm._intraday["service"]
    monkeypatch.setattr(rm, "_intraday_service", factory)
    monkeypatch.setattr(rm.ShioajiClient, "reset", lambda self, api=None: resets.append(api))
    return resets


def _bars_service(rows=None, error=None):
    import pandas as pd
    from src.services.intraday import IntradayBars

    class Svc:
        def get(self, code):
            if error:
                raise error
            b = IntradayBars()
            b.add_tick("2026-11-13 09:00:10", 100.0, 1)
            b.add_tick("2026-11-13 09:01:10", 101.0, 1)
            return b
    return Svc()


def test_intraday_recovers_from_a_dead_shioaji_session(client, monkeypatch):
    import shioaji as sj
    resets = _intraday_with(monkeypatch, [_bars_service(error=sj.ShioajiConnectionError("SessionNotEstablished")), _bars_service()])
    r = client.get("/api/intraday/0050")
    assert r.status_code == 200 and len(r.json()) == 2           # the retry on a fresh session succeeded
    assert len(resets) == 1                                        # the dead session was dropped exactly once


def test_intraday_reports_a_persistent_outage_as_503_with_the_reason(client, monkeypatch):
    import shioaji as sj
    _intraday_with(monkeypatch, [_bars_service(error=sj.ShioajiConnectionError("down")), _bars_service(error=sj.ShioajiConnectionError("still down"))])
    r = client.get("/api/intraday/0050")
    assert r.status_code == 503 and "connection lost" in r.json()["detail"]


def test_intraday_serves_the_taiex_and_maps_cooldown_and_budget_errors(client, monkeypatch):
    from src.api.shioaji_api import ShioajiCoolingDown
    from src.services.intraday import RateLimited
    _intraday_with(monkeypatch, [_bars_service()])
    assert client.get("/api/intraday/%5ETWII").status_code == 200
    _intraday_with(monkeypatch, [_bars_service(error=ShioajiCoolingDown("5s ago"))])
    assert client.get("/api/intraday/0050").status_code == 503
    _intraday_with(monkeypatch, [_bars_service(error=RateLimited("20 calls"))])
    assert client.get("/api/intraday/0050").status_code == 429
