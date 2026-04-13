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


class CustomCombinedStrategy(bt.Strategy):
    """自訂組合策略 (MACD 趨勢 + RSI 濾網 + SMA 停損)"""
    params = dict(
        macd1=12,
        macd2=26,
        macdsig=9,
        rsi_period=14,
        rsi_safe=60,   # RSI 低於這個值才買進 (避免追高)
        sma_stop=20    # 跌破 20MA 就停損
    )

    def __init__(self):
        # 1. 宣告所有需要用到的技術指標
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.macd1,
            period_me2=self.p.macd2,
            period_signal=self.p.macdsig
        )
        self.mcross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.sma_stop)

    def next(self):
        # 2. 定義買賣條件邏輯
        if not self.position:
            # 買進條件：MACD 黃金交叉，且 RSI 沒過熱 (< rsi_safe)
            if self.mcross > 0 and self.rsi < self.p.rsi_safe:
                self.buy(size=1000)
        else:
            # 賣出條件：MACD 死亡交叉，或是跌破 20 日均線 (強制停損)
            if self.mcross < 0 or self.data.close[0] < self.sma[0]:
                self.close()

class KdStrategy(bt.Strategy):
    """KD 指標 (Stochastic Oscillator) 策略"""
    params = dict(
        period=9,
        period_dfast=3,
        period_dslow=3,
        k_cross_up=20,  # K 值低於 20 黃金交叉買進
        k_cross_down=80 # K 值高於 80 死亡交叉賣出
    )

    def __init__(self):
        # 使用 StochasticFull 來計算 KD 值，預設對應參數 (9, 3, 3)
        self.stoch = bt.indicators.StochasticFull(
            self.data,
            period=self.p.period,
            period_dfast=self.p.period_dfast,
            period_dslow=self.p.period_dslow
        )
        # stoch.percK 是 K 值, stoch.percD 是 D 值
        self.k_cross_d = bt.indicators.CrossOver(self.stoch.percK, self.stoch.percD)

    def next(self):
        if not self.position:
            # 買進：K 向上交叉 D，且 K 值處於超賣區 (低檔打底)
            if self.k_cross_d > 0 and self.stoch.percK[0] < self.p.k_cross_up:
                self.buy(size=1000)
        else:
            # 賣出：K 向下交叉 D，且 K 值處於超買區 (高檔過熱)
            if self.k_cross_d < 0 and self.stoch.percK[0] > self.p.k_cross_down:
                self.close()
