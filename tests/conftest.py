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
