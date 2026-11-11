import pytest

import src.services.fx_service as fx


class _Ticker:
    rate = 32.9

    def __init__(self, symbol):
        assert symbol == "TWD=X"

    @property
    def fast_info(self):
        return {"lastPrice": self.rate}


def test_live_rate_is_used_and_cached(monkeypatch):
    monkeypatch.setattr(fx.yf, "Ticker", _Ticker)
    assert fx.get_usd_twd(32.5) == (32.9, True)
    _Ticker.rate = 99999
    assert fx.get_usd_twd(32.5) == (32.9, True)          # cached


def test_falls_back_to_configured_rate_when_offline():
    assert fx.get_usd_twd(31.0) == (31.0, False)         # conftest makes yfinance unreachable


@pytest.mark.parametrize("bad", [0.0, 3290.0, float("nan")])
def test_implausible_rates_are_rejected(monkeypatch, bad):
    monkeypatch.setattr(fx.yf, "Ticker", type("T", (_Ticker,), {"rate": bad}))
    assert fx.get_usd_twd(32.5) == (32.5, False)
