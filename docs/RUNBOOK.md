# PM/PjM 職缺觀測站維運手冊 (RUNBOOK)

本手冊供專案協作者或維護者日常維護與故障排除參考。

---

## 1. 手動補爬 (Manual Workflow Trigger)
若每日排程未執行或因網路短暫中斷失敗，可進行手動補爬：
1. 前往 GitHub Repo 頁面，點選頂部 **Actions** 頁籤。
2. 在左側列表選擇 **Daily 104 PM/PjM Pipeline & Deploy**。
3. 點選右側的 **Run workflow** 按鈕。
4. Branch 選擇 `main`，確認後點擊 **Run workflow**。
5. 執行完成後，自動會更新 `data` 分支並重新部署 GitHub Pages。

---

## 2. 更換 Gemini 金鑰與模型
### 更換金鑰
1. 若金鑰可能洩漏或失效，先至 [Google AI Studio](https://aistudio.google.com/) 撤銷舊 Key 並生成新 Key。
2. 進入 GitHub Repo -> **Settings** -> **Secrets and variables** -> **Actions**。
3. 找到 `GEMINI_API_KEY`，點選筆圖示編輯，貼上新金鑰並儲存。
4. 本機開發時，同步更新本機根目錄的 `.env` 檔案。

### 更換模型
1. 預設使用模型為 `gemini-2.5-flash`。
2. 若需更換為其他模型（例如新版 Flash），在 GitHub Actions 的 Workflow 環境變數中或 GitHub Repo Settings -> Secrets and variables -> Variables 新增 `GEMINI_MODEL`（例：`gemini-2.5-flash`）。

---

## 3. 審核 `unmatched_companies.json` 並補入子公司對照表
每天爬蟲執行時，若職稱命中 PM/PjM 規則但公司未在上市/上櫃/興櫃白名單中，會被記錄於 `data/unmatched_companies.json`。
1. 開啟 `data/unmatched_companies.json` 檢視未比對公司名稱。
2. 若確認為上市櫃公司之子公司（例如「緯穎科技」為緯創資通子公司 3231）：
   * 開啟 `data/subsidiaries.json`。
   * 新增一筆對應：`"公司全名": "母公司股票代號"`。
3. 提交 PR 或 commit 至 `data` 分支，隔天爬取時即可自動歸類。

---

## 4. 審核 `vocab_candidates.json` 與更新詞彙表
當 Gemini 萃取出的 KSA 或工作任務無法匹配到現有 `ksa_vocabulary.json` 或 `task_vocabulary.json` 時，會提出候選詞至 `data/vocab_candidates.json`。
1. 定期（每週或每月）開啟 `data/vocab_candidates.json`。
2. 評估候選詞是否有代表性與重複性：
   * 若具通用性，將其加入 `data/ksa_vocabulary.json` 或 `data/task_vocabulary.json`，指定標準 `id`、雙語名稱及對應的 `domain`（D1~D7）。
   * 將 `vocab_version` 升級（例如 `1.0` -> `1.1`）。
3. 清空 `vocab_candidates.json` 中已處理的項目。

---

## 5. 從 `backup/` 或 Git 歷史還原資料
* 系統每日在更動 `data.json` 前，會自動在 `backup/` 目錄建立 `data_backup_YYYYMMDD.json`（保留 30 天）。
* **還原方式**：
  1. 挑選目標日期的備份檔案，例如 `backup/data_backup_20261016.json`。
  2. 複製覆蓋回 `data/data.json`。
  3. commit 並 push 回 `data` 分支。

---

## 6. 失敗通知排查順序
當收到 GitHub Actions 失敗通知 Email 時，請依序排查：
1. **104 封鎖偵測 (HTTP 403 / 503 / Cloudflare)**:
   * 查看 Action Log 是否顯示 `Blocked by 104`。
   * 若 GitHub Actions IP 被阻擋，請切換為本機排程備案（Windows 工作排程器於台灣 IP 執行後 push 到 data 分支）。
2. **104 網頁改版**:
   * 查看 Log 是否顯示 `First page job count is 0` 或 `Missing essential fields > 20%`。
   * 此為熔斷機制生效，未破壞既有資料。需檢查 104 列表頁 API 結構是否有調整。
3. **Gemini API 額度或格式錯誤**:
   * 查看 Log 是否有 `429 Too Many Requests` 或 JSON schema 驗證失敗。
   * 檢查 RPM 間隔設定（`LLM_INTERVAL_SEC` 建議設為 7 秒）。
4. **程式邏輯或套件問題**:
   * 檢查 Python dependencies 是否正常安裝，執行 `python scripts/pipeline.py --test` 本機驗證。
