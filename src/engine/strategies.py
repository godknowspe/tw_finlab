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

class MACDStrategy(Strategy):
    name = "MACD"
    def init(self):
        exp1 = self.data['close'].ewm(span=12, adjust=False).mean()
        exp2 = self.data['close'].ewm(span=26, adjust=False).mean()
        self.data['macd'] = exp1 - exp2
        self.data['signal'] = self.data['macd'].ewm(span=9, adjust=False).mean()

    def on_bar(self, i, bar):
        if i < 1: return
        prev_bar = self.data.iloc[i-1]
        # Golden Cross: MACD crosses above Signal
        if prev_bar['macd'] < prev_bar['signal'] and bar['macd'] > bar['signal']:
            if self.broker.cash > bar['close'] * 1000:
                self.buy(i, self.data.iloc[i]['stock_id'], 1000)
        # Death Cross: MACD crosses below Signal
        elif prev_bar['macd'] > prev_bar['signal'] and bar['macd'] < bar['signal']:
            if self.broker.positions.get(self.data.iloc[i]['stock_id'], 0) > 0:
                self.sell(i, self.data.iloc[i]['stock_id'], self.broker.positions.get(self.data.iloc[i]['stock_id'], 0))

class BollingerBandsStrategy(Strategy):
    name = "BollingerBands"
    def init(self):
        mid = self.data['close'].rolling(20).mean()
        std = self.data['close'].rolling(20).std()
        self.data['bb_up'] = mid + (std * 2)
        self.data['bb_low'] = mid - (std * 2)

    def on_bar(self, i, bar):
        if bar['close'] < bar['bb_low'] and self.broker.cash > bar['close'] * 1000:
            self.buy(i, self.data.iloc[i]['stock_id'], 1000)
        elif bar['close'] > bar['bb_up'] and self.broker.positions.get(self.data.iloc[i]['stock_id'], 0) > 0:
            self.sell(i, self.data.iloc[i]['stock_id'], self.broker.positions.get(self.data.iloc[i]['stock_id'], 0))

STRATEGIES = {
    "RSI": RSISignals,
    "SMA_Cross": SMACross,
    "MACD": MACDStrategy,
    "BollingerBands": BollingerBandsStrategy
}
