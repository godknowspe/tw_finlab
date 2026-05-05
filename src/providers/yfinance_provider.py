import yfinance as yf
import pandas as pd
from typing import Optional
from loguru import logger
from .base import BaseDataProvider
from src.utils.retry import retry

class YFinanceProvider(BaseDataProvider):
    @retry(max_attempts=3, delay=2, backoff=2)
    def fetch_kbars(self, stock_id: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame:
        logger.info(f"Fetching kbars for {stock_id} from {start_date} to {end_date} (interval: {interval})")
        # yfinance 的股票代號處理
        if stock_id.startswith("^"):
            ticker_id = stock_id
        elif "." in stock_id:
            ticker_id = stock_id
        elif stock_id.isdigit():
            ticker_id = f"{stock_id}.TW"
        else:
            ticker_id = stock_id
        
        # 修正 yfinance 的 interval 映射 (yf 使用 '1wk' 和 '1mo')
        yf_interval = interval
        if interval == '1w': yf_interval = '1wk'
        elif interval == '1m': yf_interval = '1mo'
        
        # 處理分鐘層級資料的限制 (yfinance 限制 start_date 不能太久以前)
        # 15m 最多 60 天, 1h 最多 730 天
        # 注意：yfinance 的 start/end 是「包含」的，且對時區很敏感，建議分鐘級資料直接用 period
        
        if interval.endswith('m') or interval.endswith('h') or interval in ['1h', '60m', '15m', '30m']:
            # 優先使用 period 模式，因為 start/end 在分鐘級資料極易觸發 "The requested range must be within..." 錯誤
            download_kwargs = {
                "interval": yf_interval,
                "progress": False
            }
            if interval == '15m' or interval == '30m':
                download_kwargs["period"] = "60d"
            else:
                download_kwargs["period"] = "730d"
        else:
            # 日、週、月 K 線使用 start/end 模式
            download_kwargs = {
                "start": start_date,
                "end": end_date,
                "interval": yf_interval,
                "progress": False
            }

        df = yf.download(ticker_id, **download_kwargs)
        
        if df.empty:
            return pd.DataFrame()
            
        # 修正 yfinance 2.0+ / cache 可能回傳 MultiIndex 或 Price 等級欄位的問題
        if isinstance(df.columns, pd.MultiIndex):
            # 新版 yfinance (如 1.2.0+ 或 0.2.x) 常用 'Price' 作為 level 名稱
            if 'Price' in df.columns.names:
                df.columns = df.columns.get_level_values('Price')
            elif 'Ticker' in df.columns.names:
                # 處理像測試中看到的 MultiIndex: [Price, Ticker]
                df.columns = df.columns.get_level_values(0)
            else:
                df.columns = df.columns.get_level_values(0)
        
        # 移除可能重複的列並重設索引
        df = df.reset_index()
        df.columns = [str(col).lower() for col in df.columns]
        
        # 統一欄位名稱
        rename_map = {
            "date": "date",
            "datetime": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        }
        df = df.rename(columns=rename_map)
        
        # === 異常資料過濾機制 (Anomaly Detection) ===
        # 針對 yfinance 容易產生的幽靈資料或極端錯誤值進行過濾，並留下 log
        filtered_rows = []
        prev_close = None
        
        # 排序確保時間順序正確
        if 'date' in df.columns:
            df = df.sort_values(by='date')
            
        for idx, row in df.iterrows():
            is_anomaly = False
            anomaly_reason = ""
            
            c = float(row['close']) if pd.notnull(row['close']) else None
            v = float(row['volume']) if pd.notnull(row['volume']) else 0
            
            if c is None:
                continue
                
            # 1. 幽靈資料特徵：無交易量且開高低收完全一致 (對大盤有效)
            # 但 yf 的國際指數有時本來就沒 volume，所以主要依賴振幅過濾
            
            # 2. 振幅過濾防呆：與前一根 K 棒收盤價對比 (台股漲跌極限為 10%，我們設 15% 為容錯閾值)
            if prev_close is not None and prev_close > 0:
                pct_change = abs((c - prev_close) / prev_close)
                
                # 如果是台灣標的或大盤指數，單根 K 線波動 > 15% 視為極端異常報價
                if pct_change > 0.15 and (stock_id.endswith('.TW') or stock_id == '^TWII' or stock_id.isdigit()):
                    is_anomaly = True
                    anomaly_reason = f"Extreme price swing > 15% (Prev: {prev_close:.2f}, Cur: {c:.2f})"
            
            if is_anomaly:
                logger.warning(f"🚨 [Anomaly Data Dropped] {stock_id} at {row['date']}: {anomaly_reason}")
                # 剔除該筆資料，不更新 prev_close
                continue
                
            prev_close = c
            filtered_rows.append(row)
            
        if filtered_rows:
            df = pd.DataFrame(filtered_rows)
        else:
            df = pd.DataFrame(columns=df.columns)
            
        df["stock_id"] = stock_id
        return df

    def fetch_realtime_quote(self, stock_id: str) -> Optional[dict]:
        # yfinance 獲取即時報價較慢，通常用於歷史資料
        ticker_id = f"{stock_id}.TW" if not stock_id.endswith((".TW", ".TWO")) else stock_id
        ticker = yf.Ticker(ticker_id)
        info = ticker.fast_info
        return {
            "stock_id": stock_id,
            "price": info.get("last_price"),
            "change": info.get("last_price") - info.get("previous_close") if "previous_close" in info else None
        }
