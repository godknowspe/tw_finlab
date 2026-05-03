import shioaji as sj
import pandas as pd
import time
from typing import Optional

class ShioajiClient:
    _instance = None
    _api = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShioajiClient, cls).__new__(cls)
        return cls._instance

    def get_api(self, api_key: str = "", api_secret: str = ""):
        if self._api is None:
            self._api = sj.Shioaji()
            if api_key and api_secret:
                self._api.login(
                    api_key=api_key,
                    secret_key=api_secret
                )
        return self._api

def fetch_shioaji_positions(api) -> list:
    """
    獲取 Shioaji 真實帳戶庫存明細
    """
    try:
        # 取得所有證券庫存
        positions = api.list_positions(api.stock_account)
        results = []
        for p in positions:
            # 判斷是否為張數 (Shioaji API 回傳 quantity 為張數時，需乘 1000)
            # 註：有些帳戶設定或標的可能是股，但標準整股庫存 p.quantity 是張
            # 檢查 contract.unit，如果是 1000 代表 quantity 單位是張
            contract = api.Contracts.Stocks[p.code]
            unit = getattr(contract, 'unit', 1000)
            total_shares = int(p.quantity * unit)
            
            results.append({
                "symbol": p.code,
                "shares": total_shares,
                "avg_cost": float(p.price),
                "market": "TW",
                "currency": "TWD",
                "real_pnl": float(p.pnl), # 直接取用券商計算的真實 PnL
                "last_price": float(p.last_price)
            })
        return results
    except Exception as e:
        print(f"Error fetching Shioaji positions: {e}")
        return []

def fetch_shioaji_trades(api) -> list:
    """
    獲取 Shioaji 當日成交紀錄 (可以用於同步)
    """
    try:
        # list_trades() 回傳的是當日的委託單與成交狀態
        trades = api.list_trades()
        results = []
        for t in trades:
            # 只處理有成交的部分 (Status.Filled)
            if t.status.status == 'Filled':
                # 計算該筆委託的總成交金額與股數
                # t.trades 包含了該委託下所有的細分成單
                for detail in t.trades:
                    results.append({
                        "id": f"sj_{detail.trade_id}", # 使用 Shioaji 的交易 ID 避免重複
                        "symbol": t.contract.code,
                        "action": "BUY" if t.order.action == 'Buy' else "SELL",
                        "shares": int(detail.quantity),
                        "price": float(detail.price),
                        "timestamp": detail.ts, # 格式為 '2026-05-03 10:23:45.123'
                        "currency": "TWD",
                        "source": "Shioaji"
                    })
        return results
    except Exception as e:
        print(f"Error fetching Shioaji trades: {e}")
        return []

def fetch_shioaji_kbars(api, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取 Shioaji K 線資料
    """
    # 判斷市場 (暫時只處理台股)
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return pd.DataFrame()

    kbars = api.kbars(
        contract=contract,
        start=start_date,
        end=end_date
    )
    
    df = pd.DataFrame({**kbars})
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.rename(columns={
            "ts": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        # 轉換為 date 格式以符合現有邏輯
        df["date"] = df["date"].dt.date
        df["stock_id"] = stock_id
        
    return df

def fetch_shioaji_quote(api, stock_id: str) -> Optional[float]:
    """
    獲取 Shioaji 即時報價 (快照)
    """
    contract = api.Contracts.Stocks[stock_id]
    if not contract:
        return None
    
    # 訂閱或直接抓快照
    snapshot = api.snapshots([contract])
    if snapshot:
        return float(snapshot[0].close)
    return None
