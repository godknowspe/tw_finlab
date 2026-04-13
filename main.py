import datetime
from src.data.updater import update_stock_data
from src.engine.runner import BacktestRunner
from src.engine.strategy import SmaCross, MacdStrategy, RsiStrategy, BollingerBandsStrategy, KdStrategy

def main():
    stock_id = "2330"
    
    # 1. 抓取過去一年的資料 (確保資料齊全)
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    print("="*40)
    print(f"階段一：更新 {stock_id} 資料 ({start_date} ~ {end_date})")
    print("="*40)
    update_stock_data(stock_id, start_date, end_date)
    
    # 準備執行多個策略以進行比較
    strategies_to_test = [
        ("SMA 均線交叉", SmaCross, {}),
        ("MACD 交叉", MacdStrategy, {}),
        ("RSI 超買超賣", RsiStrategy, {}),
        ("布林通道", BollingerBandsStrategy, {}),
        ("KD 隨機指標", KdStrategy, {})
    ]

    for strat_name, strat_class, params in strategies_to_test:
        print("\n" + "#"*50)
        print(f"🚀 正在測試策略：{strat_name}")
        print("#"*50)

        # 2. 建立回測引擎 (設定初始資金 500 萬)
        runner = BacktestRunner(initial_cash=5000000.0)
        
        # 3. 載入資料
        runner.add_data(stock_id, start_date, end_date)
        
        # 4. 加入策略
        runner.add_strategy(strat_class, **params)
        
        # 5. 執行回測
        results = runner.run()

        # 6. 印出詳細報表
        if results:
            runner.print_report(results)
            
            # 7. 匯出績效圖表 (圖表檔案名稱帶上策略名稱)
            # 將中文名稱轉為英文或拼音以避免檔名問題
            safe_name = strat_class.__name__
            chart_filename = f"chart_{safe_name}.png"
            runner.plot_and_save(filename=chart_filename)

if __name__ == "__main__":
    main()
