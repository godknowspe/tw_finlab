import pytest
import datetime
from src.data.updater import update_stock_data
from src.engine.runner import BacktestRunner
from src.engine.strategy import SmaCross

def test_e2e_sma_cross():
    stock_id = "2330"
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    # 1. Update data
    update_stock_data(stock_id, start_date, end_date)
    
    # 2. Setup runner
    runner = BacktestRunner(initial_cash=1000000.0)
    runner.add_data(stock_id, start_date, end_date)
    runner.add_strategy(SmaCross)
    
    # 3. Run
    results = runner.run()
    assert len(results) > 0
    
    # 4. Assert strategy finished
    strat = results[0]
    assert strat is not None
