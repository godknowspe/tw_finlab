import datetime
import backtrader as bt
from prettytable import PrettyTable
from src.data.updater import update_stock_data
from src.data.fetcher import get_stock_data_df
from src.broker.tw_broker import TaiwanStockCommission
from src.engine.strategy import CustomCombinedStrategy

def main():
    stock_id = "2330"
    
    # 為了最佳化，我們抓取過去三年 (更長) 的資料來驗證
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=365*3)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    print(f"========================================")
    print(f"🔄 準備執行 {stock_id} 參數最佳化 ({start_date} ~ {end_date})")
    print(f"========================================")
    
    update_stock_data(stock_id, start_date, end_date)
    
    # 注意：最佳化時 optreturn=False 可以取回完整的分析器結果
    cerebro = bt.Cerebro(optreturn=False)
    cerebro.broker.setcash(5000000.0)
    
    # 設定交易成本
    comminfo = TaiwanStockCommission()
    cerebro.broker.addcommissioninfo(comminfo)
    
    # 載入資料
    df = get_stock_data_df(stock_id, start_date, end_date)
    data = bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open='open', high='high', low='low', close='close', volume='volume',
        openinterest=-1
    )
    cerebro.adddata(data, name=stock_id)
    
    # ==========================================
    # 設定最佳化參數組合
    # ==========================================
    print("載入組合策略，並測試不同的 rsi_safe (RSI 濾網) 與 sma_stop (停損均線) 參數...")
    cerebro.optstrategy(
        CustomCombinedStrategy,
        macd1=12, macd2=26, macdsig=9, # MACD 保持標準設定
        rsi_period=14,
        rsi_safe=range(50, 71, 10),    # 測試 50, 60, 70
        sma_stop=range(10, 31, 10)     # 測試 10MA, 20MA, 30MA
    )
    
    # 加入分析器
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    
    print("🚀 開始執行最佳化 (共有 3x3=9 種組合，請稍候)...")
    opt_results = cerebro.run()
    
    # ==========================================
    # 整理最佳化結果並印出報表
    # ==========================================
    table = PrettyTable()
    table.field_names = ["RSI 安全值", "停損均線", "總報酬率 (%)", "最大回撤 (%)"]
    
    # opt_results 會是一個 list of lists
    for run in opt_results:
        for strat in run:
            rsi_val = strat.params.rsi_safe
            sma_val = strat.params.sma_stop
            
            returns = strat.analyzers.returns.get_analysis().get('rtot', 0) * 100
            max_dd = strat.analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 0)
            
            table.add_row([
                rsi_val, 
                sma_val, 
                f"{returns:.2f}", 
                f"{max_dd:.2f}"
            ])
            
    # 將表格依報酬率由高到低排序並印出
    print("\n")
    print(table.get_string(sortby="總報酬率 (%)", reversesort=True, title="🏅 最佳化結果排行 (Optimization Results)"))

if __name__ == "__main__":
    main()
