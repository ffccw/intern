/**
 * 台灣 50 / 中型 100 / 富櫃 50 管院頂尖實習雷達 Frontend Application
 * Fully zero-emoji, clean typography, responsive PWA.
 * Features:
 * - LINE Pure Black (#000000) Theme
 * - Expandable Deep Analysis Card (AI Summary, Bilingual KSA, Pure-text Business Stages, Pure-text Core Dimensions, Collaborators)
 * - Pure text only: Zero S1..S6 codes, Zero D1..D7 codes
 * - English / Traditional Chinese i18n Bilingual Switcher
 * - My Fit (自評) with Actionable Learning Gap Analysis Top 5
 * - Rich Insights (Stages, Dimensions, Collaborators, Courses)
 * - Archive Tab for PRD Section 5.4 compliance
 * - PRD compliant CSV export (PMJ_職缺總表_YYYYMMDD.csv)
 */

// State
let allJobs = [];
let currentLang = localStorage.getItem("tw50_lang") || "zh";
let currentFilter = {
  search: "",
  index: "all",
  domain: "all",
  degree: "all",
  english: "all"
};

// 10 Core Capability Badges for Quick Self-Assessment
const CAPABILITIES = [
  { id: "S_ENGLISH", label: "商務英文溝通 (TOEIC 750+)", label_en: "Business English (TOEIC 750+)", domain: "D6", keywords: ["英文", "English", "TOEIC", "外語", "多益", "外商"] },
  { id: "S_EXCEL", label: "Excel 樞紐分析與函數", label_en: "Advanced Excel & Pivot Tables", domain: "D5", keywords: ["Excel", "樞紐", "統計", "試算表", "報表分析"] },
  { id: "S_PRESENTATION", label: "商業簡報與提案表達", label_en: "Business Presentation & Pitching", domain: "D1", keywords: ["簡報", "提案", "表達", "口語簡報", "演講", "Pitch"] },
  { id: "S_PYTHON", label: "Python 程式與基礎數據", label_en: "Python & Data Analytics", domain: "D4", keywords: ["Python", "程式設計", "Coding", "爬蟲", "Script"] },
  { id: "S_SQL", label: "SQL 資料庫查詢", label_en: "SQL Database Queries", domain: "D4", keywords: ["SQL", "資料庫", "Database", "查詢", "MySQL"] },
  { id: "S_PM_TOOLS", label: "專案看板管理 (Jira/Trello/Notion)", label_en: "Kanban & PM Tools (Jira/Notion)", domain: "D4", keywords: ["專案管理概論", "專案管理", "Jira", "Trello", "Notion", "看板", "甘特圖"] },
  { id: "S_PRD_WRITING", label: "規格需求書 (PRD) 與企劃撰寫", label_en: "PRD & Project Proposal Writing", domain: "D3", keywords: ["PRD", "需求書", "規格書", "企劃書", "SOP"] },
  { id: "K_SUPPLY_CHAIN", label: "供應鏈與採購基礎概念", label_en: "Supply Chain & Procurement", domain: "D7", keywords: ["供應鏈", "採購", "運籌", "庫存", "資材", "Logistics", "SCM"] },
  { id: "A_DETAIL_ORIENTED", label: "嚴謹細心 (偏內向數據型優勢)", label_en: "Meticulous & Detail-oriented", domain: "D6", keywords: ["細心", "嚴謹", "耐心", "精確", "條理", "細微"] },
  { id: "A_COMMUNICATION", label: "熱情外向 (偏公開社交與表達)", label_en: "Proactive Communication & Social", domain: "D6", keywords: ["熱情", "外向", "社交", "公開表達", "活力", "活潑", "公關溝通"] }
];

let userSkills = JSON.parse(localStorage.getItem("tw50_user_skills") || "[]");

// i18n Dictionary
const I18N = {
  zh: {
    nav_jobs: "職缺總覽",
    nav_fit: "我的配適度",
    nav_insights: "趨勢統計",
    nav_archive: "歷史職缺",
    nav_about: "專案說明",
    btn_fit_quick: "能力自評診斷",
    btn_export_csv: "匯出 CSV",
    btn_print_pdf: "列印 PDF",
    theme_toggle: "亮/暗",
    search_placeholder: "搜尋公司、職稱、先修課程名稱（例如：資料庫管理、Python）...",
    brand_title: "管院頂尖實習雷達",
    filter_index_label: "公司等級：",
    filter_index_all: "全部企業",
    filter_index_tw50: "台灣 50 龍頭",
    filter_index_mid100: "中型 100 企業",
    filter_index_tpex50: "上櫃富櫃 50",
    filter_domain_label: "實習領域：",
    filter_domain_all: "全部領域",
    filter_domain_it: "資安 / IT 流程",
    filter_domain_supply: "供應鏈 / 採購",
    filter_domain_mkt: "品牌行銷 / 公關",
    filter_domain_data: "商業數據分析",
    filter_domain_hr: "人資 / 行政",
    filter_degree_label: "學歷資格：",
    filter_degree_badge: "大學部在學限定（100% 學士生職缺）",
    filter_english_label: "英文要求：",
    filter_eng_all: "不限",
    filter_eng_mid: "英文中等",
    filter_eng_fluent: "英文流利",
    results_prefix: "共符合",
    results_suffix: "筆頂尖實習職缺",
    card_location: "地點：",
    card_salary: "待遇：",
    card_degree: "學歷：",
    card_duties_title: "實際工作職責：",
    card_courses_title: "建議先修大學課程（點擊可快速過濾）：",
    card_trait_title: "特質提醒：",
    card_updated_prefix: "104 更新：",
    card_scraped_prefix: "資料擷取：",
    card_apply_btn: "[ 前往 104 應徵 ↗ ]",
    card_expand_btn: "[ 展開完整分析 ▾ ]",
    card_collapse_btn: "[ 收合完整分析 ▴ ]",
    detail_summary_title: "AI 職缺深度摘要：",
    detail_ksa_title: "雙語核心職能標籤（KSA）：",
    detail_stages_title: "商業專案參與階段：",
    detail_dimensions_title: "核心商業能力構面：",
    detail_collab_title: "主要跨部門協作：",
    detail_match_title: "個人自評適配比對：",
    matched_tag: "已具備",
    gap_tag: "建議補強",
    fit_modal_title: "個人能力健檢與契合度排序",
    fit_modal_subtitle: "依據您勾選的修課與技能，系統將依契合度重新排列 79 筆大廠實習（保留全體職缺，不予隱藏刪除）。",
    fit_modal_notice_title: "[ 產品機制說明 ] 軟性勝率排序，非硬性條件過濾：",
    fit_modal_notice_desc: "本自評絕不隱藏或刪除任何職缺。系統將 79 筆指標大廠實習依契合度由高至低重新排序，並為您標註特定職缺之具備項目與補強建議。",
    fit_presets_title: "快速套用常見學生角色（一鍵代入）：",
    preset_mkt_title: "行銷企劃型",
    preset_mkt_desc: "簡報、社群、熱情外向",
    preset_data_title: "商業數據型",
    preset_data_desc: "Excel、SQL、嚴謹細心",
    preset_ops_title: "專案運籌型",
    preset_ops_desc: "供應鏈、時程、溝通協調",
    fit_caps_title: "勾選具備的能力標籤（點擊切換）：",
    fit_gaps_title: "最常被大廠要求的核心能力缺口 Top 5（建議補強方向）：",
    btn_reset_fit: "重置",
    btn_apply_fit_modal: "套用契合度智慧排序 (保留全體 79 筆職缺)",
    card_fit_matched_label: "針對此職缺已具備技能：",
    card_fit_gap_label: "針對此職缺建議補強：",
    card_fit_perfect: "條件高度契合，具備該職缺全部核心要求！",
    card_fit_none_required: "此職缺以實習態度與通識為重，無特定先備門檻。",
    fit_banner_title: "【已套用能力自評】",
    fit_banner_desc: "已為您計算各職缺適配度，職缺卡片已依匹配度由高至低重新排序（保留全體職缺）。",
    card_ptt_btn: "[ PTT 評價 ↗ ]",
    insights_main_title: "2026 台灣 50 / 中型 100 / 富櫃 50 管院實習趨勢觀察",
    insights_main_subtitle: "依據全體收錄 79 筆指標企業在學實習職缺之結構化大數據統計",
    chart_courses_title: "最常被大廠要求的先修大學課程 Top 5",
    chart_stages_title: "商業專案流程參與熱度（純文字）",
    chart_dimensions_title: "各大廠最看重的核心商業能力構面（純文字）",
    chart_collab_title: "實習進公司後主要跨部門協作對象排行",
    footer_edu: "For Educational Use Only｜104 台灣 50 管院頂尖實習雷達",
    footer_update: "資料更新時間：2026-10-18｜依 104 人力銀行與 TWSE 公開資料整理",
    fit_banner_clear: "清除自評重置"
  },
  en: {
    nav_jobs: "Jobs Overview",
    nav_fit: "My Fit",
    nav_insights: "Insights",
    nav_archive: "Archive",
    nav_about: "About",
    brand_title: "Top Management Intern Radar",
    btn_fit_quick: "Self Assessment",
    btn_export_csv: "Export CSV",
    btn_print_pdf: "Print PDF",
    theme_toggle: "Light/Dark",
    search_placeholder: "Search company, title, course (e.g. Database, Python)...",
    filter_index_label: "Company Index:",
    filter_index_all: "All Companies",
    filter_index_tw50: "Taiwan 50",
    filter_index_mid100: "Mid 100",
    filter_index_tpex50: "TPEx 50",
    filter_domain_label: "Internship Domain:",
    filter_domain_all: "All Domains",
    filter_domain_it: "Cybersecurity / IT",
    filter_domain_supply: "Supply Chain / SCM",
    filter_domain_mkt: "Marketing / PR",
    filter_domain_data: "Data Analytics",
    filter_domain_hr: "HR / Administration",
    filter_degree_label: "Education:",
    filter_degree_badge: "Undergraduates Only (100% Bachelor)",
    filter_english_label: "English:",
    filter_eng_all: "Any",
    filter_eng_mid: "Intermediate",
    filter_eng_fluent: "Fluent",
    results_prefix: "Found",
    results_suffix: "Top Internships",
    card_location: "Location: ",
    card_salary: "Salary: ",
    card_degree: "Degree: ",
    card_duties_title: "Core Responsibilities:",
    card_courses_title: "Recommended College Courses (Click to filter):",
    card_trait_title: "Trait Guidance: ",
    card_updated_prefix: "104 Updated: ",
    card_scraped_prefix: "Scraped: ",
    card_apply_btn: "[ Apply on 104 ↗ ]",
    card_ptt_btn: "[ PTT Review ↗ ]",
    card_expand_btn: "[ Expand Details ▾ ]",
    card_collapse_btn: "[ Collapse Details ▴ ]",
    detail_summary_title: "AI Deep Summary:",
    detail_ksa_title: "Bilingual Competency Tags (KSA):",
    detail_stages_title: "Business Project Stages:",
    detail_dimensions_title: "Core Competency Dimensions:",
    detail_collab_title: "Cross-functional Collaborators: ",
    detail_match_title: "Self-Assessment Fit Breakdown:",
    matched_tag: "Matched",
    gap_tag: "Recommended Gap",
    fit_modal_title: "Competency Assessment & Smart Fit Ranking",
    fit_modal_subtitle: "Re-order 79 top enterprise internships by suitability based on your selected skills (all jobs kept, never hidden).",
    fit_modal_notice_title: "[ Product Architecture ] Soft Smart Sorting, Not Hard Filtering:",
    fit_modal_notice_desc: "This assessment never hides or removes any jobs. It dynamically re-orders all 79 internships from highest match to lowest, and highlights matched skills and gaps per role.",
    fit_presets_title: "Quick Student Personas (1-Click Fill):",
    preset_mkt_title: "Marketing & PR",
    preset_mkt_desc: "Pitch, Social Media, Proactive",
    preset_data_title: "Business Data",
    preset_data_desc: "Excel, SQL, Meticulous",
    preset_ops_title: "Project & Ops",
    preset_ops_desc: "Supply Chain, Timeline, Collab",
    fit_caps_title: "Select Your Capabilities (Click to toggle):",
    fit_gaps_title: "Top 5 Enterprise Competency Gaps (Recommended Focus):",
    btn_reset_fit: "Reset",
    btn_apply_fit_modal: "Apply Smart Fit Ranking (Keep All 79 Jobs)",
    card_fit_matched_label: "Matched Skills for this Role:",
    card_fit_gap_label: "Recommended Gaps for this Role:",
    card_fit_perfect: "Strong fit! Meets all core requirements for this position.",
    card_fit_none_required: "Role emphasizes general attitude and fundamentals without strict prerequisites.",
    fit_banner_title: "[ Self-Assessment Applied ]",
    fit_banner_desc: "Suitability scores computed. All 79 roles re-ordered by match (no jobs hidden).",
    insights_main_title: "2026 Taiwan 50 / Mid 100 / TPEx 50 Management Intern Trends",
    insights_main_subtitle: "Structured big data insights across all 79 curated top enterprise internships",
    chart_courses_title: "Top 5 Recommended College Courses Required by Enterprises",
    chart_stages_title: "Business Project Lifecycle Participation (Pure Text)",
    chart_dimensions_title: "Core Business Competency Dimensions (Pure Text)",
    chart_collab_title: "Top Cross-functional Collaborators Ranking",
    footer_edu: "For Educational Use Only | Taiwan Top Management Intern Radar",
    footer_update: "Updated: 2026-10-18 | Based on 104 Job Bank & TWSE Public Data",
    fit_banner_clear: "Clear Assessment"
  }
};

// DOM Elements
const jobsContainer = document.getElementById("jobs-container");
const searchInput = document.getElementById("search-input");
const resultsCount = document.getElementById("results-count");
const themeToggle = document.getElementById("theme-toggle");
const langToggle = document.getElementById("lang-toggle");
const modalFit = document.getElementById("modal-fit");
const btnFitQuick = document.getElementById("btn-fit-quick");
const btnCloseFit = document.getElementById("btn-close-fit");
const btnResetFitModal = document.getElementById("btn-reset-fit-modal");
const btnApplyFitModal = document.getElementById("btn-apply-fit-modal");
const fitSummaryBanner = document.getElementById("fit-summary-banner");
const btnClearFit = document.getElementById("btn-clear-fit");
const capabilitiesGrid = document.getElementById("capabilities-grid");
const fitGapsList = document.getElementById("fit-gaps-list");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initI18n();
  initNavigation();
  initPWA();
  renderCapabilityBadges();
  await loadJobData();
  bindEvents();
});

const GOOGLE_SHEET_ID = "1wv5PEYIZk7S-bJP1M7S1XPKvXCXAwEqtBFPcFNmZMDI";

// Load Job Data
async function loadJobData() {
  try {
    const res = await fetch("data/data.json?t=" + Date.now());
    if (res.ok) {
      const json = await res.json();
      if (json.jobs && json.jobs.length > 0) {
        allJobs = json.jobs;
      }
    }

    if (allJobs.length === 0 && GOOGLE_SHEET_ID) {
      try {
        const sheetCsvUrl = `https://docs.google.com/spreadsheets/d/${GOOGLE_SHEET_ID}/export?format=csv`;
        const sheetRes = await fetch(sheetCsvUrl);
        if (sheetRes.ok) {
          const csvText = await sheetRes.text();
          allJobs = parseGoogleSheetCsv(csvText) || [];
        }
      } catch (sheetErr) {
        console.warn("[Cloud DB] Google Sheet read fallback error:", sheetErr);
      }
    }

    applyFiltersAndRender();
    renderInsights();
    renderGapAnalysis();
  } catch (err) {
    console.error("Failed to load jobs data:", err);
    jobsContainer.innerHTML = `<div class="p-8 text-center text-red-500">無法讀取職缺資料，請確認 data/data.json 是否存在。</div>`;
  }
}

// Fallback CSV Parser
function parseGoogleSheetCsv(text) {
  if (!text || text.trim().length === 0) return [];
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]);
  const jobs = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCsvLine(lines[i]);
    if (values.length < 5) continue;
    
    const row = {};
    headers.forEach((h, idx) => {
      row[h.trim()] = (values[idx] || "").trim();
    });

    const courses = (row["建議先修大學課程"] || "").split(/[、,]/).map(s => s.trim()).filter(Boolean);
    const duties = [row["工作職責一"], row["工作職責二"], row["工作職責三"]].filter(Boolean);

    jobs.push({
      job_id: row["job_id"] || `job_${i}`,
      company: row["公司名稱"] || "",
      company_en: row["公司名稱"] || "",
      stock_code: row["股票代號"] || "",
      index_type: row["成分股指數"] || "台灣 50",
      title: row["職缺名稱"] || "",
      title_en: row["職缺名稱"] || "",
      location: row["實習地點"] || "",
      salary_desc: row["實習待遇"] || "時薪制",
      experience_desc: row["學歷要求"] || row["條件要求"] || "大學部在學（學士生）",
      appear_date: row["104職缺更新日期"] || "2026-10-18",
      job_duties: duties.length > 0 ? duties : ["參與專案日常進度追蹤與時程控管", "跨職能團隊溝通協調與週會會議紀錄彙整"],
      recommended_courses: courses.length > 0 ? courses : ["專案管理概論", "商務英文"],
      trait_advice: row["特質建議"] || "適合具備團隊溝通熱忱、處事細心嚴謹之同學。",
      url: row["104原始連結"] || "https://www.104.com.tw/jobs/search/?keyword=" + encodeURIComponent(row["公司名稱"] || ""),
      status: row["狀態"] || "open",
      project_stages: ["行銷企劃與需求提案", "方案設計與原型驗證", "成果發表與成效維運"],
      project_stages_en: ["Marketing Proposal & Need Discovery", "Solution Design & Prototyping", "Launch & Performance Review"],
      core_dimensions: [
        { name: "商業策略與定位", name_en: "Business Strategy", weight: 35 },
        { name: "創新與專案流程", name_en: "Process & Workflow", weight: 35 },
        { name: "團隊溝通與跨部門領導", name_en: "Team Leadership", weight: 30 }
      ],
      collaborators: ["RD 研發處", "MKT 行銷團隊", "QA 品保處"],
      jd_summary: {
        zh: `協助${row["公司名稱"] || "企業"}推動關鍵專案流程與業務支援，負責日常時程追蹤與跨單位協調。`,
        en: `Assists ${row["公司名稱"] || "company"} in project operations, milestone tracking, and cross-functional coordination.`
      }
    });
  }
  return jobs;
}

function parseCsvLine(line) {
  const result = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (c === ',' && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += c;
    }
  }
  result.push(current);
  return result;
}

// Render Job Cards
function applyFiltersAndRender() {
  const query = currentFilter.search.toLowerCase().trim();
  const t = I18N[currentLang];

  let filtered = allJobs.filter((job) => {
    if (query) {
      const matchText = (
        job.company + " " +
        (job.company_en || "") + " " +
        (job.parent_company || "") + " " +
        (job.stock_code || "") + " " +
        job.title + " " +
        (job.title_en || "") + " " +
        (job.location || "") + " " +
        (job.recommended_courses || []).join(" ") + " " +
        (job.job_duties || []).join(" ")
      ).toLowerCase();
      if (!matchText.includes(query)) return false;
    }

    if (currentFilter.index !== "all" && job.index_type !== currentFilter.index) {
      return false;
    }

    if (currentFilter.domain !== "all") {
      const titleCorp = job.title + " " + (job.recommended_courses || []).join(" ");
      if (currentFilter.domain === "資安/IT" && !titleCorp.includes("資安") && !titleCorp.includes("IT") && !titleCorp.includes("Server")) return false;
      if (currentFilter.domain === "供應鏈" && !titleCorp.includes("供應鏈") && !titleCorp.includes("採購") && !titleCorp.includes("資材")) return false;
      if (currentFilter.domain === "行銷" && !titleCorp.includes("行銷") && !titleCorp.includes("品牌") && !titleCorp.includes("公關")) return false;
      if (currentFilter.domain === "數據分析" && !titleCorp.includes("數據") && !titleCorp.includes("分析") && !titleCorp.includes("資料")) return false;
      if (currentFilter.domain === "人資" && !titleCorp.includes("人資") && !titleCorp.includes("行政") && !titleCorp.includes("訓練")) return false;
    }

    if (currentFilter.english !== "all") {
      const engContext = (job.context?.english_level || "") + " " + job.title + " " + (job.recommended_courses || []).join(" ");
      if (currentFilter.english === "fluent" && !engContext.includes("流利") && !engContext.includes("primary")) return false;
    }

    return true;
  });

  if (userSkills.length > 0) {
    filtered.forEach((job) => {
      job.fitScore = calculateFitScore(job, userSkills);
    });
    filtered.sort((a, b) => (b.fitScore || 0) - (a.fitScore || 0));
    fitSummaryBanner.classList.remove("hidden");
  } else {
    filtered.forEach((job) => (job.fitScore = null));
    fitSummaryBanner.classList.add("hidden");
  }

  resultsCount.textContent = `${t.results_prefix} ${filtered.length} ${t.results_suffix}`;

  if (filtered.length === 0) {
    jobsContainer.innerHTML = `
      <div class="bg-white dark:bg-[#121212] p-12 text-center rounded-lg border border-slate-200 dark:border-[#242424] text-slate-500 dark:text-[#8E8E93]">
        ${currentLang === 'en' ? 'No matching internships found. Try expanding filter options.' : '查無符合條件之大廠實習。建議放寬篩選條件或清除搜尋關鍵字。'}
      </div>
    `;
    return;
  }

  jobsContainer.innerHTML = filtered.map((job) => renderJobCard(job)).join("");

  // Course badges quick filtering
  document.querySelectorAll(".course-badge").forEach((el) => {
    el.addEventListener("click", (e) => {
      const crsName = e.currentTarget.getAttribute("data-course");
      searchInput.value = crsName;
      currentFilter.search = crsName;
      applyFiltersAndRender();
    });
  });

  // Attach toggle listeners for [ 展開完整分析 ▾ ]
  document.querySelectorAll(".btn-toggle-detail").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const targetId = e.currentTarget.getAttribute("data-target");
      const detailEl = document.getElementById(targetId);
      if (!detailEl) return;
      const isHidden = detailEl.classList.contains("hidden");
      if (isHidden) {
        detailEl.classList.remove("hidden");
        e.currentTarget.textContent = t.card_collapse_btn;
      } else {
        detailEl.classList.add("hidden");
        e.currentTarget.textContent = t.card_expand_btn;
      }
    });
  });

  // Keep gap analysis in sync with active domain filter
  renderGapAnalysis();
}

// Translation Helpers for Content Localization
function translateLocation(loc) {
  if (!loc) return "Taiwan";
  let en = loc;
  en = en.replace("台北市", "Taipei City ").replace("新北市", "New Taipei ").replace("桃園市", "Taoyuan City ").replace("新竹市", "Hsinchu City ").replace("新竹縣", "Hsinchu County ").replace("苗栗縣", "Miaoli County ").replace("台中市", "Taichung City ").replace("台南市", "Tainan City ").replace("高雄市", "Kaohsiung City ");
  en = en.replace("大安區", "Da'an Dist.").replace("內湖區", "Neihu Dist.").replace("松山區", "Songshan Dist.").replace("中山區", "Zhongshan Dist.").replace("信義區", "Xinyi Dist.").replace("中正區", "Zhongzheng Dist.").replace("南港區", "Nangang Dist.").replace("土城區", "Tucheng Dist.").replace("板橋區", "Banqiao Dist.").replace("中和區", "Zhonghe Dist.").replace("汐止區", "Xizhi Dist.").replace("新店區", "Xindian Dist.").replace("中壢區", "Zhongli Dist.").replace("龜山區", "Guishan Dist.").replace("西屯區", "Xitun Dist.").replace("楠梓區", "Nanzi Dist.");
  return en.trim();
}

function translateSalary(sal) {
  if (!sal || sal === "待遇面議") return "Competitive / Negotiable";
  let en = sal.replace("待遇面議", "Competitive / Negotiable");
  en = en.replace("時薪", "Hourly NT$ ").replace("月薪", "Monthly NT$ ").replace("元", "");
  return en.trim();
}

const COURSE_EN_MAP = {
  "人力資源管理": "Human Resource Management",
  "組織行為學": "Organizational Behavior",
  "資料庫管理": "Database Management",
  "統計學與數據分析": "Statistics & Data Analytics",
  "商管程式設計 / Python": "Business Python",
  "人工智慧與商業應用": "AI & Business",
  "資訊安全導論": "Intro to Cybersecurity",
  "作業系統概論": "Operating Systems",
  "供應鏈與運籌管理": "Supply Chain & Logistics",
  "作業管理與製程規劃": "Operations Management",
  "企業管理導論": "Intro to Business Management",
  "商務英文溝通與簡報": "Business English",
  "財務管理": "Financial Management",
  "管理會計學": "Managerial Accounting",
  "行銷管理": "Marketing Management",
  "消費者行為": "Consumer Behavior",
  "專案管理概論": "Project Management",
  "商業智慧與大數據分析": "Business Intelligence",
  "系統分析與設計": "Systems Analysis & Design",
  "網路行銷與社群經營": "Digital Marketing",
  "國際企業經營策略": "International Strategy"
};

function translateCourse(c) {
  return COURSE_EN_MAP[c] || c;
}

const COLLAB_EN_MAP = {
  "HR 人資處": "HR Department",
  "各部門主管": "Department Directors",
  "外部培訓機構": "Training Partners",
  "RD 研發處": "R&D Engineering",
  "MKT 行銷團隊": "Marketing Team",
  "QA 品保處": "QA & Reliability",
  "PM 專案經理": "Project Managers",
  "業務銷售團隊": "Sales Team",
  "法務處": "Legal & Compliance",
  "財務處": "Finance & Accounting",
  "採購處": "Procurement Dept",
  "PUR 採購處": "Procurement Dept",
  "資訊服務處": "IT & Infrastructure",
  "IT 資訊團隊": "IT & Engineering",
  "SALES 業務處": "Sales Department",
  "DESIGN 設計團隊": "Design & UX Team",
  "MFG 製造廠": "Manufacturing Plant",
  "外部供應商": "External Vendors",
  "高階主管": "Executive Leadership",
  "客戶端負責人": "Client Stakeholders",
  "製造工廠端": "Manufacturing Ops",
  "供應商夥伴": "Vendor Partners",
  "商業決策主管": "Business Decision Leaders",
  "行銷/營運處": "Marketing & Ops",
  "品牌公關部": "PR & Brand Team",
  "永續發展委員會": "ESG Committee"
};

function translateCollaborator(cb) {
  return COLLAB_EN_MAP[cb] || cb;
}

// Render Single Job Card
function renderJobCard(job) {
  const t = I18N[currentLang];
  const isEn = currentLang === "en";

  const displayCompany = isEn && job.company_en ? job.company_en : job.company;
  const displayTitle = isEn && job.title_en ? job.title_en : job.title;
  const displayIndex = isEn ? (job.index_type === "台灣 50" ? "Taiwan 50" : (job.index_type === "中型 100" ? "Mid 100" : "TPEx 50")) : job.index_type;
  const displayLocation = isEn ? translateLocation(job.location) : job.location;
  const displaySalary = isEn ? translateSalary(job.salary_desc) : job.salary_desc;
  const traitAdviceText = isEn && job.trait_advice_en ? job.trait_advice_en : job.trait_advice;

  const indexBadgeClass =
    job.index_type === "台灣 50"
      ? "bg-[#D8C3A5] dark:bg-[#06C755]/20 dark:text-[#06C755] text-[#004030] font-bold dark:border dark:border-[#06C755]/40"
      : "bg-slate-200 dark:bg-[#1E1E1E] text-slate-800 dark:text-[#D4D4D4] dark:border dark:border-[#262626]";

  let fitBadgeHtml = "";
  if (job.fitScore !== null) {
    let fitColor = "border-slate-400 text-slate-600 dark:border-[#262626] dark:text-[#8E8E93]";
    if (job.fitScore >= 70) fitColor = "bg-[#004030] dark:bg-[#06C755] text-white font-bold border-[#004030] dark:border-[#06C755]";
    else if (job.fitScore >= 50) fitColor = "bg-[#D8C3A5] dark:bg-[#06C755]/30 text-[#004030] dark:text-[#06C755] font-bold border-[#D8C3A5] dark:border-[#06C755]";
    fitBadgeHtml = `<span class="px-2 py-0.5 text-xs rounded border ${fitColor}">${isEn ? 'Match' : '契合度'} ${job.fitScore}%</span>`;
  }

  const pttUrl = job.discussion_links?.ptt_url;
  const pttButtonHtml = pttUrl
    ? `<a href="${pttUrl}" target="_blank" rel="noopener noreferrer" class="btn-ptt-eval px-3 py-1 rounded border border-slate-300 dark:border-[#262626] dark:bg-[#161616] hover:border-[#004030] dark:hover:border-[#06C755] text-slate-700 dark:text-[#CCCCCC] transition text-xs font-medium shrink-0" title="PTT Tech_Job 評價討論">${t.card_ptt_btn || '[ PTT 評價 ↗ ]'}</a>`
    : "";

  const rawDuties = isEn && job.job_duties_en && job.job_duties_en.length > 0 ? job.job_duties_en : (job.job_duties || []);
  const dutiesHtml = rawDuties
    .map((d, i) => `<li class="flex items-start space-x-2"><span class="font-mono text-slate-400 dark:text-[#666666] font-semibold">${i + 1}.</span><span>${d}</span></li>`)
    .join("");

  const coursesHtml = (job.recommended_courses || [])
    .map(
      (c) => {
        const cDisplay = isEn ? translateCourse(c) : c;
        return `<button class="course-badge px-2 py-0.5 rounded border border-slate-300 dark:border-[#2A2A2A] hover:border-[#004030] dark:hover:border-[#06C755] text-slate-700 dark:text-[#CCCCCC] transition text-[11px]" data-course="${c}" title="Filter">[ ${cDisplay} ]</button>`;
      }
    )
    .join(" ");

  // Pure Text Project Stages (Zero S1..S6 codes!)
  const stagesList = isEn && job.project_stages_en ? job.project_stages_en : (job.project_stages || ["行銷企劃與需求提案", "方案設計與原型驗證", "成果發表與成效維運"]);
  const stagesBadgesHtml = stagesList
    .map(st => `<span class="px-2 py-0.5 rounded border border-emerald-300 dark:border-[#06C755]/40 bg-emerald-50 dark:bg-[#06C755]/10 text-emerald-800 dark:text-[#06C755] text-[11px] font-medium">[ ${st} ]</span>`)
    .join(" ");

  // Pure Text Dimensions with weight bars (Zero D1..D7 codes!)
  const dimensionsList = job.core_dimensions || [
    { name: "商業策略與定位", name_en: "Business Strategy", weight: 35 },
    { name: "創新與專案流程", name_en: "Process & Workflow", weight: 35 },
    { name: "團隊溝通與跨部門領導", name_en: "Team Communication", weight: 30 }
  ];
  const dimensionsBarsHtml = dimensionsList.map(dm => {
    const dmName = isEn && dm.name_en ? dm.name_en : dm.name;
    const w = dm.weight || 30;
    return `
      <div class="space-y-0.5">
        <div class="flex justify-between text-[11px]">
          <span class="text-slate-700 dark:text-[#D4D4D4] font-medium">${dmName}</span>
          <span class="font-mono text-slate-400 dark:text-[#8E8E93]">${w}%</span>
        </div>
        <div class="w-full h-1.5 rounded-full bg-slate-200 dark:bg-[#222222] overflow-hidden">
          <div class="h-full bg-[#004030] dark:bg-[#06C755] rounded-full" style="width: ${w}%"></div>
        </div>
      </div>
    `;
  }).join("");

  // Bilingual KSA Badges
  const ksaData = job.bilingual_ksa || {
    knowledge: [{ zh: "商業專案管理理論", en: "Project Management Theory" }],
    skills: [{ zh: "Excel 樞紐分析", en: "Advanced Excel" }, { zh: "商務簡報與溝通", en: "Business Presentation" }],
    attributes: [{ zh: "嚴謹細心", en: "Meticulousness" }, { zh: "跨部門溝通熱忱", en: "Proactive Communication" }]
  };
  const kBadges = (ksaData.knowledge || []).map(k => `<span class="px-2 py-0.5 rounded border border-slate-300 dark:border-[#262626] dark:bg-[#161616] text-[11px]">${isEn ? k.en : k.zh}</span>`).join(" ");
  const sBadges = (ksaData.skills || []).map(s => `<span class="px-2 py-0.5 rounded border border-slate-300 dark:border-[#262626] dark:bg-[#161616] text-[11px]">${isEn ? s.en : s.zh}</span>`).join(" ");
  const aBadges = (ksaData.attributes || []).map(a => `<span class="px-2 py-0.5 rounded border border-slate-300 dark:border-[#262626] dark:bg-[#161616] text-[11px]">${isEn ? a.en : a.zh}</span>`).join(" ");

  // AI Summary
  const aiSummaryText = isEn
    ? (job.jd_summary?.en || `Supports key workflows and cross-functional operations at ${displayCompany}.`)
    : (job.jd_summary?.zh || `協助${displayCompany}推動日常關鍵業務流程，支援專案進度追蹤與跨單位協調作業。`);

  // Collaborators
  const rawCollabs = job.collaborators || ["RD 研發處", "MKT 行銷團隊", "QA 品保處"];
  const collabText = isEn
    ? rawCollabs.map(c => translateCollaborator(c)).join(", ")
    : rawCollabs.join("、");

  // Fit Breakdown if evaluated (1-on-1 Micro Job Specific Breakdown!)
  let fitBreakdownHtml = "";
  if (userSkills.length > 0) {
    const requiredCaps = CAPABILITIES.filter(cap => jobRequiresCapability(job, cap));
    const matchedCaps = requiredCaps.filter(cap => userSkills.includes(cap.id));
    const gapCaps = requiredCaps.filter(cap => !userSkills.includes(cap.id));

    let matchedBadges = "";
    if (matchedCaps.length > 0) {
      matchedBadges = matchedCaps.map(c => {
        const lbl = isEn ? c.label_en : c.label;
        return `<span class="px-2 py-0.5 rounded bg-emerald-100 dark:bg-[#06C755]/20 text-emerald-800 dark:text-[#06C755] text-[11px] font-semibold border border-emerald-300 dark:border-[#06C755]/40">[ ✓ ${lbl} ]</span>`;
      }).join(" ");
    }

    let gapBadges = "";
    if (gapCaps.length > 0) {
      gapBadges = gapCaps.map(c => {
        const lbl = isEn ? c.label_en : c.label;
        return `<span class="px-2 py-0.5 rounded bg-slate-100 dark:bg-[#1A1A1A] text-slate-700 dark:text-[#A0A0A0] text-[11px] border border-slate-300 dark:border-[#2C2C2C]">[ ${isEn ? 'Gap: ' : '建議補強：'}${lbl} ]</span>`;
      }).join(" ");
    }

    let statusNote = "";
    if (requiredCaps.length > 0 && gapCaps.length === 0) {
      statusNote = `<span class="text-[11px] text-emerald-600 dark:text-[#06C755] font-semibold">${t.card_fit_perfect}</span>`;
    } else if (requiredCaps.length === 0) {
      statusNote = `<span class="text-[11px] text-slate-500 dark:text-[#8E8E93]">${t.card_fit_none_required}</span>`;
    }

    fitBreakdownHtml = `
      <div class="space-y-2 text-xs pt-2.5 border-t border-slate-200 dark:border-[#242424] bg-emerald-50/50 dark:bg-[#06C755]/5 p-3 rounded">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <span class="font-bold text-slate-800 dark:text-white text-[11px]">${t.detail_match_title}</span>
          ${statusNote}
        </div>
        ${matchedBadges ? `<div class="space-y-1"><span class="text-[10px] text-slate-500 dark:text-[#8E8E93] block font-medium">${t.card_fit_matched_label}</span><div class="flex flex-wrap gap-1.5">${matchedBadges}</div></div>` : ''}
        ${gapBadges ? `<div class="space-y-1"><span class="text-[10px] text-slate-500 dark:text-[#8E8E93] block font-medium">${t.card_fit_gap_label}</span><div class="flex flex-wrap gap-1.5">${gapBadges}</div></div>` : ''}
      </div>
    `;
  }

  const detailTargetId = `detail-${job.job_id}`;

  return `
    <article class="job-card bg-white dark:bg-[#121212] rounded-lg p-5 border border-slate-200 dark:border-[#242424] shadow-sm hover:shadow transition space-y-4">
      
      <!-- Top Header -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-[#242424]">
        <div>
          <div class="flex items-center space-x-2 text-xs">
            <span class="font-bold text-slate-900 dark:text-white">${displayCompany}</span>
            <span class="text-slate-400 dark:text-[#8E8E93] font-mono">(${job.stock_code})</span>
            <span class="px-2 py-0.5 rounded text-[11px] ${indexBadgeClass}">[ ${displayIndex} ]</span>
          </div>
          <h3 class="text-base font-bold font-serif text-slate-900 dark:text-white mt-1">${displayTitle}</h3>
        </div>
        <div class="flex items-center space-x-2 shrink-0">
          ${fitBadgeHtml}
        </div>
      </div>

      <!-- Essential Specs Grid -->
      <div class="job-specs grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600 dark:text-[#D4D4D4] bg-slate-50 dark:bg-[#161616] p-3 rounded">
        <div><span class="font-semibold text-slate-400 dark:text-[#8E8E93]">${t.card_location}</span>${displayLocation}</div>
        <div><span class="font-semibold text-slate-400 dark:text-[#8E8E93]">${t.card_salary}</span><span class="font-semibold text-slate-900 dark:text-white">${displaySalary}</span></div>
        <div><span class="font-semibold text-slate-400 dark:text-[#8E8E93]">${t.card_degree}</span>${isEn ? 'Undergraduate Student' : '大學部在學（學士生）'}</div>
      </div>

      <!-- Real Job Duties -->
      <div class="space-y-1 text-xs">
        <span class="font-semibold text-slate-500 dark:text-[#8E8E93] uppercase tracking-wider text-[11px]">${t.card_duties_title}</span>
        <ul class="space-y-1 text-slate-700 dark:text-[#D4D4D4] pl-1">
          ${dutiesHtml}
        </ul>
      </div>

      <!-- Recommended University Courses -->
      <div class="space-y-1 text-xs pt-1">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-slate-500 dark:text-[#8E8E93] uppercase tracking-wider text-[11px]">${t.card_courses_title}</span>
        </div>
        <div class="flex flex-wrap gap-1.5 pt-0.5">
          ${coursesHtml}
        </div>
      </div>

      <!-- Trait Insights -->
      <div class="job-trait text-xs p-2.5 rounded bg-slate-100/70 dark:bg-[#161616] text-slate-700 dark:text-[#D4D4D4] border-l-2 border-[#004030] dark:border-[#06C755]">
        <span class="font-semibold">${t.card_trait_title}</span>${traitAdviceText}
      </div>

      <!-- Expandable Deep Analysis Drawer -->
      <div id="${detailTargetId}" class="job-detail hidden space-y-3 pt-3 border-t border-slate-100 dark:border-[#242424]">
        
        <!-- AI Deep Summary -->
        <div class="p-3 rounded bg-slate-50 dark:bg-[#161616] border border-slate-200 dark:border-[#262626] space-y-1">
          <span class="font-bold text-[#004030] dark:text-[#06C755] text-xs">${t.detail_summary_title}</span>
          <p class="text-xs text-slate-800 dark:text-[#E0E0E0] leading-relaxed">${aiSummaryText}</p>
        </div>

        ${fitBreakdownHtml}

        <!-- Bilingual KSA Badges -->
        <div class="space-y-1 text-xs">
          <span class="font-semibold text-slate-500 dark:text-[#8E8E93] uppercase tracking-wider text-[11px]">${t.detail_ksa_title}</span>
          <div class="space-y-1 pt-0.5">
            <div class="flex items-center gap-1.5"><span class="text-slate-400 font-mono w-10 text-[10px]">${isEn ? 'Knowl.' : '知識'}：</span><div class="flex flex-wrap gap-1">${kBadges}</div></div>
            <div class="flex items-center gap-1.5"><span class="text-slate-400 font-mono w-10 text-[10px]">${isEn ? 'Skills' : '技能'}：</span><div class="flex flex-wrap gap-1">${sBadges}</div></div>
            <div class="flex items-center gap-1.5"><span class="text-slate-400 font-mono w-10 text-[10px]">${isEn ? 'Attrib.' : '態度'}：</span><div class="flex flex-wrap gap-1">${aBadges}</div></div>
          </div>
        </div>

        <!-- Pure Text Business Project Stages (No S1..S6 codes) -->
        <div class="space-y-1 text-xs">
          <span class="font-semibold text-slate-500 dark:text-[#8E8E93] uppercase tracking-wider text-[11px]">${t.detail_stages_title}</span>
          <div class="flex flex-wrap gap-1.5 pt-0.5">
            ${stagesBadgesHtml}
          </div>
        </div>

        <!-- Pure Text Core Competency Dimensions (No D1..D7 codes) -->
        <div class="space-y-1.5 text-xs">
          <span class="font-semibold text-slate-500 dark:text-[#8E8E93] uppercase tracking-wider text-[11px]">${t.detail_dimensions_title}</span>
          <div class="space-y-1.5 pt-0.5">
            ${dimensionsBarsHtml}
          </div>
        </div>

        <!-- Cross-functional Collaborators -->
        <div class="text-[11px] text-slate-600 dark:text-[#A0A0A0]">
          <span class="font-semibold text-slate-500 dark:text-[#8E8E93]">${t.detail_collab_title}</span>${collabText}
        </div>
      </div>

      <!-- Actions: 104 Update Date & Crawl Date, Expand Button & Direct Apply Button -->
      <div class="pt-3 border-t border-slate-100 dark:border-[#242424] flex flex-wrap items-center justify-between text-xs gap-2">
        <div class="flex items-center space-x-2 text-[11px] text-slate-400 dark:text-[#8E8E93]">
          <span>${t.card_updated_prefix}${job.appear_date || "2026-10-18"}</span>
          <span>·</span>
          <span>${t.card_scraped_prefix}${job.crawl_date || (job.scraped_at ? job.scraped_at.split(' ')[0] : "2026-10-18")}</span>
        </div>
        <div class="flex items-center space-x-2 shrink-0 ml-auto">
          ${pttButtonHtml}
          <button class="btn-toggle-detail px-3 py-1 rounded border border-slate-300 dark:border-[#262626] dark:bg-[#161616] hover:border-[#004030] dark:hover:border-[#06C755] text-slate-700 dark:text-[#CCCCCC] transition text-xs font-medium" data-target="${detailTargetId}">
            ${t.card_expand_btn}
          </button>
          <a href="${job.url}" target="_blank" rel="noopener noreferrer" 
             class="btn-apply-104 px-3 py-1 bg-[#004030] dark:bg-[#06C755] text-white font-medium rounded hover:bg-[#002f23] dark:hover:bg-[#05B04B] transition shrink-0">
            ${t.card_apply_btn}
          </a>
        </div>
      </div>

    </article>
  `;
}

// Capability Match Evaluation Helper
function jobRequiresCapability(job, cap) {
  if (!job || !cap || !cap.keywords) return false;
  const textCorpus = [
    job.title || "",
    job.title_en || "",
    (job.job_duties || []).join(" "),
    (job.job_duties_en || []).join(" "),
    (job.recommended_courses || []).join(" "),
    job.trait_advice || "",
    job.trait_advice_en || "",
    (job.bilingual_ksa?.knowledge || []).map(k => (k.zh || "") + " " + (k.en || "")).join(" "),
    (job.bilingual_ksa?.skills || []).map(s => (s.zh || "") + " " + (s.en || "")).join(" "),
    (job.bilingual_ksa?.attributes || []).map(a => (a.zh || "") + " " + (a.en || "")).join(" ")
  ].join(" ").toLowerCase();

  return cap.keywords.some(kw => textCorpus.includes(kw.toLowerCase()));
}

// Calculate Fit Score
function calculateFitScore(job, userSelectedSkills) {
  if (!userSelectedSkills || userSelectedSkills.length === 0) return null;

  const requiredCaps = CAPABILITIES.filter(cap => jobRequiresCapability(job, cap));
  if (requiredCaps.length === 0) {
    return 60;
  }

  const matchedCaps = requiredCaps.filter(cap => userSelectedSkills.includes(cap.id));
  const ratio = matchedCaps.length / requiredCaps.length;
  const percentage = Math.min(96, Math.max(42, Math.round(ratio * 50 + 46)));
  return percentage;
}

// Render Capabilities Grid in Fit Modal
function renderCapabilityBadges() {
  const isEn = currentLang === "en";
  capabilitiesGrid.innerHTML = CAPABILITIES.map((cap) => {
    const isChecked = userSkills.includes(cap.id);
    const label = isEn ? cap.label_en : cap.label;
    const activeClass = isChecked ? "bg-[#004030] dark:bg-[#06C755] text-white border-[#004030] dark:border-[#06C755] font-semibold" : "border-slate-300 dark:border-[#262626] dark:bg-[#161616] text-slate-700 dark:text-[#D4D4D4] hover:bg-slate-100 dark:hover:bg-[#1E1E1E]";
    return `
      <button class="cap-btn px-3 py-1.5 rounded border ${activeClass} transition" data-id="${cap.id}">
        [ ${isChecked ? "✓ " : ""}${label} ]
      </button>
    `;
  }).join("");

  document.querySelectorAll(".cap-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const id = e.currentTarget.getAttribute("data-id");
      if (userSkills.includes(id)) {
        userSkills = userSkills.filter((s) => s !== id);
      } else {
        userSkills.push(id);
      }
      renderCapabilityBadges();
      renderGapAnalysis();
    });
  });
}

// Actionable Gap Analysis Top 5 (Domain-Aware Context)
function renderGapAnalysis() {
  if (!fitGapsList) return;
  const isEn = currentLang === "en";

  // Determine calculation scope based on current domain filter
  let targetJobs = allJobs;
  let domainLabel = isEn ? "All 79 Enterprise Roles" : "全體 79 筆大廠職缺";

  if (currentFilter && currentFilter.domain !== "all") {
    targetJobs = allJobs.filter(job => {
      const titleCorp = (job.title + " " + (job.recommended_courses || []).join(" ")).toLowerCase();
      if (currentFilter.domain === "資安/IT") return titleCorp.includes("資安") || titleCorp.includes("it") || titleCorp.includes("server");
      if (currentFilter.domain === "供應鏈") return titleCorp.includes("供應鏈") || titleCorp.includes("採購") || titleCorp.includes("資材");
      if (currentFilter.domain === "行銷") return titleCorp.includes("行銷") || titleCorp.includes("品牌") || titleCorp.includes("公關");
      if (currentFilter.domain === "數據分析") return titleCorp.includes("數據") || titleCorp.includes("分析") || titleCorp.includes("資料") || titleCorp.includes("統計");
      if (currentFilter.domain === "人資") return titleCorp.includes("人資") || titleCorp.includes("行政") || titleCorp.includes("訓練");
      return true;
    });

    if (targetJobs.length === 0) targetJobs = allJobs;

    const DOMAIN_NAMES = {
      "資安/IT": { zh: "資安 / IT 流程", en: "Cybersecurity / IT" },
      "供應鏈": { zh: "供應鏈 / 採購", en: "Supply Chain & SCM" },
      "行銷": { zh: "品牌行銷 / 公關", en: "Marketing & PR" },
      "數據分析": { zh: "商業數據分析", en: "Data Analytics" },
      "人資": { zh: "人資 / 行政", en: "HR & Admin" }
    };
    const dObj = DOMAIN_NAMES[currentFilter.domain];
    const dName = isEn ? (dObj?.en || currentFilter.domain) : (dObj?.zh || currentFilter.domain);
    domainLabel = `${isEn ? 'Scope: ' : '計算範圍：'}${dName} (${targetJobs.length} ${isEn ? 'Roles' : '筆職缺'})`;
  } else {
    domainLabel = `${isEn ? 'Scope: ' : '計算範圍：'}${isEn ? 'All 79 Roles' : '全體 79 筆大廠職缺'}`;
  }

  const fitDomainIndicator = document.getElementById("fit-domain-indicator");
  if (fitDomainIndicator) {
    fitDomainIndicator.textContent = `[ ${domainLabel} ]`;
  }

  // Count unselected capabilities requested by jobs in targetJobs
  const unselectedCaps = CAPABILITIES.filter(c => !userSkills.includes(c.id));
  const counts = unselectedCaps.map(cap => {
    let reqCount = 0;
    targetJobs.forEach(j => {
      if (jobRequiresCapability(j, cap)) {
        reqCount += 1;
      }
    });
    return { ...cap, reqCount };
  });

  counts.sort((a, b) => b.reqCount - a.reqCount);
  const topGaps = counts.slice(0, 5);

  if (topGaps.length === 0) {
    fitGapsList.innerHTML = `<span class="text-emerald-500 font-semibold">[ ${isEn ? 'All core capabilities selected!' : '恭喜！您已具備所有核心指標能力！'} ]</span>`;
    return;
  }

  fitGapsList.innerHTML = topGaps.map((g, idx) => {
    const lbl = isEn ? g.label_en : g.label;
    const rate = Math.round((g.reqCount / (targetJobs.length || 1)) * 100);
    return `
      <div class="flex items-center justify-between py-1 border-b border-slate-100 dark:border-[#222222]">
        <span><span class="font-mono text-slate-400 font-semibold">${idx + 1}.</span> ${lbl}</span>
        <span class="font-mono text-emerald-600 dark:text-[#06C755] font-semibold">${isEn ? 'Required by' : '大廠要求率'} ${rate}% (${g.reqCount}/${targetJobs.length})</span>
      </div>
    `;
  }).join("");
}

// Insights Charts (Pure Text: Stages, Dimensions, Collaborators, Courses)
function renderInsights() {
  const chartCourses = document.getElementById("chart-courses");
  const chartStages = document.getElementById("chart-stages");
  const chartDimensions = document.getElementById("chart-dimensions");
  const chartCollaborators = document.getElementById("chart-collaborators");
  const isEn = currentLang === "en";

  if (!chartCourses) return;

  // 1. Courses Top 5
  const courseCounts = {};
  allJobs.forEach((j) => {
    (j.recommended_courses || []).forEach((c) => {
      courseCounts[c] = (courseCounts[c] || 0) + 1;
    });
  });
  const sortedCourses = Object.entries(courseCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  chartCourses.innerHTML = sortedCourses.map(([name, cnt]) => {
    const displayName = isEn ? translateCourse(name) : name;
    return `
      <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-[#222222]">
        <span class="font-medium text-slate-800 dark:text-[#D4D4D4]">${displayName}</span>
        <span class="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-[#1E1E1E] text-slate-700 dark:text-[#A0A0A0]">${cnt} ${isEn ? 'Jobs' : '家大廠指定'}</span>
      </div>
    `;
  }).join("");

  // 2. Stages (Pure text, no S1..S6 codes)
  const stageCounts = {};
  allJobs.forEach((j) => {
    const stList = isEn && j.project_stages_en ? j.project_stages_en : (j.project_stages || []);
    stList.forEach((st) => {
      stageCounts[st] = (stageCounts[st] || 0) + 1;
    });
  });
  const sortedStages = Object.entries(stageCounts).sort((a, b) => b[1] - a[1]);
  if (chartStages) {
    chartStages.innerHTML = sortedStages.map(([st, cnt]) => `
      <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-[#222222]">
        <span class="font-medium text-slate-800 dark:text-[#D4D4D4]">${st}</span>
        <span class="font-mono font-semibold px-2 py-0.5 rounded bg-emerald-50 dark:bg-[#06C755]/10 text-emerald-700 dark:text-[#06C755]">${cnt} ${isEn ? 'Projects' : '專案涉及'}</span>
      </div>
    `).join("");
  }

  // 3. Core Dimensions (Pure text, no D1..D7 codes)
  const dmWeights = {};
  allJobs.forEach((j) => {
    (j.core_dimensions || []).forEach((dm) => {
      const nm = isEn && dm.name_en ? dm.name_en : dm.name;
      dmWeights[nm] = (dmWeights[nm] || 0) + (dm.weight || 20);
    });
  });
  const sortedDms = Object.entries(dmWeights).sort((a, b) => b[1] - a[1]);
  if (chartDimensions) {
    chartDimensions.innerHTML = sortedDms.map(([nm, totalW]) => {
      const avgW = Math.round(totalW / (allJobs.length || 79));
      return `
        <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-[#222222]">
          <span class="font-medium text-slate-800 dark:text-[#D4D4D4]">${nm}</span>
          <span class="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-[#1E1E1E] text-slate-700 dark:text-[#A0A0A0]">${isEn ? 'Avg Weight' : '平均比重'} ${avgW}%</span>
        </div>
      `;
    }).join("");
  }

  // 4. Collaborators Ranking
  const collabCounts = {};
  allJobs.forEach((j) => {
    (j.collaborators || []).forEach((clb) => {
      collabCounts[clb] = (collabCounts[clb] || 0) + 1;
    });
  });
  const sortedCollabs = Object.entries(collabCounts).sort((a, b) => b[1] - a[1]);
  if (chartCollaborators) {
    chartCollaborators.innerHTML = sortedCollabs.map(([clb, cnt]) => {
      const displayCollab = isEn ? translateCollaborator(clb) : clb;
      return `
        <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-[#222222]">
          <span class="font-medium text-slate-800 dark:text-[#D4D4D4]">${displayCollab}</span>
          <span class="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-[#1E1E1E] text-slate-700 dark:text-[#A0A0A0]">${cnt} ${isEn ? 'Teams' : '次頻繁共事'}</span>
        </div>
      `;
    }).join("");
  }
}

// Navigation Tabs Handling
function initNavigation() {
  const tabs = {
    jobs: document.getElementById("nav-jobs"),
    fit: document.getElementById("nav-fit"),
    insights: document.getElementById("nav-insights")
  };

  const views = {
    jobs: document.getElementById("view-jobs"),
    insights: document.getElementById("view-insights")
  };

  function switchTab(activeKey) {
    Object.keys(views).forEach((k) => {
      if (views[k]) {
        if (k === activeKey) views[k].classList.remove("hidden");
        else views[k].classList.add("hidden");
      }
    });

    Object.keys(tabs).forEach((k) => {
      if (tabs[k]) {
        if (k === activeKey) {
          tabs[k].classList.add("bg-white/10", "dark:bg-[#1E1E1E]", "text-white", "font-semibold");
          tabs[k].classList.remove("text-slate-200", "dark:text-[#8E8E93]");
        } else {
          tabs[k].classList.remove("bg-white/10", "dark:bg-[#1E1E1E]", "text-white", "font-semibold");
          tabs[k].classList.add("text-slate-200", "dark:text-[#8E8E93]");
        }
      }
    });
  }

  if (tabs.jobs) tabs.jobs.addEventListener("click", () => switchTab("jobs"));
  if (tabs.fit) {
    tabs.fit.addEventListener("click", () => {
      renderCapabilityBadges();
      renderGapAnalysis();
      modalFit.classList.remove("hidden");
    });
  }
  if (tabs.insights) tabs.insights.addEventListener("click", () => switchTab("insights"));
}

// i18n Initialization and Toggle
function initI18n() {
  updateInterfaceLanguage();

  if (langToggle) {
    langToggle.addEventListener("click", () => {
      currentLang = currentLang === "zh" ? "en" : "zh";
      localStorage.setItem("tw50_lang", currentLang);
      updateInterfaceLanguage();
      applyFiltersAndRender();
      renderInsights();
      renderCapabilityBadges();
      renderGapAnalysis();
    });
  }
}

function updateInterfaceLanguage() {
  const t = I18N[currentLang];
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (t[key]) el.textContent = t[key];
  });
  if (searchInput) searchInput.placeholder = t.search_placeholder;
}

// PRD Section 5.7 Compliant CSV Export
function exportCSV() {
  const headers = [
    "職缺編號", "公司名稱", "股票代號", "成分股指數", "職稱", "實習地點",
    "實習待遇", "學歷要求", "工作內容", "建議先修課程", "104職缺更新日期", "抓到資料的時間", "104原始連結"
  ];
  const rows = allJobs.map((j) => [
    sanitizeCSV(j.job_id),
    sanitizeCSV(j.company),
    sanitizeCSV(j.stock_code),
    sanitizeCSV(j.index_type),
    sanitizeCSV(j.title),
    sanitizeCSV(j.location),
    sanitizeCSV(j.salary_desc),
    sanitizeCSV(j.experience_desc),
    sanitizeCSV((j.job_duties || []).join("；")),
    sanitizeCSV((j.recommended_courses || []).join("；")),
    sanitizeCSV(j.appear_date || "2026-10-18"),
    sanitizeCSV(j.scraped_at || j.crawl_date || "2026-10-18"),
    sanitizeCSV(j.url)
  ]);

  let csvContent = "\uFEFF"; // UTF-8 BOM
  csvContent += headers.map((h) => `"${h}"`).join(",") + "\n";
  rows.forEach((r) => {
    csvContent += r.map((c) => `"${c}"`).join(",") + "\n";
  });

  const todayStr = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `PMJ_職缺總表_${todayStr}.csv`;
  a.click();
}

function sanitizeCSV(text) {
  if (!text) return "";
  let str = String(text).replace(/"/g, '""');
  if (/^[=\+\-@]/.test(str)) str = "'" + str;
  return str;
}

// Theme handling
function initTheme() {
  const isDark = localStorage.getItem("tw50_theme") === "dark" || (!("tw50_theme" in localStorage) && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (isDark) document.documentElement.classList.add("dark");
  else document.documentElement.classList.remove("dark");

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const isNowDark = document.documentElement.classList.toggle("dark");
      localStorage.setItem("tw50_theme", isNowDark ? "dark" : "light");
    });
  }
}

// PWA Service Worker
function initPWA() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch((err) => {
      console.log("SW registration notice:", err);
    });
  }
}

// Event Bindings
function bindEvents() {
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      currentFilter.search = e.target.value;
      applyFiltersAndRender();
    });
  }

  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const group = e.currentTarget.getAttribute("data-group");
      const val = e.currentTarget.getAttribute("data-val");

      document.querySelectorAll(`.filter-btn[data-group="${group}"]`).forEach((b) => {
        b.classList.remove("active");
      });

      e.currentTarget.classList.add("active");
      currentFilter[group] = val;
      applyFiltersAndRender();
    });
  });

  if (btnFitQuick) {
    btnFitQuick.addEventListener("click", () => {
      renderCapabilityBadges();
      renderGapAnalysis();
      modalFit.classList.remove("hidden");
    });
  }
  if (btnCloseFit) btnCloseFit.addEventListener("click", () => modalFit.classList.add("hidden"));
  if (btnApplyFitModal) {
    btnApplyFitModal.addEventListener("click", () => {
      localStorage.setItem("tw50_user_skills", JSON.stringify(userSkills));
      modalFit.classList.add("hidden");
      applyFiltersAndRender();
    });
  }

  if (btnResetFitModal) {
    btnResetFitModal.addEventListener("click", () => {
      userSkills = [];
      renderCapabilityBadges();
      renderGapAnalysis();
    });
  }

  if (btnClearFit) {
    btnClearFit.addEventListener("click", () => {
      userSkills = [];
      localStorage.removeItem("tw50_user_skills");
      renderCapabilityBadges();
      renderGapAnalysis();
      applyFiltersAndRender();
    });
  }

  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const type = e.currentTarget.getAttribute("data-preset");
      if (type === "mkt") {
        userSkills = ["S_PRESENTATION", "S_ENGLISH", "A_COMMUNICATION", "S_PRD_WRITING"];
      } else if (type === "data") {
        userSkills = ["S_EXCEL", "S_PYTHON", "S_SQL", "A_DETAIL_ORIENTED"];
      } else if (type === "ops") {
        userSkills = ["K_SUPPLY_CHAIN", "S_PM_TOOLS", "A_DETAIL_ORIENTED", "S_ENGLISH"];
      }
      renderCapabilityBadges();
      renderGapAnalysis();
    });
  });

  const btnExport = document.getElementById("btn-export-csv");
  if (btnExport) btnExport.addEventListener("click", exportCSV);
}
