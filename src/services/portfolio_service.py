import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from loguru import logger
from src.api.shioaji_api import fetch_shioaji_positions

class PortfolioService:
    def __init__(self, initial_cash_twd: float, initial_cash_usd: float, usd_twd_rate: float = 32.5, shioaji_api: Optional[Any] = None):
        self.initial_cash_twd = initial_cash_twd
        self.initial_cash_usd = initial_cash_usd
        self.usd_twd_rate = usd_twd_rate
        self.shioaji_api = shioaji_api

    def calculate_positions(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        根據成交紀錄計算目前的部位、平均成本、剩餘現金
        """
        positions = {}
        # 區分手動美股與自動台股
        us_trades = [t for t in trades if t.get("currency") == "USD" or not (t["symbol"].isdigit() or ".TW" in t["symbol"])]
        
        cash_twd = self.initial_cash_twd
        cash_usd = self.initial_cash_usd
        realized_pnl_twd = 0.0
        realized_pnl_usd = 0.0

        # 1. 處理手動美股 (從 Trades 計算)
        sorted_us_trades = sorted(us_trades, key=lambda x: x["timestamp"])
        for t in sorted_us_trades:
            sym = t["symbol"]
            shares = t["shares"]
            price = t["price"]
            currency = t.get("currency", "USD")
            
            if sym not in positions:
                positions[sym] = {"shares": 0, "avg_cost": 0.0, "currency": currency, "realized_pnl": 0.0}
            
            pos = positions[sym]
            if t["action"] == "BUY":
                pos["avg_cost"] = ((pos["shares"] * pos["avg_cost"]) + (shares * price)) / (pos["shares"] + shares)
                pos["shares"] += shares
                cash_usd -= (shares * price)
            elif t["action"] == "SELL":
                sell_shares = min(shares, pos["shares"])
                realized_pnl_usd += (price - pos["avg_cost"]) * sell_shares
                pos["realized_pnl"] += (price - pos["avg_cost"]) * sell_shares
                pos["shares"] -= sell_shares
                cash_usd += (sell_shares * price)

        # 2. 處理台股 (一律從 Trades 計算，確保手動輸入的 Trade 會反映在庫存、現金與已實現損益中)
        tw_trades = [t for t in trades if t not in us_trades]
        sorted_tw_trades = sorted(tw_trades, key=lambda x: x["timestamp"])
        for t in sorted_tw_trades:
            sym = t["symbol"]
            if sym not in positions:
                positions[sym] = {"shares": 0, "avg_cost": 0.0, "currency": "TWD", "realized_pnl": 0.0}
            pos = positions[sym]
            if t["action"] == "BUY":
                pos["avg_cost"] = ((pos["shares"] * pos["avg_cost"]) + (t["shares"] * t["price"])) / (pos["shares"] + t["shares"])
                pos["shares"] += t["shares"]
                cash_twd -= (t["shares"] * t["price"])
            elif t["action"] == "SELL":
                sell_shares = min(t["shares"], pos["shares"])
                realized_pnl_twd += (t["price"] - pos["avg_cost"]) * sell_shares
                pos["shares"] -= sell_shares
                cash_twd += (sell_shares * t["price"])

        # 如果 Shioaji API 可用，我們僅更新從真實帳戶取得的未實現盈虧與即時價格，不覆蓋手動帳本的股數
        if self.shioaji_api:
            try:
                logger.info("Syncing Taiwan positions from Shioaji API for real PnL and pricing...")
                sj_positions = fetch_shioaji_positions(self.shioaji_api)
                for p in sj_positions:
                    sym = p["symbol"]
                    if sym in positions:
                        # 僅附加 broker 提供的真實 PnL 與報價，保留 Ledger 計算出來的 shares 與 avg_cost
                        positions[sym]["real_pnl"] = p.get("real_pnl", 0.0)
                        positions[sym]["api_last_price"] = p.get("last_price")
            except Exception as e:
                logger.error(f"Failed to sync Shioaji positions for PnL: {e}")

        return {
            "positions": positions,
            "cash": {"TWD": cash_twd, "USD": cash_usd},
            "realized_pnl": {"TWD": realized_pnl_twd, "USD": realized_pnl_usd}
        }

    def enrich_portfolio(self, portfolio_data: Dict[str, Any], latest_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        結合即時報價，計算未實現損益與總資產
        """
        enriched_positions = []
        total_market_value_twd = 0.0
        total_market_value_usd = 0.0
        
        positions = portfolio_data["positions"]
        cash = portfolio_data["cash"]
        
        def safe_json_float(v, default=0.0):
            """確保數值是 JSON 相容的（非 NaN/Inf）"""
            if pd.isna(v) or np.isinf(v):
                return default
            return float(v)

        for sym, pos in positions.items():
            if pos["shares"] <= 0:
                continue
                
            # 優先使用 API 回傳的價格，若無則用最新報價，再無則用成本
            last_price = pos.get("api_last_price") or latest_prices.get(sym, pos["avg_cost"])
            
            # 處理 last_price 為 NaN 的情況
            if pd.isna(last_price) or np.isinf(last_price):
                last_price = pos["avg_cost"]
                
            market_value = last_price * pos["shares"]
            
            # 盈虧計算：若有 API 傳回的真實盈虧則優先使用，否則自行計算
            if "real_pnl" in pos and pos["currency"] == "TWD":
                unrealized = pos["real_pnl"]
            else:
                unrealized = market_value - (pos["avg_cost"] * pos["shares"])
            
            # 轉換為 JSON 安全的 float
            market_value = safe_json_float(market_value)
            unrealized = safe_json_float(unrealized)
            last_price = safe_json_float(last_price)
            avg_cost = safe_json_float(pos["avg_cost"])
            
            if pos["currency"] == "TWD":
                total_market_value_twd += market_value
            else:
                total_market_value_usd += market_value
                
            enriched_positions.append({
                "symbol": sym,
                "shares": int(pos["shares"]),
                "avg_cost": round(avg_cost, 2),
                "unrealized": int(unrealized) if pos["currency"] == "TWD" else round(unrealized, 2),
                "currency": pos["currency"],
                "market_value": int(market_value) if pos["currency"] == "TWD" else round(market_value, 2),
                "last_price": round(last_price, 2)
            })

        equiv_cash_twd = safe_json_float(cash["TWD"]) + (safe_json_float(cash["USD"]) * self.usd_twd_rate)
        equiv_mv_twd = total_market_value_twd + (total_market_value_usd * self.usd_twd_rate)
        
        return {
            "positions": enriched_positions,
            "cash": {
                "TWD": safe_json_float(cash["TWD"]),
                "USD": safe_json_float(cash["USD"])
            },
            "summary": {
                "market_value_twd": safe_json_float(total_market_value_twd),
                "market_value_usd": safe_json_float(total_market_value_usd),
                "total_equity_twd": safe_json_float(equiv_cash_twd + equiv_mv_twd)
            }
        }
