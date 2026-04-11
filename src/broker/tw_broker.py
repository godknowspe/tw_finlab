import backtrader as bt

class TaiwanStockCommission(bt.CommInfoBase):
    """
    台股手續費與交易稅設定
    買進：手續費 0.1425% (可打折)
    賣出：手續費 0.1425% (可打折) + 證交稅 0.3%
    """
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True), # 手續費以百分比表示
        ('commission', 0.001425),
        ('tax', 0.003),
        ('discount', 0.6), # 券商手續費折扣 (預設 6 折)
        ('min_comm', 20.0), # 最低手續費 20 元
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        計算單筆交易的總手續費與稅金
        """
        # size > 0 為買進，size < 0 為賣出
        is_sell = size < 0

        # 基本手續費
        comm = abs(size) * price * self.p.commission * self.p.discount
        # 最低手續費門檻
        comm = max(self.p.min_comm, comm)

        # 如果是賣出，還要加上證交稅
        if is_sell:
            tax = abs(size) * price * self.p.tax
            comm += tax

        return comm
