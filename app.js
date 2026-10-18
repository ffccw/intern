/**
 * 台灣 50 / 中型 100 管院實習雷達 Frontend Application
 * Fully zero-emoji, clean typography, responsive PWA.
 */

// State
let allJobs = [];
let currentFilter = {
  search: "",
  index: "all",
  domain: "all",
  degree: "all",
  english: "all"
};

// 10 Core Capability Badges for Quick Self-Assessment
const CAPABILITIES = [
  { id: "S_ENGLISH", label: "商務英文溝通 (TOEIC 750+)", domain: "D6" },
  { id: "S_EXCEL", label: "Excel 樞紐分析與函數", domain: "D5" },
  { id: "S_PRESENTATION", label: "商業簡報與提案表達", domain: "D1" },
  { id: "S_PYTHON", label: "Python 程式與基礎數據", domain: "D4" },
  { id: "S_SQL", label: "SQL 資料庫查詢", domain: "D4" },
  { id: "S_PM_TOOLS", label: "專案看板管理 (Jira/Trello/Notion)", domain: "D4" },
  { id: "S_PRD_WRITING", label: "規格需求書 (PRD) 與企劃撰寫", domain: "D3" },
  { id: "K_SUPPLY_CHAIN", label: "供應鏈與採購基礎概念", domain: "D7" },
  { id: "A_DETAIL_ORIENTED", label: "嚴謹細心 (偏內向數據型優勢)", domain: "D6" },
  { id: "A_COMMUNICATION", label: "熱情外向 (偏公開社交與表達)", domain: "D6" }
];

let userSkills = JSON.parse(localStorage.getItem("tw50_user_skills") || "[]");

// DOM Elements
const jobsContainer = document.getElementById("jobs-container");
const searchInput = document.getElementById("search-input");
const resultsCount = document.getElementById("results-count");
const themeToggle = document.getElementById("theme-toggle");
const modalFit = document.getElementById("modal-fit");
const btnFitQuick = document.getElementById("btn-fit-quick");
const btnCloseFit = document.getElementById("btn-close-fit");
const btnResetFitModal = document.getElementById("btn-reset-fit-modal");
const btnApplyFitModal = document.getElementById("btn-apply-fit-modal");
const fitSummaryBanner = document.getElementById("fit-summary-banner");
const btnClearFit = document.getElementById("btn-clear-fit");
const capabilitiesGrid = document.getElementById("capabilities-grid");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initNavigation();
  initPWA();
  renderCapabilityBadges();
  await loadJobData();
  bindEvents();
});

const GOOGLE_SHEET_ID = "1wv5PEYIZk7S-bJP1M7S1XPKvXCXAwEqtBFPcFNmZMDI";

// Load Job Data (Priority: Verified local data.json -> Fallback: Live Google Sheet)
async function loadJobData() {
  try {
    // 1. First load verified local data.json (contains rich direct job & Dcard links)
    try {
      const res = await fetch("data/data.json");
      if (res.ok) {
        const json = await res.json();
        if (json.jobs && json.jobs.length > 0) {
          allJobs = json.jobs;
          console.log(`[Data] Successfully loaded ${allJobs.length} verified jobs from data.json!`);
        }
      }
    } catch (localErr) {
      console.warn("[Data] Local data.json failed, falling back to Google Sheets:", localErr);
    }

    // 2. Fallback to Google Sheets if local data.json not loaded
    if (allJobs.length === 0 && GOOGLE_SHEET_ID) {
      try {
        const sheetCsvUrl = `https://docs.google.com/spreadsheets/d/${GOOGLE_SHEET_ID}/export?format=csv`;
        const sheetRes = await fetch(sheetCsvUrl);
        if (sheetRes.ok) {
          const csvText = await sheetRes.text();
          allJobs = parseGoogleSheetCsv(csvText) || [];
          console.log(`[Cloud DB] Synced ${allJobs.length} jobs from Google Sheets fallback.`);
        }
      } catch (sheetErr) {
        console.warn("[Cloud DB] Google Sheet read failed:", sheetErr);
      }
    }

    applyFiltersAndRender();
    renderInsights();
  } catch (err) {
    console.error("Failed to load jobs data:", err);
    jobsContainer.innerHTML = `<div class="p-8 text-center text-red-500">無法讀取職缺資料，請確認 data/data.json 是否存在。</div>`;
  }
}

// Simple robust CSV parser for Google Sheet export
function parseGoogleSheetCsv(text) {
  if (!text || text.trim().length === 0) return [];
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];

  // Parse header
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
      stock_code: row["股票代號"] || "",
      index_type: row["成分股指數"] || "台灣 50",
      title: row["職缺名稱"] || "",
      location: row["實習地點"] || "",
      salary_desc: row["實習待遇"] || "時薪制",
      experience_desc: row["條件要求"] || "在學學生",
      job_duties: duties.length > 0 ? duties : ["負責專案進度與時程協調", "跨部門溝通與主管回報"],
      recommended_courses: courses.length > 0 ? courses : ["專案管理概論", "商務英文"],
      trait_advice: row["特質建議"] || "適合細心、有責任感並渴望實習經驗的同學。",
      url: row["104原始連結"] || "https://www.104.com.tw/jobs/search/?keyword=" + encodeURIComponent(row["公司名稱"] || ""),
      status: row["狀態"] || "open",
      discussion_links: {
        dcard_label: (row["Dcard避雷連結"] && row["Dcard避雷連結"].trim() !== "" && row["Dcard避雷連結"] !== "null") ? `Dcard 實習心得 ↗` : null,
        dcard_url: (row["Dcard避雷連結"] && row["Dcard避雷連結"].trim() !== "" && row["Dcard避雷連結"] !== "null") ? row["Dcard避雷連結"].trim() : null,
        ptt_url: (row["PTT評價連結"] && row["PTT評價連結"].trim() !== "" && row["PTT評價連結"] !== "null") ? row["PTT評價連結"].trim() : null
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

  let filtered = allJobs.filter((job) => {
    // Search query
    if (query) {
      const matchText = (
        job.company +
        " " +
        job.title +
        " " +
        (job.recommended_courses || []).join(" ") +
        " " +
        (job.job_duties || []).join(" ")
      ).toLowerCase();
      if (!matchText.includes(query)) return false;
    }

    // Index
    if (currentFilter.index !== "all" && job.index_type !== currentFilter.index) {
      return false;
    }

    // Domain
    if (currentFilter.domain !== "all") {
      const titleCorp = job.title + " " + (job.recommended_courses || []).join(" ");
      if (currentFilter.domain === "資安/IT" && !titleCorp.includes("資安") && !titleCorp.includes("IT")) return false;
      if (currentFilter.domain === "供應鏈" && !titleCorp.includes("供應鏈") && !titleCorp.includes("採購") && !titleCorp.includes("資材")) return false;
      if (currentFilter.domain === "行銷" && !titleCorp.includes("行銷") && !titleCorp.includes("品牌") && !titleCorp.includes("公關")) return false;
      if (currentFilter.domain === "數據分析" && !titleCorp.includes("數據") && !titleCorp.includes("分析")) return false;
      if (currentFilter.domain === "人資" && !titleCorp.includes("人資") && !titleCorp.includes("行政")) return false;
    }

    // Degree
    if (currentFilter.degree !== "all") {
      const reqLvl = job.education_req?.level || "none";
      if (currentFilter.degree === "ma" && reqLvl !== "ma") return false;
    }

    // English
    if (currentFilter.english !== "all") {
      const engContext = (job.context?.english_level || "") + " " + job.title + " " + (job.recommended_courses || []).join(" ");
      if (currentFilter.english === "fluent" && !engContext.includes("流利") && !engContext.includes("primary")) return false;
    }

    return true;
  });

  // Calculate Match Score if User has Evaluated
  if (userSkills.length > 0) {
    filtered.forEach((job) => {
      job.fitScore = calculateFitScore(job, userSkills);
    });
    // Sort by fit score descending
    filtered.sort((a, b) => (b.fitScore || 0) - (a.fitScore || 0));
    fitSummaryBanner.classList.remove("hidden");
  } else {
    filtered.forEach((job) => (job.fitScore = null));
    fitSummaryBanner.classList.add("hidden");
  }

  resultsCount.textContent = `共符合 ${filtered.length} 筆頂尖實習職缺`;

  if (filtered.length === 0) {
    jobsContainer.innerHTML = `
      <div class="bg-white dark:bg-slate-800 p-12 text-center rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500">
        查無符合條件之大廠實習。建議放寬篩選條件或清除搜尋關鍵字。
      </div>
    `;
    return;
  }

  jobsContainer.innerHTML = filtered.map((job) => renderJobCard(job)).join("");

  // Attach click listener to recommended courses badges for instant filtering
  document.querySelectorAll(".course-badge").forEach((el) => {
    el.addEventListener("click", (e) => {
      const crsName = e.currentTarget.getAttribute("data-course");
      searchInput.value = crsName;
      currentFilter.search = crsName;
      applyFiltersAndRender();
    });
  });
}

// Card HTML Template (Zero Emoji, Clean Borders)
function renderJobCard(job) {
  const indexBadgeClass =
    job.index_type === "台灣 50"
      ? "bg-[#D8C3A5] text-[#004030] font-bold"
      : "bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200";

  // Fit score badge if calculated
  let fitBadgeHtml = "";
  if (job.fitScore !== null) {
    let fitColor = "border-slate-400 text-slate-600";
    if (job.fitScore >= 70) fitColor = "bg-[#004030] text-white font-bold border-[#004030]";
    else if (job.fitScore >= 50) fitColor = "bg-[#D8C3A5] text-[#004030] font-bold border-[#D8C3A5]";
    fitBadgeHtml = `<span class="px-2 py-0.5 text-xs rounded border ${fitColor}">契合度 ${job.fitScore}%</span>`;
  }

  const dutiesHtml = (job.job_duties || [])
    .map((d, i) => `<li class="flex items-start space-x-2"><span class="font-mono text-slate-400 font-semibold">${i + 1}.</span><span>${d}</span></li>`)
    .join("");

  const coursesHtml = (job.recommended_courses || [])
    .map(
      (c) =>
        `<button class="course-badge px-2 py-0.5 rounded border border-slate-300 dark:border-slate-600 hover:border-[#004030] dark:hover:border-[#D8C3A5] text-slate-700 dark:text-slate-300 transition text-[11px]" data-course="${c}" title="點擊過濾修過這門課的職缺">[ ${c} ]</button>`
    )
    .join(" ");

  return `
    <article class="job-card bg-white dark:bg-slate-800 rounded-lg p-5 border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow transition space-y-4">
      
      <!-- Top Header -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-slate-700">
        <div>
          <div class="flex items-center space-x-2 text-xs">
            <span class="font-bold text-slate-900 dark:text-slate-100">${job.company}</span>
            <span class="text-slate-400 font-mono">(${job.stock_code})</span>
            <span class="px-2 py-0.5 rounded text-[11px] ${indexBadgeClass}">[ ${job.index_type} ]</span>
          </div>
          <h3 class="text-base font-bold font-serif text-slate-900 dark:text-slate-100 mt-1">${job.title}</h3>
        </div>
        <div class="flex items-center space-x-2 shrink-0">
          ${fitBadgeHtml}
        </div>
      </div>

      <!-- Essential Specs Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/50 p-3 rounded">
        <div><span class="font-semibold text-slate-400">地點：</span>${job.location}</div>
        <div><span class="font-semibold text-slate-400">待遇：</span><span class="font-semibold text-slate-900 dark:text-slate-100">${job.salary_desc}</span></div>
        <div><span class="font-semibold text-slate-400">條件：</span>${job.experience_desc}</div>
      </div>

      <!-- Real Job Duties -->
      <div class="space-y-1 text-xs">
        <span class="font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider text-[11px]">實際工作職責：</span>
        <ul class="space-y-1 text-slate-700 dark:text-slate-200 pl-1">
          ${dutiesHtml}
        </ul>
      </div>

      <!-- Recommended University Courses -->
      <div class="space-y-1 text-xs pt-1">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider text-[11px]">建議先修大學課程（點擊可快速過濾）：</span>
        </div>
        <div class="flex flex-wrap gap-1.5 pt-0.5">
          ${coursesHtml}
        </div>
      </div>

      <!-- Trait Insights -->
      <div class="text-xs p-2.5 rounded bg-slate-100/70 dark:bg-slate-700/40 text-slate-700 dark:text-slate-300 border-l-2 border-[#004030] dark:border-[#D8C3A5]">
        <span class="font-semibold">特質提醒：</span>${job.trait_advice}
      </div>

      <!-- Actions and Discussion Links ("沒有就隱藏") -->
      <div class="pt-2 border-t border-slate-100 dark:border-slate-700 flex flex-wrap items-center justify-between gap-2 text-xs">
        ${(() => {
          const isValidUrl = (url) => {
            if (!url || typeof url !== "string") return false;
            const cleaned = url.trim().toLowerCase();
            return (cleaned.startsWith("http://") || cleaned.startsWith("https://")) && !cleaned.includes("null");
          };

          const dUrl = isValidUrl(job.discussion_links?.dcard_url) ? job.discussion_links.dcard_url.trim() : null;
          const pUrl = isValidUrl(job.discussion_links?.ptt_url) ? job.discussion_links.ptt_url.trim() : null;
          const rawLabel = job.discussion_links?.dcard_label;
          const dLabel = (rawLabel && rawLabel !== "null" && rawLabel.trim()) ? rawLabel.trim() : "Dcard 實習心得 ↗";

          const links = [];
          if (dUrl) {
            links.push(`<a href="${dUrl}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded border border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 hover:underline">[ ${dLabel} ]</a>`);
          }
          if (pUrl) {
            links.push(`<a href="${pUrl}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded border border-slate-300 dark:border-slate-600 hover:underline text-slate-600 dark:text-slate-300">[ PTT 評價討論 ↗ ]</a>`);
          }
          if (links.length > 0) {
            return `<div class="flex flex-wrap items-center gap-2"><span class="font-semibold text-slate-400">論壇避雷與風評：</span>${links.join("")}</div>`;
          }
          return "";
        })()}
        <a href="${job.url}" target="_blank" rel="noopener noreferrer" 
           class="px-3 py-1 bg-[#004030] text-white font-medium rounded hover:bg-[#002f23] transition shrink-0 ml-auto">
          [ 前往 104 應徵 ↗ ]
        </a>
      </div>

    </article>
  `;
}

// Calculate Fit Score
function calculateFitScore(job, userSelectedSkills) {
  if (!userSelectedSkills || userSelectedSkills.length === 0) return null;

  const jobSkills = job.ksa_normalized?.skills || [];
  const jobAttributes = job.ksa_normalized?.attributes || [];
  const jobCourses = job.recommended_courses || [];

  let matched = 0;
  let totalCriteria = 4; // Normalized baseline

  userSelectedSkills.forEach((skillId) => {
    if (jobSkills.includes(skillId) || jobAttributes.includes(skillId)) matched += 1;
    if (skillId === "S_ENGLISH" && job.recommended_courses?.includes("商務英文溝通與簡報")) matched += 1;
    if (skillId === "S_PYTHON" && job.recommended_courses?.includes("商管程式設計 / Python")) matched += 1;
    if (skillId === "S_EXCEL" && job.recommended_courses?.includes("統計學與數據分析")) matched += 1;
  });

  const percentage = Math.min(95, Math.max(35, Math.round((matched / totalCriteria) * 50 + 40)));
  return percentage;
}

// Render Capabilities Grid in Fit Modal
function renderCapabilityBadges() {
  capabilitiesGrid.innerHTML = CAPABILITIES.map((cap) => {
    const isChecked = userSkills.includes(cap.id);
    const activeClass = isChecked ? "bg-[#004030] text-white border-[#004030] font-semibold" : "border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700";
    return `
      <button class="cap-btn px-3 py-1.5 rounded border ${activeClass} transition" data-id="${cap.id}">
        [ ${isChecked ? "✓ " : ""}${cap.label} ]
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
    });
  });
}

// Event Bindings
function bindEvents() {
  // Search
  searchInput.addEventListener("input", (e) => {
    currentFilter.search = e.target.value;
    applyFiltersAndRender();
  });

  // Filter Buttons
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const group = e.currentTarget.getAttribute("data-group");
      const val = e.currentTarget.getAttribute("data-val");

      document.querySelectorAll(`.filter-btn[data-group="${group}"]`).forEach((b) => {
        b.classList.remove("active", "bg-[#004030]", "text-white", "border-[#004030]");
        b.classList.add("border-slate-300", "dark:border-slate-600");
      });

      e.currentTarget.classList.add("active", "bg-[#004030]", "text-white", "border-[#004030]");
      e.currentTarget.classList.remove("border-slate-300", "dark:border-slate-600");

      currentFilter[group] = val;
      applyFiltersAndRender();
    });
  });

  // Modal Fit
  btnFitQuick.addEventListener("click", () => modalFit.classList.remove("hidden"));
  btnCloseFit.addEventListener("click", () => modalFit.classList.add("hidden"));
  btnApplyFitModal.addEventListener("click", () => {
    localStorage.setItem("tw50_user_skills", JSON.stringify(userSkills));
    modalFit.classList.add("hidden");
    applyFiltersAndRender();
  });

  btnResetFitModal.addEventListener("click", () => {
    userSkills = [];
    renderCapabilityBadges();
  });

  btnClearFit.addEventListener("click", () => {
    userSkills = [];
    localStorage.removeItem("tw50_user_skills");
    renderCapabilityBadges();
    applyFiltersAndRender();
  });

  // Presets
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
    });
  });

  // CSV Export
  document.getElementById("btn-export-csv").addEventListener("click", exportCSV);
}

// Navigation Tabs
function initNavigation() {
  const tabs = {
    jobs: document.getElementById("nav-jobs"),
    fit: document.getElementById("nav-fit"),
    insights: document.getElementById("nav-insights"),
    about: document.getElementById("nav-about")
  };

  const views = {
    jobs: document.getElementById("view-jobs"),
    insights: document.getElementById("view-insights"),
    about: document.getElementById("view-about")
  };

  function switchTab(activeTab) {
    Object.keys(tabs).forEach((k) => {
      if (k === activeTab) {
        tabs[k].className = "px-3 py-1.5 rounded transition bg-white/10 text-white font-semibold";
      } else {
        tabs[k].className = "px-3 py-1.5 rounded transition text-slate-200 hover:bg-white/5";
      }
    });

    Object.keys(views).forEach((k) => {
      if (k === activeTab) views[k].classList.remove("hidden");
      else views[k].classList.add("hidden");
    });
  }

  tabs.jobs.addEventListener("click", () => switchTab("jobs"));
  tabs.fit.addEventListener("click", () => modalFit.classList.remove("hidden"));
  tabs.insights.addEventListener("click", () => switchTab("insights"));
  tabs.about.addEventListener("click", () => switchTab("about"));
}

// Insights Chart Renderer
function renderInsights() {
  const chartCourses = document.getElementById("chart-courses");
  const chartLocations = document.getElementById("chart-locations");

  // Count courses
  const courseCounts = {};
  const locCounts = {};

  allJobs.forEach((j) => {
    (j.recommended_courses || []).forEach((c) => {
      courseCounts[c] = (courseCounts[c] || 0) + 1;
    });
    const locKey = j.location.split("（")[0].slice(0, 3);
    locCounts[locKey] = (locCounts[locKey] || 0) + 1;
  });

  const sortedCourses = Object.entries(courseCounts).sort((a, b) => b[1] - a[1]);
  const sortedLocs = Object.entries(locCounts).sort((a, b) => b[1] - a[1]);

  chartCourses.innerHTML = sortedCourses
    .map(
      ([name, cnt]) => `
      <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-700">
        <span class="font-medium">${name}</span>
        <span class="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700">${cnt} 家大廠要求</span>
      </div>
    `
    )
    .join("");

  chartLocations.innerHTML = sortedLocs
    .map(
      ([loc, cnt]) => `
      <div class="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-700">
        <span class="font-medium">${loc}地區</span>
        <span class="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700">${cnt} 筆實習</span>
      </div>
    `
    )
    .join("");
}

// Safe CSV Export (with BOM and formula injection protection)
function exportCSV() {
  const headers = ["公司", "股票代號", "成分股", "職稱", "地點", "薪資待遇", "學歷要求", "工作內容", "建議先修課程", "104連結"];
  const rows = allJobs.map((j) => [
    sanitizeCSV(j.company),
    sanitizeCSV(j.stock_code),
    sanitizeCSV(j.index_type),
    sanitizeCSV(j.title),
    sanitizeCSV(j.location),
    sanitizeCSV(j.salary_desc),
    sanitizeCSV(j.experience_desc),
    sanitizeCSV((j.job_duties || []).join("；")),
    sanitizeCSV((j.recommended_courses || []).join("；")),
    sanitizeCSV(j.url)
  ]);

  let csvContent = "\uFEFF"; // UTF-8 BOM
  csvContent += headers.map((h) => `"${h}"`).join(",") + "\n";
  rows.forEach((r) => {
    csvContent += r.map((c) => `"${c}"`).join(",") + "\n";
  });

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `TW50_管院頂尖實習清單_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}

function sanitizeCSV(text) {
  if (!text) return "";
  let str = String(text).replace(/"/g, '""');
  if (/^[=\+\-@]/.test(str)) str = "'" + str; // Prevent formula injection
  return str;
}

// Theme handling
function initTheme() {
  const isDark = localStorage.getItem("tw50_theme") === "dark" || (!("tw50_theme" in localStorage) && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (isDark) document.documentElement.classList.add("dark");
  else document.documentElement.classList.remove("dark");

  themeToggle.addEventListener("click", () => {
    const isNowDark = document.documentElement.classList.toggle("dark");
    localStorage.setItem("tw50_theme", isNowDark ? "dark" : "light");
  });
}

// PWA Service Worker
function initPWA() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch((err) => {
      console.log("SW registration failed (expected in local preview):", err);
    });
  }
}
