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
EOF
chmod 600 .env

# 5. 啟動（需要 lsof）
./server_start.sh && tail -f nohup_uvicorn.log
```

開 `http://127.0.0.1:8000`，右上角 Sync 應顯示 `git: ok · gist: ok`（或 `idle`，第一次存檔前）。

## 注意

- **一次只讓一台主機寫入，server 執行中不要手動改或 pull `tw_finlab-data`**（存檔會回 409 拒絕）。換到另一台前，先停掉舊主機的 server，確認 `tw_finlab-data` 已 push。
  同一台上第二個 server 會因 lock 拒絕啟動。
- 啟動時 pull 失敗（分歧、網路），server 仍用本機資料開起來，但 Sync 顯示 `pull_failed`／`held`，
  **不會**把持股匯出到 Gist。到 `tw_finlab-data` 手動 `git pull --rebase` 解決後重啟。
- push 失敗會顯示 `push_failed`，commit 保留在本機，背景每 5 分鐘重試。
- 預設只綁 `127.0.0.1`（API 無認證）。要從其他裝置連，在 `.env` 加 `TW_FINLAB_HOST=0.0.0.0`，
  並確定只在可信網路上使用。
- 舊格式帳本（例如含 `sj_` 字串 id）server 會拒絕載入；先跑
  `PYTHONPATH=. .venv/bin/python -m src.tools.migrate_state <path>`（預設 dry run，`--write` 才寫入並備份）。
