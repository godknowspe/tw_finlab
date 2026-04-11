import backtrader as bt

class SmaCross(bt.Strategy):
    """均線交叉策略"""
    params = dict(pfast=10, pslow=30)

    def __init__(self):
        sma1 = bt.ind.SMA(period=self.p.pfast)
        sma2 = bt.ind.SMA(period=self.p.pslow)
        self.crossover = bt.ind.CrossOver(sma1, sma2)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy(size=1000)
        elif self.crossover < 0:
            self.close()


class MacdStrategy(bt.Strategy):
    """MACD 策略"""
    params = dict(
        macd1=12,
        macd2=26,
        macdsig=9
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.macd1,
            period_me2=self.p.macd2,
            period_signal=self.p.macdsig
        )
        self.mcross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if not self.position:
            if self.mcross > 0: # MACD 黃金交叉
                self.buy(size=1000)
        elif self.mcross < 0: # MACD 死亡交叉
            self.close()


class RsiStrategy(bt.Strategy):
    """RSI 超買超賣策略"""
    params = dict(
        rsi_period=14,
        rsi_upper=70,
        rsi_lower=30
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if not self.position:
            if self.rsi < self.p.rsi_lower: # 超賣，買進
                self.buy(size=1000)
        else:
            if self.rsi > self.p.rsi_upper: # 超買，賣出
                self.close()


class BollingerBandsStrategy(bt.Strategy):
    """布林通道策略"""
    params = dict(
        period=20,
        devfactor=2.0
    )

    def __init__(self):
        self.bband = bt.indicators.BollingerBands(
            self.data.close, 
            period=self.p.period, 
            devfactor=self.p.devfactor
        )

    def next(self):
        if not self.position:
            if self.data.close[0] < self.bband.lines.bot[0]: # 突破下軌買進
                self.buy(size=1000)
        else:
            if self.data.close[0] > self.bband.lines.top[0]: # 突破上軌平倉
                self.close()
