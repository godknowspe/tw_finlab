from prettytable import PrettyTable

def print_backtest_report(results):
    """印出詳細的回測績效報表"""
    strat = results[0]
    
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    
    table = PrettyTable()
    table.field_names = ["指標 (Metric)", "數值 (Value)"]
    table.align["指標 (Metric)"] = "l"
    table.align["數值 (Value)"] = "r"
    
    total_return = returns.get('rtot', 0) * 100
    table.add_row(["總報酬率 (Total Return)", f"{total_return:.2f}%"])
    
    sharpe_ratio = sharpe.get('sharperatio', None)
    sharpe_str = f"{sharpe_ratio:.4f}" if sharpe_ratio is not None else "N/A"
    table.add_row(["夏普值 (Sharpe Ratio)", sharpe_str])
    
    max_dd = drawdown.get('max', {}).get('drawdown', 0)
    table.add_row(["最大回撤 (Max Drawdown)", f"{max_dd:.2f}%"])
    
    total_trades = trades.get('total', {}).get('closed', 0)
    table.add_row(["總交易次數 (Total Trades)", str(total_trades)])
    
    if total_trades > 0:
        won_trades = trades.get('won', {}).get('total', 0)
        lost_trades = trades.get('lost', {}).get('total', 0)
        win_rate = (won_trades / total_trades) * 100
        table.add_row(["勝率 (Win Rate)", f"{win_rate:.2f}% ({won_trades}勝/{lost_trades}敗)"])
    else:
        table.add_row(["勝率 (Win Rate)", "N/A (無交易紀錄)"])
        
    print("\n" + table.get_string(title=f"📈 回測績效報表 ({strat.__class__.__name__})"))

