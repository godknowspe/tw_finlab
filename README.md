# tw_finlab 台灣股市回測系統專案規劃書

## 1. 背景與目標 (Background & Motivation)
建立一套針對台灣股票市場設計的回測與量化分析系統。此系統整合開源的 `FinMind` (用作台股數據源) 以及 `Backtrader` (用作強大的回測引擎)，並使用 `SQLAlchemy` 及 `pandas` 處理與儲存歷史資料。
最終目標是提供一個可擴充的模組化框架，方便開發者建立、驗證以及優化台股交易策略。

## 2. 專案範圍 (Scope)
- **資料獲取 (Data Acquisition)**: 透過 FinMind API 自動抓取台股日線資料（K線資料）、三大法人買賣超等公開市場資訊。
- **資料儲存 (Data Storage)**: 建立本地關聯式資料庫 (SQLite / PostgreSQL)，透過 SQLAlchemy ORM 模型管理歷史資料，減少重複 API 請求。
- **資料處理 (Data Processing)**: 利用 pandas 清洗與轉換資料格式，以符合 Backtrader 所需的 DataFeed 標準。
- **回測引擎 (Backtesting Engine)**: 基於 Backtrader，設定初始資金、手續費、滑價等台股專屬環境參數。
- **策略模組 (Strategy Modules)**: 實作並測試基礎策略（如均線交叉策略）。
- **結果報表 (Reporting)**: 輸出回測績效指標（如夏普值、最大回撤等），並視覺化交易圖表。

## 3. 系統架構與模組設計 (Architecture)
專案結構已初步建立，各資料夾權責劃分如下：

```text
tw_finlab/
├── data/           # 存放本地 SQLite 資料庫或快取資料 (CSV等)
├── src/
│   ├── api/        # 負責與外部服務 (FinMind) 介接的 API 封裝
│   ├── broker/     # 回測引擎的經紀商設定 (手續費、證交稅、滑價等台股設定)
│   ├── data/       # 資料庫模型 (SQLAlchemy Models)、資料處理與轉接器 (Pandas -> Backtrader)
│   ├── engine/     # 封裝 Backtrader 執行邏輯、策略基礎類別 (BaseStrategy)
│   └── ui/         # 圖表繪製與績效報表產生
├── tests/          # 單元測試與整合測試
├── requirements.txt # 相依套件 (FinMind, backtrader, pandas, sqlalchemy 等)
└── README.md       # 專案說明文件
```

## 4. 實作計畫 (Implementation Plan)

### 第一階段：基礎建設與資料串接 (Foundation & Data)
1. **資料庫設定**: 使用 SQLAlchemy 定義 `DailyPrice` (日線資料) 表格結構。
2. **FinMind 整合**: 在 `src/api/` 中實作下載台股特定區間資料的爬蟲腳本。
3. **資料庫更新機制**: 撰寫腳本，將下載的資料存入資料庫，並支援增量更新。

### 第二階段：回測引擎整合 (Engine Integration)
1. **Backtrader 轉接器**: 在 `src/data/` 實作自訂的 Backtrader DataFeed，從資料庫讀取資料供引擎使用。
2. **台股經紀商設定**: 在 `src/broker/` 實作手續費 (0.1425% 帶折扣) 與證券交易稅 (0.3%) 的設定。
3. **引擎封裝**: 在 `src/engine/` 建立執行回測的主程式框架 (`BacktestRunner`)。

### 第三階段：策略開發與驗證 (Strategy & Validation)
1. 建立第一個測試策略（例如 SMA 均線交叉）。
2. 執行回測，並在 `src/ui/` 實作印出交易明細與最終績效。
3. 產生 Backtrader 內建的圖表。

## 5. 驗證與測試 (Verification)
- 針對 `src/api/` 的資料抓取邏輯撰寫 pytest 測試。
- 針對 `src/data/` 的資料轉換邏輯撰寫測試，確保餵給 Backtrader 的 K線資料無誤。
- 進行一次完整的端到端 (End-to-End) 測試：抓取 2330 (台積電) 過去一年的資料，執行均線策略，並驗證結果是否合理。
