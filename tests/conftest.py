import os
import pytest


@pytest.fixture(autouse=True)
def _isolate_portfolio_export(monkeypatch):
    # The exporter prefers PORTFOLIO_EXPORT_* env vars over the test's app_state,
    # so a developer shell with real credentials would push test data to the live gist.
    for key in list(os.environ):
        if key.startswith("PORTFOLIO_EXPORT_"):
            monkeypatch.delenv(key)

    def _no_network(*args, **kwargs):
        raise RuntimeError("tests must mock outbound HTTP to GitHub")

    monkeypatch.setattr("requests.patch", _no_network)
    monkeypatch.setattr("requests.put", _no_network)



@pytest.fixture(autouse=True)
def _offline_market_data(monkeypatch):
    """Tests never reach yfinance: quotes, kbars, FX and instrument lookups all fail as if
    offline. Tests that need prices pass them in or monkeypatch the service."""
    import yfinance
    import src.services.fx_service as fx
    monkeypatch.setattr(fx, "_cache", None)

    class _Offline:
        def __init__(self, *a, **k):
            raise RuntimeError("no network in tests")

    def _offline_download(*a, **k):
        raise RuntimeError("no network in tests")
    monkeypatch.setattr(yfinance, "Ticker", _Offline)
    monkeypatch.setattr(yfinance, "download", _offline_download)
    # Never refetch in tests: serve whatever the (test) cache holds.
    monkeypatch.setattr("src.services.market_data.MarketDataService.refresh", lambda self, *a, **k: False)
    monkeypatch.setattr("src.services.portfolio_exporter.stop_lookup", None)
