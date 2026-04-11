import backtrader as bt
import matplotlib
# 設定 matplotlib 的 backend 為 Agg，避免在無介面環境或純產圖時跳出視窗阻塞程式
matplotlib.use('Agg')
from src.data.fetcher import get_stock_data_df
from src.broker.tw_broker import TaiwanStockCommission
from src.ui.reporter import print_backtest_report

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
        print_backtest_report(results)

    def plot_and_save(self, filename="backtest_result.png"):
        """繪製並匯出圖表"""
        # 注意: cerebro.plot 預設會回傳包含 figure 的 list
        figs = self.cerebro.plot(style='candlestick', barup='red', bardown='green', volume=False)
        if figs and len(figs) > 0 and len(figs[0]) > 0:
            fig = figs[0][0]
            fig.savefig(filename, bbox_inches='tight')
            print(f"📈 績效圖表已成功匯出至: {filename}")
        else:
            print("⚠️ 無法產生圖表。")
