# tw_finlab

個人用台股＋美股投資組合儀表板：手動（或永豐 Shioaji 同步）記錄交易，顯示持股、損益、K 線與技術指標，
做簡易策略回測，並把目前持股匯出給外部通知程式。

- 後端：FastAPI、SQLite（行情快取）、pandas、yfinance（預設行情來源，可選 FinMind / Shioaji）
- 前端：Vue 3 + Vite + Pinia + Tailwind + lightweight-charts（`frontend/`）
- 帳本：`app_state.json`，放在另一個私有 repo；多台主機可同時開著，server 自動以 git 同步並合併；本 repo 不含任何個人資料

## 功能

- **Watchlist / Positions / Trades**：即時報價（WebSocket）、均價成本、已實現／未實現損益（含手續費、交易稅）
- **Symbol**：日／週／月及 15m／30m／60m K 線，SMA、布林、MACD、RSI，疊加個股持倉損益與買賣點
- **Equity**：以實際投入資金計算的台股／美股／合計報酬率走勢
- **Analysis**：逐筆（FIFO lot）MAE / MFE / 出場效率
- **Backtest**：RSI、SMA 交叉、MACD、布林；訊號次一根開盤成交，台股費稅與整張、美股零手續費

## 執行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
./server_start.sh          # http://127.0.0.1:8000
PYTHONPATH=. .venv/bin/pytest tests/
```

設定（`.env`）、私有資料 repo 與新主機部署見 [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)；
架構說明見 [`CLAUDE.md`](CLAUDE.md)。
