import backtrader as bt
import matplotlib
# 設定 matplotlib 的 backend 為 Agg，避免在無介面環境或純產圖時跳出視窗阻塞程式
matplotlib.use('Agg')
from src.data.fetcher import get_stock_data_df
from src.broker.tw_broker import TaiwanStockCommission

class BacktestRunner:
    def __init__(self, initial_cash=100000.0):
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(initial_cash)
        
        # 設定台股專用交易成本
        comminfo = TaiwanStockCommission()
        self.cerebro.broker.addcommissioninfo(comminfo)
        
        # 加入績效分析器 (Analyzers)
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.01) # 無風險利率預設 1%
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    def add_data(self, stock_id: str, start_date: str = None, end_date: str = None):
        df = get_stock_data_df(stock_id, start_date, end_date)
        if df.empty:
            raise ValueError(f"No data found for {stock_id} in database. Please fetch data first.")
            
        # 將 DataFrame 匯入 Backtrader
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None, # 日期已經設為 Index
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest=-1 # 台股現貨無未平倉量
        )
        self.cerebro.adddata(data, name=stock_id)

    def add_strategy(self, strategy_class, **kwargs):
        self.cerebro.addstrategy(strategy_class, **kwargs)

    def run(self):
        print(f"--- 開始回測 ---")
        print(f"初始資金: {self.cerebro.broker.getvalue():.2f}")
        results = self.cerebro.run()
        print(f"最終資金: {self.cerebro.broker.getvalue():.2f}")
        return results

    def print_report(self, results):
        """印出詳細的回測績效報表"""
        strat = results[0]
        
        # 取得分析結果
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        returns = strat.analyzers.returns.get_analysis()

        print("\n" + "="*40)
        print("📊 回測績效報表 (Performance Report)")
        print("="*40)
        
        # 報酬率
        total_return = returns.get('rtot', 0) * 100
        print(f"總報酬率 (Total Return): {total_return:.2f}%")
        
        # 夏普值
        sharpe_ratio = sharpe.get('sharperatio', None)
        sharpe_str = f"{sharpe_ratio:.4f}" if sharpe_ratio is not None else "N/A"
        print(f"夏普值 (Sharpe Ratio): {sharpe_str}")
        
        # 最大回撤
        max_dd = drawdown.get('max', {}).get('drawdown', 0)
        print(f"最大回撤 (Max Drawdown): {max_dd:.2f}%")
        
        # 交易統計
        total_trades = trades.get('total', {}).get('closed', 0)
        if total_trades > 0:
            won_trades = trades.get('won', {}).get('total', 0)
            lost_trades = trades.get('lost', {}).get('total', 0)
            win_rate = (won_trades / total_trades) * 100
            print(f"總交易次數 (Total Trades): {total_trades}")
            print(f"勝率 (Win Rate): {win_rate:.2f}% ({won_trades} 勝 / {lost_trades} 敗)")
        else:
            print("總交易次數 (Total Trades): 0 (無交易紀錄)")
        print("="*40)

    def plot_and_save(self, filename="backtest_result.png"):
        """繪製並匯出圖表"""
        # 注意: cerebro.plot 預設會回傳包含 figure 的 list (例如 [[<Figure size 640x480 with 4 Axes>]])
        figs = self.cerebro.plot(style='candlestick', barup='red', bardown='green', volume=False)
        if figs and len(figs) > 0 and len(figs[0]) > 0:
            fig = figs[0][0]
            fig.savefig(filename, bbox_inches='tight')
            print(f"📈 績效圖表已成功匯出至: {filename}")
        else:
            print("⚠️ 無法產生圖表。")
