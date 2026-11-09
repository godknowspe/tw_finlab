# tw_finlab 新主機部署指南

私有資料不在本 repo（本 repo 是 public）：

| 資料 | 位置 | 新主機怎麼取得 |
|---|---|---|
| 交易帳本、自選股、現金、設定 `app_state.json` | 私有 repo `godknowspe/tw_finlab-data` | `git clone`，server 啟動時自動 pull、存檔後自動 commit + push |
| 行情快取 `data/tw_finlab.db` | 本機 | 不用搬；第一次開圖表時自動從 yfinance 重抓 |
| Gist token 等環境變數 | 本機 `.env`（git-ignored） | 手動建立，見下 |

## 步驟

```bash
# 1. 程式與私有資料（SSH key 需已加到 GitHub）
git clone git@github.com:godknowspe/tw_finlab.git ~/code/tw_finlab
git clone git@github.com:godknowspe/tw_finlab-data.git ~/code/tw_finlab-data

# 2. Python 環境（3.11 / 3.12 皆可；Alpine 不行，shioaji 需要 glibc）
cd ~/code/tw_finlab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. 前端
cd frontend && npm install && npm run build && cd ..

# 4. .env（chmod 600）
cat > .env <<EOF
TW_FINLAB_STATE_FILE=$HOME/code/tw_finlab-data/app_state.json
PORTFOLIO_EXPORT_METHODS=gist
PORTFOLIO_EXPORT_GIST_ID=<gist id>
PORTFOLIO_EXPORT_GITHUB_TOKEN=<token with gist scope>
TW_FINLAB_EXPORT=1        # 只在「負責匯出 Gist」的那一台設 1，其他台設 0
EOF
chmod 600 .env

# 5. 啟動（需要 lsof）
./server_start.sh && tail -f nohup_uvicorn.log
```

開 `http://127.0.0.1:8000`，右上角 Sync 應顯示 `git: ok · gist: ok`（或 `idle`，第一次存檔前）。

## 多台主機同時使用

兩台的 server 可以同時開著，不用輪流停。每台在每次存檔後、以及每 60 秒（`.env` 可設 `TW_FINLAB_SYNC_SECONDS`）
自動跟 `tw_finlab-data` 同步；另一台記的交易約一分鐘內出現，網頁約 30 秒內自動刷新。

- **兩台各記一筆交易**：自動合併。兩筆可能顯示相同的編號（#），這沒關係，系統內部以 uid 區分，刪除也是依 uid。
- **衝突**：兩台改了同一個東西（同一筆交易、同一個現金欄位），或合併後帳本算不平（例如兩台各賣掉同一批股票），
  就會停止同步，Sync 顯示 `conflict` 和原因。本機仍可繼續記錄（留在本機的 commit 裡），但**不會**匯出 Gist。
  處理方式：
  1. 兩台都停 server。
  2. 在其中一台 `cd tw_finlab-data && git fetch`，看 `git log --oneline HEAD...@{upstream}` 兩邊各多了哪些 commit。
  3. 修好本機 `app_state.json`（例如刪掉重複賣出的那筆），`git commit -am "Resolve conflict"`。**不要 force push**。
  4. 啟動這台 server：它會用修好的版本和遠端做合併、驗證後 push。Sync 顯示 `ok` 後再啟動另一台。

  步驟 3 只適用於「刪掉或改回某一邊」的情況（例如刪掉重複的賣出、或把欄位改成和遠端相同）。
  如果要保留**本機的值**或**兩邊都不是的新值**（例如現金兩台各改成 90 萬、80 萬，你要 85 萬），
  普通 commit 會在重啟後再次衝突。這時要做一個包含遠端的合併 commit：
  ```bash
  git merge --no-commit -s ours @{upstream}   # 記下遠端，但檔案保持本機內容
  # 編輯 app_state.json 成最終要的內容
  git commit -am "Resolve conflict"
  ```
  然後照步驟 4 啟動。不論哪種情況都**不要 force push**，也不要 `reset --hard`，以免丟掉另一台還沒同步的交易。
- **只有一台負責匯出 Gist**（`.env` 設 `TW_FINLAB_EXPORT=1` 的那台），而且只在它和遠端帳本一致時才匯出。
  另一台記的交易會先同步過來，再由它匯出。負責匯出的那台沒開時，Gist 會停在最後一次的內容，開機同步後自動補上。
- 離線時照常記錄，恢復連線後的下一輪自動推上去。

## 注意

- server 執行中不要手動編輯或 pull `tw_finlab-data`（存檔會回 409 拒絕）；同步交給 server。
  同一個 clone 上開第二個 server 會因 lock 拒絕啟動。
- 預設只綁 `127.0.0.1`（API 無認證）。要從其他裝置連，在 `.env` 加 `TW_FINLAB_HOST=0.0.0.0`，
  並確定只在可信網路上使用。
- 舊格式帳本（例如含 `sj_` 字串 id）server 會拒絕載入；先跑
  `PYTHONPATH=. .venv/bin/python -m src.tools.migrate_state <path>`（預設 dry run，`--write` 才寫入並備份）。
