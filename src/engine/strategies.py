from src.engine.backtest import Strategy

class RSISignals(Strategy):
    name = "RSI"
    def init(self):
        delta = self.data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.data['rsi'] = 100 - (100 / (1 + rs))

    def on_bar(self, i, bar):
        if bar['rsi'] < 30 and self.broker.cash > bar['close'] * 1000:
            self.buy(i, self.data.iloc[i]['stock_id'], 1000)
        elif bar['rsi'] > 70 and self.broker.positions.get(self.data.iloc[i]['stock_id'], 0) > 0:
            self.sell(i, self.data.iloc[i]['stock_id'], self.broker.positions.get(self.data.iloc[i]['stock_id'], 0))

class SMACross(Strategy):
    name = "SMA_Cross"
    def init(self):
        self.data['sma20'] = self.data['close'].rolling(20).mean()
        self.data['sma60'] = self.data['close'].rolling(60).mean()

    def on_bar(self, i, bar):
        if i < 1: return
        prev_bar = self.data.iloc[i-1]
        if prev_bar['sma20'] < prev_bar['sma60'] and bar['sma20'] > bar['sma60']:
            if self.broker.cash > bar['close'] * 1000:
                self.buy(i, self.data.iloc[i]['stock_id'], 1000)
        elif prev_bar['sma20'] > prev_bar['sma60'] and bar['sma20'] < bar['sma60']:
            if self.broker.positions.get(self.data.iloc[i]['stock_id'], 0) > 0:
                self.sell(i, self.data.iloc[i]['stock_id'], self.broker.positions.get(self.data.iloc[i]['stock_id'], 0))

STRATEGIES = {
    "RSI": RSISignals,
    "SMA_Cross": SMACross
}
