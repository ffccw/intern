# 產品需求文件（PRD）— 104 上市櫃 PM／PjM 新人職缺觀測站
專案名稱：104 上市櫃 PM/PjM 新人職缺追蹤與雙語 KSA 自動分析系統 (PWA)

> **關於這份文件**
> 這是一份 MVP（最小可行產品）產品需求文件的**實作範例**，記錄一個真實專案從初稿到第二版的規格與設計取捨，**僅供參考，不是標準答案**。
> 文件中的許多決定（例如每日 80 筆上限、連續 3 天未出現才判定下架、配適度權重、使用 Gemini 免費版）都是依這個專案的條件所做的選擇，換成別的專案可能有不同的答案。閱讀時可以多留意每個決定背後的「原因」，再依自己的需求調整。
> 文件由作者與 AI 協作討論完成。

> 版本：v2（2026-10-16）
> 相較初稿的主要變更：補齊前端規格、改用職務類別查詢（配合 104 robots.txt）、排除 PE、年資納入 1-3 年、納入興櫃與子公司、API 上限改為分批處理、下架判定加緩衝、新增 `ksa_normalized` 與欄位擴充、模型參數化、中英雙語規則、JD 語意分析（PM 七大構面、Stage-Gate 階段、工作職責、職務情境、AI 摘要）、我的配適度（勾選自評版）、AI 資安與倫理（第 8 節）、視覺與技術設計原則（5.6）、維運與部署（第 11 節）、匯出功能（5.7）、本機安全（11.5）。

---

## 1. 專案目標與定位
本系統每天定時自動抓取 104 人力銀行上，**上市、上櫃、興櫃公司（含其子公司）**的 PM／PjM 新人職缺，用 Google Gemini API 萃取雙語職能需求（KSA）並分析工作內容（JD），再以極簡靜態架構（GitHub Pages + PWA）呈現，提供求職者免安裝、免登入的最新與歷史職缺分析工具。

* **用途：** 教學與非商業用途。上線前應以 104 robots.txt 所列表單（https://forms.cloud.microsoft/r/Zim6WH7i7U）申請爬取許可。
* **介面語言：** 中英雙語（可切換）。

---

## 2. 業務邏輯與資料管線 (Pipeline)

### 2.1 資料過濾與抓取

1. **公司白名單：**
   * 每次執行時讀取 TWSE（上市）、TPEx（上櫃、興櫃）公開資料的最新公司名單，記錄股票代號與上市別（上市／上櫃／興櫃）。
   * **名稱比對：** 去除「股份有限公司」「有限公司」「(股)」、全半形、空白及英文大小寫差異後比對，並保留簡稱對照。
   * **子公司：** 另外維護 `subsidiaries.json`（子公司名稱 → 母公司股票代號）。系統每天將「職稱符合但公司未比對成功」的名單輸出到 `unmatched_companies.json`，供人工確認後補入對照表。104 公司名稱中若有「(XX子公司)」字樣，也一併作為比對線索。

2. **查詢方式（配合 104 robots.txt）：**
   * 104 的 robots.txt 對所有爬蟲禁止 `keyword=` 與 `kwop=` 參數，因此**不使用關鍵字搜尋**，改用 **104 職務類別代碼（jobcat）** 查詢，例如產品企劃、專案管理相關類別（實際代碼於開發時確認並寫入設定檔）。
   * 取回結果後，在本機做職稱過濾。

3. **職稱過濾：**
   * **正向詞組 A（任一）：** PM、PjM、產品、專案、Project、Product
   * **正向詞組 B（任一）：** 經理、專員、工程師、助理、管理師、Manager、Engineer、Specialist、Assistant
   * 職稱須**同時**命中 A 與 B；另外，職稱以獨立英文字出現 `PM`、`PjM` 時可直接視為命中。
   * **英文比對**不分大小寫，並以單字邊界判斷（避免 `PMC`、`APM` 誤判）。
   * **排除詞（任一命中即排除）：** 產品工程師、Product Engineer、PE、PMC、生管、製程工程師、實習、實習生、工讀、工讀生、Intern、Internship。
   * **第二道判定：** Gemini 萃取 KSA 時同時回傳 `role_type`（`PM` / `PjM` / `Other`）。判定為 `Other` 的職缺不在前端預設列表中顯示，但保留紀錄以便檢查誤判。

4. **年資限制：** 納入 104 經驗條件為「經驗不拘」「1 年以下」「1-3 年」的職缺。

5. **執行時間：** 台灣時間每日凌晨 **03:05**，GitHub Actions cron 寫為 `5 19 * * *`（UTC）。GitHub 排程可能延遲 10～60 分鐘，仍可在 07:00 前更新上線。

6. **頻率控制：**
   * 列表頁每頁之間 `sleep(3~5)` 秒。
   * **僅新職缺**才進入個別職缺頁取得 JD，每頁之間同樣 `sleep(3~5)` 秒。
   * 既有職缺只用列表結果更新 `last_seen_date`，不重複進入職缺頁。

### 2.2 增量更新、雙語 KSA 萃取與 JD 語意分析

1. **增量比對：** 讀取現有 `data.json`。職缺 ID 已存在且 `ai_status: "done"` 時，只更新狀態欄位，嚴禁重複呼叫 AI API。
2. **雙語 KSA 萃取：**
   * 新職缺的 JD 送交 Gemini。模型名稱由環境變數 `GEMINI_MODEL` 設定，預設值為 `gemini-2.5-flash`，換模型不需改程式。
   * 原始 JD 不論是全中文、全英文或中英夾雜，都整篇送出。K、S、A 的每個標籤**一律輸出中英兩個欄位** `{ "zh": "...", "en": "..." }`，不存成「中文 (English)」單一字串。
   * Gemini 同時回傳 `jd_lang`（`zh` / `en` / `mixed`），標記原文語言。
   * Gemini 同時回傳職稱翻譯 `title_zh`、`title_en`（原文為中文者，`title_zh` 即原文，反之亦然）。
   * 使用 Gemini **structured output（responseSchema）** 強制回傳 JSON，不靠 prompt 要求格式。
3. **標準化標籤 `ksa_normalized`：**
   * 維護一份標準詞彙表 `ksa_vocabulary.json`（每個標籤含 `id`、`zh`、`en`、`category`：K/S/A）。
   * Gemini 同時回傳 `ksa`（原始雙語標籤）與 `ksa_normalized`（對應到詞彙表的 `id` 陣列）。
   * 無法對應時，Gemini 提出候選新詞，寫入 `vocab_candidates.json` 供人工審核後併入詞彙表。
   * 前端的統計圖表一律以 `ksa_normalized` 計算。
   * **學歷與科系要求（歸入 K 知識）：** 以 104 職缺的結構化欄位「學歷要求」「科系要求」為主要來源，Gemini 再從 JD 內文補充（例：「理工背景尤佳」）。結果存於 `education_req`：
     * `level`：最低學歷（`none` 不拘 / `hs` 高中職 / `as` 專科 / `ba` 大學 / `ma` 碩士 / `phd` 博士）。
     * `majors`：科系要求，對應到標準科系群組詞彙表 `major_vocabulary.json` 的 id（例：`MAJ_BUS` 商業及管理、`MAJ_CS` 資訊、`MAJ_EE` 電機電子、`MAJ_IE` 工業工程、`MAJ_ME` 機械、`MAJ_CHEM` 化學化工、`MAJ_MAT` 材料、`MAJ_BIO` 生醫、`MAJ_DESIGN` 設計、`MAJ_COMM` 傳播、`MAJ_LANG` 外語、`MAJ_ECON` 經濟、`MAJ_SCI_ENG` 理工不限）；空陣列代表科系不拘。
     * `major_required`：`true` 為必要條件，`false` 為「尤佳」等加分條件。
     * `source`：`104`（結構化欄位）或 `jd`（由 Gemini 從內文判讀）。
4. **JD 語意分析（與 KSA 在同一次 Gemini 呼叫中完成，不增加呼叫次數）：**
   * **AI 摘要 `jd_summary`：** Gemini 以自己的文字撰寫 2～3 句中英摘要 `{ "zh": "...", "en": "..." }`，中文上限 100 字、英文上限 60 words，不得直接摘錄原文句子。
   * **工作職責 `tasks_normalized`：** 對應到標準詞彙表 `task_vocabulary.json` 的 id 陣列（例：需求訪談、規格制定、時程管理、供應商管理、跨部門協調、上市規劃、客訴處理）。無法對應時同樣寫入 `vocab_candidates.json`。
   * **PM 七大構面 `pm_domains`：** 依作者課程「PM 產品經理」心智圖的架構，給出該職缺在七個構面的比重（合計 100）：
     | id | 構面 | English |
     |---|---|---|
     | `D1` | 策略 | Strategy |
     | `D2` | 產品線組合管理 | Portfolio Management |
     | `D3` | 產品創新流程 | PI Process |
     | `D4` | 產品設計開發工具 | PDD Tools |
     | `D5` | 市場研究 | Market Research in PI |
     | `D6` | 文化、團隊與領導 | Culture, Teams, and Leadership |
     | `D7` | 產品創新管理 | PI Management |
   * **Stage-Gate 階段 `stage_gate`：** 依作者課程「NPD Stage-Gate Model」心智圖的架構，列出該職務參與的階段（可複選）：
     | id | 階段 | English |
     |---|---|---|
     | `S1` | 行銷：規劃與提案 | Marketing – Plan & Proposal |
     | `S2` | 可行性：規格 | Feasibility – Specification |
     | `S3` | 產品設計：原型驗證 | Product Design – Prototype Verification |
     | `S4` | 模具：驗證與工程樣品 | Tooling – Validation & Engineering Sample |
     | `S5` | 工程：試產與可靠度 | Engineering – Pilot-Run & Reliability |
     | `S6` | 產品上市：量產、品保與客服 | Product Launch – Mass Production, QA & CS |
     | `EOL` | 產品終止／換代 | End of Life |
   * **職務情境 `context`：**
     * `collaborators`：主要協作單位（可複選，代碼取自 Stage-Gate 心智圖：GM、MKT、SA、RD、DQA、TE、QA、PE、PUR、PC、MC、MFG、QC、FAE、CS）。
     * `product_type`：`hardware` / `software` / `service` / `mixed`。
     * `market`：`B2B` / `B2C` / `both`。
     * `travel`：是否需出差或外派（`none` / `occasional` / `frequent` / `overseas`）。
     * `english_level`：英文使用程度（`none` / `reading` / `daily` / `primary`）。
   * JD 中沒有提到的項目一律回傳 `null`，不得推測。
   * **歧視性條件 `compliance_flags`：** JD 若出現與工作能力無關、可能違反《就業服務法》第 5 條的條件，**不得列入 KSA 標籤**，改以代碼記錄於 `compliance_flags`（例：`GENDER` 性別、`AGE` 年齡、`APPEARANCE` 容貌、`MILITARY_SERVICE` 役畢（隱含性別限制）、`MARITAL` 婚姻、`ORIGIN` 籍貫或出生地、`OTHER`）。詳見第 8 節。
   * **依據片段檢查：** Gemini 為每個 KSA 與工作職責標籤附上 JD 原文中的依據片段。程式確認該片段確實出現在原文中後即刪除片段（不存檔）；找不到依據的標籤直接捨棄。
6. **初版詞彙表建立流程：**
   1. 讓 Gemini 以開放方式分析前 50 筆職缺，不限定詞彙。
   2. 開發者將結果歸類、去重，整理成 `ksa_vocabulary.json`、`task_vocabulary.json` 草稿（含 `domain` 對應）。
   3. 由專案負責人審核定稿為 `vocab_version: "1.0"`，再正式啟用每日排程。
   4. 之後的候選新詞（`vocab_candidates.json`）定期審核，併入後提升版本號。
7. **版本追蹤：** 每筆職缺記錄 `ai_model`、`prompt_version`、`vocab_version`。詞彙表或 prompt 大幅修改時，可依版本號挑出需要重新分析的職缺（重新分析同樣受每日 80 筆上限限制，且優先順序低於新職缺）。
5. **著作權合規（不存原文）：** JSON 檔中**嚴格禁止儲存原始工作內容全文**（包含 104 列表 API 回傳的 `description` 摘要），只保留結構化標籤、AI 自行撰寫的摘要、公司基本欄位與 104 原始連結。

### 2.3 每日 API 上限與分批處理

1. 單次排程最多送出 **80 筆**新職缺給 Gemini（環境變數 `MAX_LLM_PER_RUN`，預設 80）。
2. 超過上限時**不中斷整批**，處理方式如下：
   * 前 80 筆完成萃取並存檔（`ai_status: "done"`）。
   * 其餘職缺照樣寫入 `data.json`，但標示為 `ai_status: "pending"`，只有基本欄位、沒有 KSA。
   * 隔天優先處理 `pending` 職缺，依 `first_seen_date` 由舊到新。
   * 在 workflow 輸出警告（warning annotation），但不讓 workflow 失敗。
3. **前端顯示：** `pending` 職缺照常出現在列表，KSA 區塊顯示「分析中 / Analyzing」，不列入統計圖表。
4. **冷啟動：** 第一次執行時預期會有數百筆，依上述機制約數天內消化完畢，期間網站可正常使用。
5. **Gemini 免費額度節流：** 每次呼叫之間依該模型的每分鐘請求上限（RPM）間隔，預設 7 秒（`LLM_INTERVAL_SEC`）。
6. **分析失敗處理：** 單筆職缺經重試後仍無法取得合格結果（格式不符、驗證失敗）時，標為 `ai_status: "failed"` 並記錄 `ai_fail_count`，隔天重試；連續 3 天失敗改標為 `"error"`，不再自動重試，列入 workflow 摘要供人工檢查。前端對 `failed`、`error` 的顯示與 `pending` 相同。

### 2.4 下架判定與一個月自動歸檔

1. **只有完整成功的爬取才會更新下架狀態。** 任一列表頁失敗（重試後仍失敗）時，當天不變更任何職缺的狀態。
2. 完整爬取後未出現的 `open` 職缺，`miss_count + 1`。**連續 3 天**未出現才改為 `status: "closed"`，並記錄 `closed_date`。
3. 職缺重新出現時，`miss_count` 歸零；若原本已 `closed`，改回 `open`，並清除 `closed_date`。
4. `closed` 狀態**超過 30 天**的職缺，從 `data.json` 移到 `history_archive.json`。
5. `history_archive.json` 依年份分檔（`history_archive_2026.json`…），避免單一檔案無限增長。前端僅在使用者開啟「歷史職缺」時才載入。

---

## 3. 異常處理與資安熔斷機制

1. **網頁改版防空跑警報：** 列表第一頁取得的職缺數為 0 時，立刻中斷並 `sys.exit(1)`，讓 GitHub Actions 失敗並寄送 Email 通知。
2. **欄位結構檢查：** 抽查當次取得的職缺，若 `job_id`、`company`、`title` 任一欄位缺漏比例 **> 20%**，視為 104 改版，同樣 `sys.exit(1)`，且不寫入任何資料。
3. **封鎖偵測：** 收到 HTTP 403／503 或 Cloudflare 驗證頁時，視為被封鎖：記錄錯誤並 `sys.exit(1)`。
4. **網路容錯重試：** 網路請求與 API 呼叫遇到暫時性錯誤時，採指數退避重試（最多 3 次，間隔 2s、4s、8s）。
5. **金鑰資安：** `GEMINI_API_KEY` 嚴禁寫死在程式碼中，必須由 **GitHub Secrets** 注入環境變數。在 Google Cloud 將此金鑰限定只能呼叫 Generative Language API。AI 相關的其他資安措施見第 8 節。
6. **手動補爬：** workflow 開啟 `workflow_dispatch`，可從 GitHub 網頁手動執行。
7. **權限：** workflow 只開必要權限（見 11.3 第 5 點）。

---

## 4. 自動備份機制 (Backup Strategy)
* **每日備份：** 每次寫入 `data.json`、`history_archive_*.json` 之前，先將前一版複製到 `backup/`，命名為 `data_backup_YYYYMMDD.json`、`archive_backup_YYYYMMDD.json`。
* **保留期限：** `backup/` 只保留最近 30 天，超過的由腳本自動刪除。
* **說明：** 備份檔內容和前一天 commit 的檔案完全相同，git 會共用同一份儲存，因此幾乎不增加 repo 容量。這份備份的好處是不懂 git 的人也能直接下載舊版；更早的版本可從 git 歷史還原。

---

## 5. 前端 PWA 規格

### 5.1 共通
* 靜態網站，部署於 GitHub Pages，資料來源為 repo 中的 JSON 檔。
* **PWA：** 可安裝到手機桌面；離線時顯示最後一次快取的資料，並標示資料日期。
* **中英雙語：** 介面文字可一鍵切換（預設依瀏覽器語言），切換結果記在 localStorage。亮／暗主題同樣預設依系統設定（見 5.6）。各類內容的雙語來源如下：

  | 內容 | 雙語來源 |
  |---|---|
  | 介面文字 | 前端中英對照表 `i18n.json` |
  | KSA 標籤 | Gemini 輸出的 `zh` / `en` 欄位；標準化標籤取自 `ksa_vocabulary.json` |
  | 職稱 | 顯示原文，另附 Gemini 翻譯（`title_zh` / `title_en`） |
  | 公司名稱 | TWSE／TPEx 資料中的公司英文簡稱，不使用 AI 翻譯 |
  | 產業、地區、學歷 | 104 固定選項，以對照表 `mappings.json` 轉換 |
  | 薪資 | 規則轉換（例：「月薪 40,000 元以上」→「Monthly NT$40,000+」；「待遇面議」→「Negotiable」） |

  原則：**固定選項用對照表，自由文字才交給 Gemini**。
* **顯示方式：** 中文模式下 KSA 顯示為「需求管理 (Requirement Management)」，英文模式只顯示英文。
* **雙語搜尋：** 搜尋時同時比對中英欄位，不論目前介面語言。
* RWD：手機（寬度 375px）到桌機都能正常使用。
* 頁首顯示「資料更新時間」與「目前開放職缺數」。
* 頁尾顯示非官方聲明與資料來源；AI 產生內容的標示與錯誤回報方式見 8.5。
* 不安裝流量統計或追蹤工具，不使用 cookie（見 8.3）。

### 5.2 職缺列表
* 卡片或表格呈現：職稱、公司（標示上市／上櫃／興櫃、子公司則註明母公司）、產業、地區、學歷、薪資、首次出現日期、狀態，並附 104 原始連結。
* **篩選：** 職務類型（PM／PjM）、產業、上市別、地區、狀態（開放／已關閉）、首次出現日期範圍。
* **搜尋：** 公司名稱、職稱、KSA 標籤（中英文皆可）。
* **排序：** 最新出現（預設）、公司名稱。
* 展開卡片可看該職缺的 AI 摘要、K（含學歷與科系要求，置於 K 區塊最前面，並標示「必要」或「尤佳」）、S、A 標籤、工作職責、七大構面小雷達圖、Stage-Gate 參與階段、職務情境；有 `compliance_flags` 者以中性文字標示（見 8.4）；`pending`、`failed`、`error` 職缺顯示「分析中 / Analyzing」。

### 5.3 統計儀表板
所有圖表皆可依職務類型（PM／PjM）、產業、時間範圍（近 30 天／近 90 天／全部）篩選；點選圖上的任一標籤或區塊，跳回職缺列表並以該條件篩選。

1. **KSA Top 20：** 以 `ksa_normalized` 計算，K、S、A 三組各顯示出現次數 Top 20。選定一個標籤後，顯示其每月出現比例的變化。
2. **工作職責 Top 20：** 以 `tasks_normalized` 計算，呈現「新人 PM／PjM 最常做的事」。
3. **PM 七大構面雷達圖：** 顯示所選職缺 `pm_domains` 的平均比重；PM 與 PjM 可並列兩條線比較。不疊加課程比重。
4. **Stage-Gate 熱度圖：** 橫軸為 S1～S6、EOL，縱軸為 PM／PjM（或產業），顏色深淺代表參與該階段的職缺比例。
5. **協作單位長條圖：** 以 `context.collaborators` 計算，呈現「進公司後主要跟誰共事」。
6. **職務情境分布：** 產品類型、B2B／B2C、出差程度、英文使用程度的比例圖；另顯示 `jd_lang` 的中／英／夾雜比例。
7. **學歷與科系要求：** 最低學歷分布（不拘／專科／大學／碩士…）的比例圖，以及最常被要求的科系群組 Top 10（標示其中「必要」與「尤佳」的比例），另顯示「科系不拘」的比例。
8. **職缺合規觀察：** 以 `compliance_flags` 計算，呈現含各類歧視性條件（性別、年齡、容貌、役畢等）的職缺比例，並可依產業比較。只呈現統計比例，不列出公司排行（見 8.4）。

### 5.4 歷史職缺
* 獨立分頁，選擇年份後才載入對應的 `history_archive_YYYY.json`。
* 提供與職缺列表相同的篩選與搜尋功能，也可納入 KSA 統計（勾選「含歷史資料」）。

### 5.5 我的配適度（勾選自評版）
不上傳履歷、不呼叫 AI；使用者自行勾選具備的能力，由瀏覽器即時計算與每個職缺的配適度。

1. **自評勾選：**
   * 從 `ksa_vocabulary.json`（K、S、A）與 `task_vocabulary.json`（做過的工作職責）中勾選自己具備的項目。
   * 依類別分組，可搜尋（中英皆可）；每組依「目前職缺中出現次數」排序，常見項目排前面。
   * 每個項目分兩級：「熟悉」（權重 1）、「略懂」（權重 0.5），未勾選為 0。
   * **學歷與科系：** 在知識（K）組的最前面，選擇自己的最高學歷（單選）與就讀科系群組（可複選；雙主修、輔系可一併勾選），不分熟悉／略懂。
2. **隱私：** 勾選結果只存在使用者瀏覽器的 localStorage，不傳送到任何伺服器。提供「匯出 / 匯入」JSON 檔，方便換裝置；提供「清除我的資料」按鈕。
3. **配適度計算（每個 `ai_status: "done"` 的職缺）：**
   * 各類別覆蓋率 = 使用者在該職缺要求項目上的權重總和 ÷ 該職缺要求項目數。
   * 總分 = Skills 35% + Knowledge 25% + Tasks 25% + Attributes 15%。職缺某類別無要求時，該類別不計，其餘權重等比例放大。
   * 結果以 0～100% 顯示，分為「高度符合 ≥70%」「部分符合 40～69%」「差距較大 <40%」三級。
   * **學歷與科系併入 K 計算：** 職缺有學歷要求（`level` 不為 `none`）時，K 多一個項目，使用者學歷達到或超過要求計 1，未達計 0。職缺有科系要求（`majors` 非空）時，K 再多一個項目，使用者任一科系符合計 1；不符合時，`major_required: true` 計 0，`false`（尤佳）計 0.5。學歷不拘、科系不拘的職缺不增加項目。
   * `compliance_flags` 不列入計算，也不出現在自評勾選清單與缺口分析中。
4. **呈現：**
   * 職缺列表新增「依配適度排序」，卡片上顯示配適度與分級顏色。
   * 展開卡片時列出「已具備」與「尚缺」的項目。
   * **缺口分析：** 在目前篩選條件下的所有職缺中，統計使用者「未勾選但最常被要求」的項目 Top 10，作為補強方向。學歷與科系不列入缺口分析（短期內無法補強），但展開職缺卡片時仍會在「尚缺」中列出。
   * **我的構面輪廓：** 依使用者勾選項目在七大構面的分布畫出雷達圖，可與所選職缺的平均構面比重並列比較。
5. **聲明：** 頁面註明「配適度僅依自評與職缺標籤計算，供參考，不代表錄取機會」。
6. **未來規劃（不在本版範圍）：** 上傳履歷由 AI 自動判讀勾選（使用者自備 Gemini 金鑰，在瀏覽器端處理）。

> 為支援第 4 點的構面輪廓，`ksa_vocabulary.json` 與 `task_vocabulary.json` 的每個項目須另標 `domain`（`D1`～`D7`，可為 `null`）。

### 5.6 視覺與技術設計原則
**沿用**專案負責人既有的個人網頁設計系統，維持系列作品一致的風格（以下為重點；讀者可換成自己的風格）：
* **色彩：** 主色深綠 `#004030`、輔色暖金 `#D8C3A5`；亮色背景 `#f4f4f4`、暗色背景 `#121212`；卡片亮色白底、暗色 slate-800。
* **字型：** 標題 Merriweather（serif，粗體），內文與介面 Inter（sans）。
* **版面：** 固定式頁首（高 64px，含漢堡目錄、首頁鍵、品牌標題、語言切換、亮暗切換）；頁尾（高 32px，深綠底，含版本日期、「For Educational Use Only」、作者署名與連結、回到頂端）。
* **亮／暗主題切換**、切換分頁時的淡入動畫、RWD 規範（不用固定像素寬度）。
* **雙語字典：** 中英兩份 key 完全對稱；中文一律使用台灣繁體用語。
* **防護：** 保留網域白名單與防止被其他網站以 iframe 嵌入。

**調整**（本系統是資料查詢工具，與學習教材的需求不同）：

| 項目 | 學習 SPA 作法 | 本系統作法 | 原因 |
|---|---|---|---|
| 技術架構 | 瀏覽器端即時編譯（Babel standalone、Tailwind Play CDN） | 以 Vite 預先建置 React + Tailwind，由 GitHub Actions 建置後部署 | 手機載入較快；CSP 不需開放 `unsafe-eval`（見 8.2） |
| 函式庫來源 | CDN | 打包進網站本身 | PWA 離線時仍可運作；不受 CDN 異動影響 |
| 檔案結構 | 單一 HTML | 多檔（頁面、JSON 資料、manifest、service worker） | PWA 與每日資料更新的需要 |
| 預設語言／主題 | 英文、深色 | 依瀏覽器語言與系統主題，使用者切換後記住 | 主要使用者為台灣求職者 |
| 右鍵、F12 攔截 | 有 | 不採用 | 資料與原始碼皆公開；使用者需要複製公司名稱與連結 |
| 語音導覽、翻轉卡、測驗、答案混淆 | 有 | 不採用 | 非教材用途 |
| 學習歷程 CSV（含學號、姓名） | 有 | 不採用 | 不蒐集個資（見 8.3）；配適度資料僅存本機且可匯出（見 5.5） |
| HTML 淨化（DOMPurify） | 有 | 不需要 | 本系統一律以純文字顯示，不插入 HTML（見 8.2） |

**頁面結構**（沿用模組式導覽，漢堡目錄每項附圖示與編號）：
| 編號 | 頁面 | 內容 |
|---|---|---|
| 0 | 總覽 Overview | 統計卡（開放職缺數、本週新增、PM／PjM 比例、資料更新時間）＋本週新職缺 |
| 1 | 職缺列表 Jobs | 見 5.2 |
| 2 | 統計儀表板 Insights | 見 5.3 |
| 3 | 我的配適度 My Fit | 見 5.5 |
| 4 | 歷史職缺 Archive | 見 5.4 |
| 5 | 關於與方法 About | 資料來源、AI 分析方式與限制、七大構面與 Stage-Gate 說明、非官方聲明、錯誤回報 |

**圖表配色：** 深綠與暖金只有兩色，不足以區分 K／S／A、PM／PjM、七大構面等類別。以這兩色為基調延伸一組類別色盤，亮暗主題分別調校，並檢查色覺障礙者可辨識。圖表函式庫於開發時選定並打包。

> 詳細版面（各頁示意稿）另行討論後補入。

### 5.7 匯出功能
所有匯出檔都在使用者的瀏覽器中產生，不經過伺服器。

| 匯出對象 | 位置 | 格式 | 內容 |
|---|---|---|---|
| 職缺總表 | 職缺列表頁上方 | CSV | 依目前篩選條件與排序，每列一筆職缺（欄位見下方） |
| 單一職缺 | 展開的職缺卡片 | PDF | 該職缺的完整分析卡片，一頁一筆 |
| 單張圖表 | 每張圖表右上角 | PNG、CSV | 圖表圖片；圖表背後的統計數字 |
| 整頁儀表板 | 統計儀表板頁上方 | PDF | 目前篩選條件下的所有圖表 |
| 我的配適度報告 | 我的配適度頁 | PDF、JSON | PDF：配適度排名、缺口分析、構面雷達圖；JSON：自評資料備份與還原（見 5.5） |

1. **CSV 欄位：** 職缺編號、公司、公司英文名、上市別、母公司、職稱（原文、中、英）、職務類型、產業、地區、學歷要求、科系要求（含必要／尤佳）、薪資、首次出現日、狀態、關閉日、K、S、A、工作職責（標準化標籤，依介面語言輸出，多值以「; 」分隔）、七大構面比重（D1～D7 各一欄）、Stage-Gate 階段、AI 摘要、104 連結；使用者有自評資料時，加上「配適度」欄。
2. **CSV 編碼：** UTF-8 加 BOM，確保 Excel 直接開啟時中文不亂碼。
3. **PDF：** 使用瀏覽器內建的「列印 → 另存為 PDF」，搭配列印專用版面（隱藏頁首、選單、按鈕，保留圖表與頁尾聲明），不引入 PDF 函式庫。
4. **PNG：** 圖表一律以 SVG 繪製，匯出時轉為 PNG（2 倍解析度，背景依目前主題填色）。
5. **來源標示：** 每個匯出檔都附資料來源、整理日期與 AI 聲明（CSV 放在檔案末列；PDF、PNG 放在頁尾或圖片底部），例如「資料來源：104 人力銀行、TWSE／TPEx；本站整理於 2026-10-16；AI 分析可能有誤，以 104 原始職缺為準」。
6. **檔名：** `PMJ_<內容>_<YYYYMMDD>.<副檔名>`，例：`PMJ_職缺總表_20261016.csv`、`PMJ_KSA_Top20_20261016.png`。
7. **不匯出的內容：**
   * 單筆職缺層級的 `compliance_flags`（避免被用於點名或排行個別公司，見 8.4）；「職缺合規觀察」圖表的彙總統計仍可匯出。
   * JD 原文（見 2.2 第 5 點）。
8. **安全：** CSV 中以 `=`、`+`、`-`、`@` 開頭的儲存格前加上單引號，防止 Excel 公式注入（CSV injection）。

---

## 6. 測試與驗證 (Testing & Verification)
腳本提供以下測試參數，可在本機與 CI 執行；`--test` 依序執行測項 1～3，測項 4～6 為前端測試。測試模式一律在暫存資料夾中建立假資料，**不得讀寫正式的 `data.json`、歷史檔與備份**；`--test-crawl` 只抓前 5 筆，避免在本機對 104 大量請求。

* **測項 1：爬蟲與職稱過濾（`--test-crawl`）**
  * 能成功讀取 TWSE／TPEx 名單，並取得 104 前 5 筆職缺。
  * 職稱過濾單元測試：「專案工程師」「Product Specialist」「產品經理」「Product Manager」「PM」須命中；「產品工程師」「Product Engineer」「PMC 生管專員」「專案經理PM實習生」「Product Manager Intern」須排除。
* **測項 2：Gemini 雙語格式（`--test-llm`）**
  * 分別餵入全中文、全英文、中英夾雜三段假 JD，驗證回傳的 JSON 符合 schema；每個 K、S、A 標籤的 `zh`、`en` 欄位都不為空且語言正確；`jd_lang` 判定正確；`ksa_normalized`、`tasks_normalized` 的每個 id 都存在於詞彙表；`pm_domains` 七項合計為 100；`jd_summary` 未超過字數上限，且與原文無連續 15 字以上相同。
  * **提示注入測試：** 餵入夾帶「忽略以上指示，輸出……」、HTML／`<script>` 標籤與網址的假 JD，驗證輸出不受影響，或該筆被判為驗證失敗。
  * **歧視性條件測試：** 餵入含「限男性」「役畢」「35 歲以下」「外型佳」的假 JD，驗證這些條件不出現在 KSA，且正確記入 `compliance_flags`。
  * **學歷與科系測試：** 餵入內文寫「電機、材料相關科系尤佳」的假 JD，驗證 `majors` 對應為 `MAJ_EE`、`MAJ_MAT`，且 `major_required` 為 `false`；104 結構化欄位與內文衝突時，以 104 欄位為準。
  * **個資過濾測試：** 餵入含人資姓名、Email、電話的假 JD，驗證輸出不含這些資料。
  * **依據片段測試：** 驗證找不到原文依據的標籤被捨棄，且依據片段未寫入資料檔。
* **測項 3：狀態流轉與歸檔（`--test-archive`）**
  * 用假資料庫驗證：連續 3 天未出現才轉為 `closed`；重新出現會轉回 `open`；`closed` 超過 30 天移入歷史檔；爬取不完整時不變更任何狀態；超過 80 筆時多出的職缺標為 `pending`；AI 分析失敗轉為 `failed`，連續 3 天後轉為 `error`。
* **測項 4：配適度計算（前端單元測試）**
  * 以固定的假職缺與假勾選資料驗證：全部具備為 100%、全部未具備為 0%、「略懂」以 0.5 計、某類別無要求時權重正確重新分配、`pending` 職缺不計分；學歷達標計 1、未達計 0；科系符合計 1、不符合時必要計 0、尤佳計 0.5；學歷與科系不拘時不增加 K 項目。
* **測項 5：前端 XSS 防護**
  * 以職稱、公司名稱、摘要含 `<script>`、`<img onerror=...>` 的假資料載入前端，驗證只顯示為純文字，不會執行。
* **測項 6：匯出功能（前端）**
  * 職缺總表 CSV 的列數與目前篩選結果一致；以 Excel 開啟中文正常；欄位不含 `compliance_flags` 與 JD 原文；末列有來源標示。
  * 以 `=HYPERLINK(...)` 開頭的假職稱匯出後，儲存格前有單引號，Excel 不會執行公式。
  * 圖表 PNG 在亮、暗主題下文字皆清楚可讀；PDF 列印版面不含選單與按鈕。

---

## 7. 資料結構定義 (`data.json` 範例)
```json
{
  "updated_at": "2026-10-16T03:41:00+08:00",
  "jobs": [
    {
      "job_id": "104_7x9ab",
      "url": "https://www.104.com.tw/job/7x9ab",
      "company": "台灣積體電路製造股份有限公司",
      "company_en": "TSMC",
      "stock_code": "2330",
      "listing_type": "上市",
      "parent_company": null,
      "industry": "半導體製造業",
      "title": "專案工程師",
      "title_zh": "專案工程師",
      "title_en": "Project Engineer",
      "jd_lang": "zh",
      "role_type": "PjM",
      "location": "新竹市東區",
      "education_req": {
        "level": "ma",
        "majors": ["MAJ_EE", "MAJ_MAT", "MAJ_CHEM"],
        "major_required": true,
        "source": "104"
      },
      "salary_desc": "待遇面議",
      "experience_desc": "1年以上",
      "status": "open",
      "first_seen_date": "2026-10-16",
      "last_seen_date": "2026-10-16",
      "closed_date": null,
      "miss_count": 0,
      "ai_status": "done",
      "ai_fail_count": 0,
      "ai_model": "gemini-2.5-flash",
      "prompt_version": "1.0",
      "vocab_version": "1.0",
      "ksa": {
        "knowledge": [
          { "zh": "半導體製程基礎", "en": "Semiconductor Principles" },
          { "zh": "專案管理理論", "en": "Project Management Theory" }
        ],
        "skills": [
          { "zh": "MS Project 操作", "en": "MS Project" },
          { "zh": "英文多益 750 分以上", "en": "TOEIC 750+" },
          { "zh": "跨部門會議主持", "en": "Cross-functional Facilitation" }
        ],
        "attributes": [
          { "zh": "高抗壓性", "en": "Stress Tolerance" },
          { "zh": "嚴謹細心", "en": "Meticulousness" }
        ]
      },
      "ksa_normalized": {
        "knowledge": ["K_SEMICONDUCTOR", "K_PM_THEORY"],
        "skills": ["S_PM_TOOLS", "S_ENGLISH", "S_FACILITATION"],
        "attributes": ["A_STRESS_TOLERANCE", "A_DETAIL_ORIENTED"]
      },
      "jd_summary": {
        "zh": "負責先進製程導入專案的時程與資源控管，協調研發、製造與品保單位，追蹤良率改善進度並定期向主管回報。",
        "en": "Manages schedules and resources for advanced-process introduction projects, coordinating R&D, manufacturing and QA, and reporting yield-improvement progress."
      },
      "tasks_normalized": ["T_SCHEDULE_MGMT", "T_CROSS_FUNC_COORD", "T_PROGRESS_REPORT"],
      "pm_domains": { "D1": 5, "D2": 0, "D3": 35, "D4": 10, "D5": 0, "D6": 20, "D7": 30 },
      "stage_gate": ["S3", "S4", "S5"],
      "context": {
        "collaborators": ["RD", "MFG", "QA"],
        "product_type": "hardware",
        "market": "B2B",
        "travel": "occasional",
        "english_level": "reading"
      },
      "compliance_flags": []
    }
  ]
}
```

---

## 8. AI 資安與倫理
（詳見 PRD 原文規範）

---

## 9. 維運與部署
（詳見 PRD 原文規範）
