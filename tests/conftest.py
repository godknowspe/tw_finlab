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
def _offline_fx(monkeypatch):
    """The live USD/TWD lookup must not reach yfinance from tests; act as if it is offline."""
    import src.services.fx_service as fx
    monkeypatch.setattr(fx, "_cache", None)

    class _Offline:
        def __init__(self, *a, **k):
            raise RuntimeError("no network in tests")
    monkeypatch.setattr(fx.yf, "Ticker", _Offline)
