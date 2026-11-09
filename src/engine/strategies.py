from src.engine.backtest import Strategy


class _UnitStrategy(Strategy):
    """Signals add one unit (one 1000-share lot for TW, `us_unit` shares for US) per buy
    signal and exit the whole position on a sell signal, as the original strategies did."""
    us_unit = 10

    @property
    def unit(self):
        return self.lot if self.lot > 1 else self.us_unit

    def enter(self, bar):
        if self.broker.cash > bar['close'] * self.unit:
            self.buy(self.unit)

    def exit(self):
        if self.broker.shares > 0:
            self.sell()


class RSISignals(_UnitStrategy):
    name = "RSI"
    def init(self):
        delta = self.data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.data['rsi'] = 100 - (100 / (1 + rs))

    def on_bar(self, i, bar):
        if bar['rsi'] < 30:
            self.enter(bar)
        elif bar['rsi'] > 70:
            self.exit()


class SMACross(_UnitStrategy):
    name = "SMA_Cross"
    def init(self):
        self.data['sma20'] = self.data['close'].rolling(20).mean()
        self.data['sma60'] = self.data['close'].rolling(60).mean()

    def on_bar(self, i, bar):
        if i < 1: return
        prev_bar = self.data.iloc[i-1]
        if prev_bar['sma20'] < prev_bar['sma60'] and bar['sma20'] > bar['sma60']:
            self.enter(bar)
        elif prev_bar['sma20'] > prev_bar['sma60'] and bar['sma20'] < bar['sma60']:
            self.exit()


class MACDStrategy(_UnitStrategy):
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
            self.enter(bar)
        # Death Cross: MACD crosses below Signal
        elif prev_bar['macd'] > prev_bar['signal'] and bar['macd'] < bar['signal']:
            self.exit()


class BollingerBandsStrategy(_UnitStrategy):
    name = "BollingerBands"
    def init(self):
        mid = self.data['close'].rolling(20).mean()
        std = self.data['close'].rolling(20).std()
        self.data['bb_up'] = mid + (std * 2)
        self.data['bb_low'] = mid - (std * 2)

    def on_bar(self, i, bar):
        if bar['close'] < bar['bb_low']:
            self.enter(bar)
        elif bar['close'] > bar['bb_up']:
            self.exit()


STRATEGIES = {
    "RSI": RSISignals,
    "SMA_Cross": SMACross,
    "MACD": MACDStrategy,
    "BollingerBands": BollingerBandsStrategy
}
