import pandas as pd
import numpy as np

class Strategy:
    """策略基類，所有新策略都應該繼承這個類別"""
    def __init__(self):
        self.broker = None
        self.data = None
        self.params = {}

    def init(self):
        """策略初始化（例如計算指標）"""
        pass

    def on_bar(self, i, bar):
        """
        每一根 K 棒執行的邏輯
        i: 當前索引
        bar: 當前這根 K 棒的資料 (Series)
        """
        pass

    def buy(self, i, symbol, size=None):
        if self.broker:
            self.broker.submit_order(i, symbol, size, side='buy', price=self.data.iloc[i]['close'])

    def sell(self, i, symbol, size=None):
        if self.broker:
            self.broker.submit_order(i, symbol, size, side='sell', price=self.data.iloc[i]['close'])

class BacktestEngine:
    def __init__(self, data, initial_cash=1000000):
        self.data = data
        self.cash = initial_cash
        self.positions = {}  # {symbol: shares}
        self.history = []    # 紀錄淨值變化
        self.trades = []     # 紀錄交易細節
        
        # 台灣市場交易成本預設
        self.fee_rate = 0.001425  # 手續費
        self.tax_rate = 0.003     # 交易稅

    def run(self, strategy_cls):
        strategy = strategy_cls()
        strategy.data = self.data
        strategy.broker = self
        strategy.init()

        for i in range(len(self.data)):
            bar = self.data.iloc[i]
            strategy.on_bar(i, bar)
            self._update_history(bar)

        return self._calculate_performance()

    def submit_order(self, i, symbol, size, side, price):
        """模擬撮合"""
        if side == 'buy':
            cost = size * price * (1 + self.fee_rate)
            if self.cash >= cost:
                self.cash -= cost
                self.positions[symbol] = self.positions.get(symbol, 0) + size
                self.trades.append({'date': self.data.index[i], 'side': 'buy', 'price': price, 'size': size})
        elif side == 'sell':
            current_shares = self.positions.get(symbol, 0)
            if current_shares >= size:
                proceeds = size * price * (1 - self.fee_rate - self.tax_rate)
                self.cash += proceeds
                self.positions[symbol] -= size
                self.trades.append({'date': self.data.index[i], 'side': 'sell', 'price': price, 'size': size})

    def _update_history(self, bar):
        market_value = sum(self.positions[sym] * bar['close'] for sym in self.positions)
        self.history.append({
            'date': bar.name,
            'cash': self.cash,
            'market_value': market_value,
            'total_equity': self.cash + market_value
        })

    def _calculate_performance(self):
        df = pd.DataFrame(self.history)
        if df.empty: return {}
        
        total_return = (df['total_equity'].iloc[-1] / df['total_equity'].iloc[0]) - 1
        # 計算最大回撤
        df['cum_max'] = df['total_equity'].cummax()
        df['drawdown'] = (df['total_equity'] - df['cum_max']) / df['cum_max']
        max_dd = df['drawdown'].min()
        
        return {
            'total_return': total_return,
            'max_drawdown': max_dd,
            'final_equity': df['total_equity'].iloc[-1],
            'equity_curve': df
        }
