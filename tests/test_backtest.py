import pandas as pd
import pytest

from src.engine.backtest import BacktestEngine, Strategy


class BuyFirstBar(Strategy):
    def on_bar(self, i, bar):
        if i == 0:
            self.buy(self.lot)


def frame(symbol, opens, closes):
    idx = pd.date_range("2026-01-01", periods=len(opens), freq="D")
    return pd.DataFrame({"open": opens, "high": opens, "low": opens, "close": closes,
                         "volume": 1e6, "stock_id": symbol}, index=idx)


def test_signal_fills_at_next_open_not_signal_close():
    res = BacktestEngine(frame("2330", [100, 120, 120], [100, 120, 120])).run(BuyFirstBar)
    assert res["trades"][0]["price"] == 120
    assert res["trades"][0]["date"] == pd.Timestamp("2026-01-02")


def test_return_measured_from_initial_cash_including_first_fee():
    res = BacktestEngine(frame("2330", [100, 100, 100], [100, 100, 100]), initial_cash=1_000_000).run(BuyFirstBar)
    fee = 100_000 * 0.001425
    assert res["final_equity"] == pytest.approx(1_000_000 - fee)
    assert res["total_return"] == pytest.approx(-fee / 1_000_000)
    assert res["max_drawdown"] < 0


def test_us_symbol_uses_us_costs_and_single_share_lot():
    engine = BacktestEngine(frame("VTI", [300, 300, 300], [300, 300, 300]))
    assert engine.costs["lot"] == 1 and engine.initial_cash == 30_000
    res = engine.run(BuyFirstBar)
    assert res["final_equity"] == pytest.approx(30_000)


class BuyMaxFirstBar(Strategy):
    def on_bar(self, i, bar):
        if i == 0:
            self.buy()


def test_invalid_next_open_drops_order():
    for bad in (0.0, -10.0, float("nan")):
        res = BacktestEngine(frame("VTI", [100, bad, 100], [100, 100, 100]), initial_cash=1000).run(BuyFirstBar)
        assert res["trades"] == [] and res["final_equity"] == 1000


def test_max_size_buy_accounts_for_minimum_fee():
    res = BacktestEngine(frame("2330", [1, 1, 1], [1, 1, 1]), initial_cash=2010).run(BuyMaxFirstBar)
    assert res["trades"][0]["size"] == 1000
