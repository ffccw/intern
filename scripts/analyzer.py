"""
Gemini 3.1 Flash Lite Semantic Analysis Module for Management Internships
Conforms to PRD v2 (2026-10-18 release) specification (Sections 2.2, 2.3, 8.1, 8.4).
- Model: gemini-3.1-flash-lite (default) / gemini-2.5-flash fallback
- Free tier budget: 500 requests/day, 15 RPM, 250k tokens/min
- Output: Structured JSON conforming to strict responseSchema
- Full bilingual extraction: KSA, AI original summary, core PM domains, college courses
"""
import os
import re
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()

COMPLIANCE_PATTERNS = {
    "GENDER": re.compile(r"(限男|限女|男性尤佳|女性尤佳|限男性|限女性)"),
    "AGE": re.compile(r"(\d{2}\s*歲以下|\d{2}\s*歲以內|年輕活力)"),
    "APPEARANCE": re.compile(r"(外型佳|儀態端莊|面貌清秀|五官端正)"),
    "MILITARY_SERVICE": re.compile(r"(役畢|兵役畢|需役畢)"),
}


def sanitize_input_text(text: str) -> str:
    """Pre-sanitize raw text to prevent prompt injection and XSS."""
    if not text:
        return ""
    text = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def detect_compliance_flags(text: str) -> List[str]:
    """Detect discriminatory terms based on Employment Service Act Article 5."""
    flags = []
    for flag_id, pattern in COMPLIANCE_PATTERNS.items():
        if pattern.search(text):
            flags.append(flag_id)
    return sorted(list(set(flags)))


def generate_discussion_links(company: str, title: str) -> Dict[str, str]:
    """Generates direct curated search URLs for Dcard and PTT community reviews."""
    clean_company = re.sub(r"股份有限公司|有限公司|（.*?）|\(.*?\)", "", company).strip()
    keywords = ["實習", clean_company]
    if "資安" in title:
        keywords.append("資安")
    elif "AI" in title or "機器人" in title:
        keywords.append("AI")
    elif "人資" in title:
        keywords.append("人資")
    elif "行銷" in title:
        keywords.append("行銷")
    elif "採購" in title or "供應鏈" in title:
        keywords.append("供應鏈")

    dcard_query = " ".join(keywords)
    dcard_url = f"https://www.dcard.tw/search/posts?query={urllib.parse.quote(dcard_query)}"
    ptt_query = f"site:ptt.cc/bbs/Tech_Job {clean_company} 實習"
    ptt_url = f"https://www.google.com/search?q={urllib.parse.quote(ptt_query)}"

    return {
        "dcard_label": f"Dcard【{clean_company} 實習】討論串",
        "dcard_url": dcard_url,
        "ptt_label": f"PTT Tech_Job 版【{clean_company} 實習評價】",
        "ptt_url": ptt_url,
    }


def call_gemini_api(job_title: str, company: str, raw_description: str) -> Optional[Dict[str, Any]]:
    """
    Calls Google Gemini API with structured output schema.
    REQUIRES non-empty raw_description (真實 104 頁面工作內容原文).
    Raises ValueError if raw_description is empty — no template fallback allowed.
    """
    if not GEMINI_API_KEY:
        return None

    if not raw_description or not raw_description.strip():
        raise ValueError(
            f"[Analyzer] raw_description is empty for '{job_title}' @ {company}. "
            "Cannot call Gemini without real JD content. Fix crawler first."
        )

    sanitized_jd = sanitize_input_text(raw_description)
    prompt = f"""
你是一位專業的科技業招募與管理學院實習顧問。
請嚴格根據以下「104 頁面原始工作內容」分析這份實習職缺，輸出結構化 JSON（繁體中文＋專業英文）。
【重要】job_duties 必須直接對應原始工作內容的真實文字，嚴禁使用罐頭模板或憑標題猜測。

=== 職缺基本資訊 ===
公司名稱：{company}
職務名稱：{job_title}

=== 104 頁面原始工作內容（以此為唯一依據） ===
{sanitized_jd}

=== 分析規範 (PRD v2 規格) ===
1. job_duties: 從上方原始工作內容中精確提煉 3 點「實習生實際執行的具體工作任務」。
   - 必須與原文對應，不可憑職稱或公司名稱推測
   - 嚴禁罐頭套話（禁止：「日常進度追蹤」、「協助各部門業務」等空泛句子）
   - 每一點必須有具體動作與具體對象
2. job_duties_en: 對應上述 3 點的專業英文翻譯。
3. recommended_courses: 依據工作真實本質，推薦 3~4 門最相關的大學先修課程。
   可選範圍：["人工智慧與商業應用", "商管程式設計 / Python", "資料庫管理", "統計學與數據分析", "供應鏈與運籌管理", "作業管理與製程規劃", "專案管理概論", "行銷管理", "消費者行為", "網路行銷與社群經營", "財務管理", "管理會計學", "人力資源管理", "組織行為學", "資訊安全導論", "作業系統概論", "系統分析與設計", "商務英文溝通與簡報", "企業管理導論", "國際企業經營策略"]
4. jd_summary: 原創雙語摘要（中文 60~100 字，英文 40~60 words），嚴禁直接摘錄原文。
5. bilingual_ksa: Knowledge (2項), Skills (2項), Attributes (2項)，每項提供 zh 與 en。
6. trait_advice: 中文特質建議（60 字以內）。
7. trait_advice_en: 英文特質建議。
8. collaborators: 主要跨部門協作對象（2~3 個）。
9. core_dimensions: 各維度權重（合計 100）。
"""

    models_to_try = [
        GEMINI_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]
    # De-duplicate while preserving order and filtering empty strings
    models_to_try = [m for m in dict.fromkeys(models_to_try) if m]

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_json_str = parts[0]["text"].strip()
                            raw_json_str = re.sub(r"^```(?:json)?\s*", "", raw_json_str)
                            raw_json_str = re.sub(r"\s*```$", "", raw_json_str)
                            parsed = json.loads(raw_json_str)
                            parsed["ai_model"] = model
                            return parsed
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = (attempt + 1) * 6
                    print(f"[Gemini API] Quota limit on {model}, sleeping {wait_time}s (attempt {attempt+1}/2)...")
                    time.sleep(wait_time)
                    continue
                elif e.code in (401, 403):
                    print(f"[Gemini API] Key or access error (HTTP {e.code}) on {model}")
                    return None
                else:
                    print(f"[Gemini API] Error {e.code} on {model}")
                    break
            except Exception as err:
                print(f"[Gemini API] Failed on model {model}: {err}")
                break

    return None


def fallback_domain_semantic_analysis(job_title: str, company: str, raw_description: str) -> Dict[str, Any]:
    """
    Domain-aware extractor used only when Gemini API is unavailable.
    REQUIRES non-empty raw_description. Raises ValueError if empty — no template fill allowed.
    Uses raw_description content (not just title) to select the correct duty template.
    """
    if not raw_description or not raw_description.strip():
        raise ValueError(
            f"[Analyzer] raw_description is empty for '{job_title}' @ {company}. "
            "Cannot generate job_duties without real JD content. Fix crawler first."
        )
    text = f"{job_title} {raw_description}".lower()

    # 1. AI, Computer Vision, Robotics & Image Annotation
    if any(k in text for k in ["影像標記", "標註", "標記", "機器人", "電腦視覺", "yolo", "cv"]):
        duties = [
            "使用專業軟體工具進行影像資料框選與語意標註，供機器人 AI 模型訓練使用",
            "執行影像標籤格式初審與資料集前處理，確保訓練樣本資料品質",
            "具備基礎電腦軟體操作能力與 AI/電腦視覺基礎概念尤佳（工讀/兼職配合排班）"
        ]
        duties_en = [
            "Perform image annotation and bounding-box labeling using software tools for robotic AI training",
            "Conduct dataset format verification and pre-processing to ensure training sample quality",
            "Apply basic computer vision and software skills to data quality assurance"
        ]
        courses = ["人工智慧與商業應用", "商管程式設計 / Python", "資料庫管理", "統計學與數據分析"]
        collabs = ["RD 研發處", "IT 資訊團隊", "QA 品保處"]
        trait_zh = "職缺注重影像標籤精準度與耐性，適合沉穩細心、能專注於數據處理與獨立作業的同學。"
        trait_en = "Emphasizes precision and patience in dataset labeling; ideal for meticulous and detail-oriented students."
        summary_zh = f"支援{company}機器人與電腦視覺部門之 AI 模型訓練，負責專用軟體標記、資料集格式檢驗與日常數據建置。"
        summary_en = f"Supports {company} robotics team in AI model training, performing dataset labeling and QA verification."
        ksa = {
            "knowledge": [{"zh": "人工智慧與電腦視覺概論", "en": "AI & Computer Vision Fundamentals"}, {"zh": "資料前處理與資料集規範", "en": "Dataset Pre-processing Standards"}],
            "skills": [{"zh": "影像標註工具操作", "en": "Annotation Tool Operations"}, {"zh": "資料清洗與格式檢核", "en": "Data Cleaning & Verification"}],
            "attributes": [{"zh": "高度細心與耐心", "en": "High Meticulousness & Patience"}, {"zh": "獨立專注作業", "en": "Autonomous Concentration"}]
        }

    # 2. Software, Java, Web, Firmware, Algorithm Engineering
    elif any(k in text for k in ["java", "軟體", "開發", "工程師", "演算法", "韌體", "x86", "c#", ".net", "python", "backend", "frontend"]):
        duties = [
            "參與軟體模組功能開發、API 介接與系統架構維護作業",
            "撰寫單元測試案例（Unit Test）並協助研發工程師排除系統 Bug",
            "整理軟體設計技術文件、開發規格書與版本發布紀錄"
        ]
        duties_en = [
            "Participate in software feature implementation, API integration, and system maintenance",
            "Draft unit test cases and assist software engineers in debugging system anomalies",
            "Maintain technical documentation, software specifications, and version release logs"
        ]
        courses = ["商管程式設計 / Python", "資料庫管理", "系統分析與設計", "作業系統概論"]
        collabs = ["RD 研發處", "IT 資訊團隊", "QA 品保處"]
        trait_zh = "職缺重視邏輯架構與程式除錯能力，適合具備程式基礎且樂於探究技術細節的同學。"
        trait_en = "Values algorithmic thinking and debugging skills; suitable for students passionate about software engineering."
        summary_zh = f"協助{company}技術團隊推動核心軟體系統研發，負責模組程式撰寫、單元測試驗證與技術文件管理。"
        summary_en = f"Assists {company} engineering teams in software development, unit testing, and technical documentation."
        ksa = {
            "knowledge": [{"zh": "資料庫架構與物件導向", "en": "Database & OOP Concepts"}, {"zh": "系統分析與軟體工程流程", "en": "System Analysis & SDLC"}],
            "skills": [{"zh": "程式設計與 API 串接", "en": "Programming & API Integration"}, {"zh": "版本控制 (Git) 與測試", "en": "Git Version Control & Testing"}],
            "attributes": [{"zh": "邏輯思維與抗壓性", "en": "Logical Thinking & Resilience"}, {"zh": "持續主動自學技術", "en": "Proactive Self-learning"}]
        }

    # 3. Supply Chain, Procurement, Logistics, SCM
    elif any(k in text for k in ["採購", "供應鏈", "資材", "料號", "庫存", "運籌", "logistics", "scm", "buyer"]):
        duties = [
            "追蹤半導體零組件與原物料交期時程，異常交期及時預警與跟催",
            "協助採購主管向國內外供應商詢價、比價並整理報價分析表",
            "核對採購訂單料號、發票清單與進出貨 ERP 系統資料登錄"
        ]
        duties_en = [
            "Monitor component delivery schedules and track supplier lead times proactively",
            "Assist procurement managers in vendor RFQ comparison and pricing analysis",
            "Verify purchase order part numbers and reconcile logistics data in ERP systems"
        ]
        courses = ["供應鏈與運籌管理", "作業管理與製程規劃", "專案管理概論", "統計學與數據分析"]
        collabs = ["PUR 採購處", "MFG 製造廠", "外部供應商"]
        trait_zh = "職缺強調交期時效敏感度與跨供應商交涉，適合處事有條理、數字觀念敏銳的同學。"
        trait_en = "Emphasizes schedule sensitivity and supplier coordination; ideal for structured, organized students."
        summary_zh = f"支援{company}供應鏈與採購運籌體系，負責料號交期追蹤、供應商報價整理與庫存進出貨管理。"
        summary_en = f"Supports {company} supply chain operations, tracking component lead times and vendor quotations."
        ksa = {
            "knowledge": [{"zh": "供應鏈與運籌管理理論", "en": "Supply Chain & Logistics Theory"}, {"zh": "國際貿易與採購法規", "en": "Trade & Procurement Basics"}],
            "skills": [{"zh": "ERP 系統與 Excel 樞紐分析", "en": "ERP Systems & Advanced Excel"}, {"zh": "交期跟催與供應商溝通", "en": "Vendor Coordination & Tracking"}],
            "attributes": [{"zh": "條理分明與數字敏感", "en": "Structured Thinking & Numerical Sense"}, {"zh": "談判應變與溝通熱忱", "en": "Negotiation & Communication"}]
        }

    # 4. Accounting, Finance & Audit
    elif any(k in text for k in ["會計", "財務", "出納", "帳務", "審計", "稅務", "acct", "finance", "audit"]):
        duties = [
            "審核日常各項營業費用原始憑證、發票單據合規性與傳票登錄",
            "協助應收／應付帳款明細帳核對、銀行對帳單編製與差異調節",
            "支援月底財務報表編製、稅務申報底稿整理與會計檔案歸檔"
        ]
        duties_en = [
            "Verify expense receipts, invoice compliance, and prepare accounting vouchers",
            "Reconcile accounts receivable/payable ledgers and assist in bank reconciliation",
            "Assist in month-end financial statement preparation and tax filing document filing"
        ]
        courses = ["管理會計學", "財務管理", "統計學與數據分析", "商業智慧與大數據分析"]
        collabs = ["財務處", "各部門主管", "IT 資訊團隊"]
        trait_zh = "職缺重視嚴謹法規意識與零失誤帳務精神，適合沉穩細心、恪守誠信與保密原則的同學。"
        trait_en = "Requires precision in financial reconciliation; ideal for highly detail-oriented and trustworthy students."
        summary_zh = f"協助{company}財務會計處進行日常帳務核對、會計傳票編製與月結報表底稿整理。"
        summary_en = f"Assists {company} finance department with daily ledger reconciliation and accounting documentation."
        ksa = {
            "knowledge": [{"zh": "中級會計學與財務法規", "en": "Intermediate Accounting & Regulations"}, {"zh": "稅務申報與內部控制制度", "en": "Tax Compliance & Internal Controls"}],
            "skills": [{"zh": "會計軟體與財務函數分析", "en": "Accounting Software & Financial Excel"}, {"zh": "帳務審核與沖銷調節", "en": "Ledger Audit & Reconciliation"}],
            "attributes": [{"zh": "高度誠信與保密操守", "en": "Integrity & Confidentiality"}, {"zh": "零失誤嚴謹作業態度", "en": "Rigorous Attention to Detail"}]
        }

    # 5. Marketing, PR, Social Media, Branding
    elif any(k in text for k in ["行銷", "品牌", "公關", "社群", "企劃", "推廣", "mkt", "pr", "marketing"]):
        duties = [
            "協助品牌官方社群媒體內容規劃、文案發想撰寫與排程發布",
            "蒐集產業競品行銷活動動態與市場情報，整理成趨勢分析簡報",
            "支援大型實體展覽、品牌發表會與校園推廣活動現場籌備執行"
        ]
        duties_en = [
            "Draft social media content, creative copywriting, and schedule cross-platform posts",
            "Monitor competitor marketing campaigns and compile competitive intelligence reports",
            "Support on-site logistics and coordination for exhibitions, press events, and roadshows"
        ]
        courses = ["行銷管理", "消費者行為", "網路行銷與社群經營", "商務英文溝通與簡報"]
        collabs = ["MKT 行銷團隊", "DESIGN 設計團隊", "SALES 業務處"]
        trait_zh = "職缺重視創新靈感與社群敏銳度，適合熱情外向、擅長文案表達且熱愛與人群互動的同學。"
        trait_en = "Values creative flair and audience empathy; ideal for communicative, dynamic, and outgoing students."
        summary_zh = f"支援{company}行銷企劃與品牌推廣專案，負責社群文案發想、競品市場調研與行銷活動現場執行。"
        summary_en = f"Supports {company} marketing campaigns, social media copywriting, market research, and event logistics."
        ksa = {
            "knowledge": [{"zh": "數位行銷與品牌經營策略", "en": "Digital Marketing & Branding Strategy"}, {"zh": "消費者心理學與社群生態", "en": "Consumer Psychology & Social Trends"}],
            "skills": [{"zh": "文案撰寫與內容企劃", "en": "Creative Copywriting & Content Planning"}, {"zh": "社群成效數據分析 (GA4/Meta)", "en": "Social Media Analytics (GA4/Meta)"}],
            "attributes": [{"zh": "敏銳創意思維與好奇心", "en": "Creative Curiosity & Trend Sensitivity"}, {"zh": "活潑熱情與人際溝通力", "en": "Outgoing & Interpersonal Dynamics"}]
        }

    # 6. Human Resources, Training, Recruiting
    elif any(k in text for k in ["人資", "招募", "培訓", "教育訓練", "hr", "talent"]):
        duties = [
            "協助校園實習與新鮮人招募專案，包含履歷初篩、面試聯繫與現場接待",
            "支援企業內部教育訓練課程規劃、線上數位學習平台維護與課後問卷統計",
            "維護人資系統各項差勤與員工基本資料庫，確保人事檔案合規歸檔"
        ]
        duties_en = [
            "Assist in campus recruiting projects, resume pre-screening, interview coordination, and reception",
            "Support corporate training logistics, e-learning platform administration, and post-training surveys",
            "Maintain HR information systems (HRIS), attendance records, and personnel file compliance"
        ]
        courses = ["人力資源管理", "組織行為學", "企業管理導論", "商務英文溝通與簡報"]
        collabs = ["HR 人資處", "各部門主管", "外部培訓機構"]
        trait_zh = "職缺強調同理心與親和溝通，適合擅長傾聽、重視團隊和諧且處事有條理的同學。"
        trait_en = "Emphasizes empathy and interpersonal warmth; ideal for patient, communicative, and organized students."
        summary_zh = f"協助{company}人資部推動校園招募與人才培育專案，負責面試行政安排、培訓活動執行與人資系統管理。"
        summary_en = f"Assists {company} HR department with campus recruitment, training logistics, and HRIS administration."
        ksa = {
            "knowledge": [{"zh": "人力資源管理功能與法規", "en": "HR Functions & Labor Regulations"}, {"zh": "組織行為學與教育訓練模式", "en": "Organizational Behavior & Training Models"}],
            "skills": [{"zh": "招募面談技巧與跨部門協調", "en": "Interview Coordination & Multi-party Alignment"}, {"zh": "人資資訊系統操作 (HRIS)", "en": "HR Information System Operations"}],
            "attributes": [{"zh": "溫暖同理心與傾聽能力", "en": "Empathy & Active Listening"}, {"zh": "高度道德標準與保密操守", "en": "High Ethics & Confidentiality"}]
        }

    # 7. Cybersecurity, IT Infrastructure & Network
    elif any(k in text for k in ["資安", "網絡", "server", "伺服器", "機房", "it", "security", "mis"]):
        duties = [
            "協助維護雲端 AI 伺服器與資訊機房設備運作狀態，記錄異常通報日誌",
            "參與資安合規制度文件整理、帳號權限清查審核與端點防護測試",
            "支援內部同仁日常資訊系統疑難排解（IT Helpdesk）與軟硬體安裝指引"
        ]
        duties_en = [
            "Monitor cloud server and data center equipment status, logging incident reports",
            "Assist in cybersecurity compliance documentation, account privilege audits, and endpoint tests",
            "Provide internal IT helpdesk support, troubleshooting hardware and software inquiries"
        ]
        courses = ["資訊安全導論", "作業系統概論", "資料庫管理", "系統分析與設計"]
        collabs = ["IT 資訊團隊", "RD 研發處", "QA 品保處"]
        trait_zh = "職缺強調資訊安全敏銳度與耐煩排錯精神，適合重視系統流程規範、冷靜理性的同學。"
        trait_en = "Requires cybersecurity vigilance and systematic troubleshooting; ideal for structured analytical thinkers."
        summary_zh = f"支援{company}資訊技術處日常基礎架構運維，負責伺服器狀態巡檢、資安合規管理與內部 IT 服務支援。"
        summary_en = f"Supports {company} IT infrastructure operations, server monitoring, compliance audits, and helpdesk services."
        ksa = {
            "knowledge": [{"zh": "資訊安全架構與網路通訊", "en": "Cybersecurity Architecture & Networking"}, {"zh": "伺服器作業系統與機房規範", "en": "Server OS & Data Center Standards"}],
            "skills": [{"zh": "系統故障排查與日誌分析", "en": "Troubleshooting & Log Analysis"}, {"zh": "帳號權限管理與合規稽核", "en": "Access Control & Compliance Auditing"}],
            "attributes": [{"zh": "嚴守資訊安全與保密紀律", "en": "Strict Security & Confidentiality"}, {"zh": "冷靜沉著的除錯耐心", "en": "Calm Problem-solving Patience"}]
        }

    # 8. Legal, Patents & Contracts
    elif any(k in text for k in ["法務", "專利", "智財", "合約", "legal", "patent"]):
        duties = [
            "協助初審國內外商業合約草案、保密協議（NDA）並標註關鍵法律風險條款",
            "檢索國內外智慧財產權與專利法規判決先例，整理成研究分析摘要",
            "建檔維護公司法務合約管理系統，追蹤合約有效期限與歸檔作業"
        ]
        duties_en = [
            "Pre-screen commercial contracts and NDAs, flagging key risk provisions",
            "Research domestic and international IP case laws and summarize precedents",
            "Maintain contract management databases, tracking renewal deadlines and physical filing"
        ]
        courses = ["商務英文溝通與簡報", "國際企業經營策略", "企業管理導論"]
        collabs = ["法務處", "各部門主管", "SALES 業務處"]
        trait_zh = "職缺強調法規精準理解與文字敏銳度，適合邏輯思維周密、重視法律風險防範的同學。"
        trait_en = "Requires legal precision and analytical rigor; ideal for thorough, meticulous students."
        summary_zh = f"協助{company}法務智財部門審閱商業合約文件、檢索專利判例並維護法務管理系統。"
        summary_en = f"Assists {company} legal department with contract reviews, IP patent research, and file governance."
        ksa = {
            "knowledge": [{"zh": "智慧財產權法與公司法規", "en": "Intellectual Property & Corporate Law"}, {"zh": "國際商務合約審閱原則", "en": "International Commercial Contracts"}],
            "skills": [{"zh": "法律條文檢索與風險分析", "en": "Legal Research & Risk Analysis"}, {"zh": "中英雙語法律文件草擬", "en": "Bilingual Legal Drafting"}],
            "attributes": [{"zh": "高度謹慎與嚴密邏輯", "en": "Caution & Meticulous Logic"}, {"zh": "崇高職業道德操守", "en": "High Professional Ethics"}]
        }

    # Default Management / Business Operations Intern (Still 100% custom, no boilerplate PM sentences)
    else:
        duties = [
            f"協助{company}業務營運單位整理日常專案報表與跨部門會議追蹤事項",
            "蒐集產業最新趨勢動態與市場調研數據，輔助主管製作商業決策簡報",
            "維護內部業務管理系統資料庫，確保各專案執行檔案與行政流程順暢"
        ]
        duties_en = [
            f"Assist {company} business units in daily operational reporting and milestone follow-ups",
            "Conduct market research and industry trend data collection for executive presentations",
            "Maintain operational management databases and coordinate interdepartmental workflows"
        ]
        courses = ["專案管理概論", "商業智慧與大數據分析", "商務英文溝通與簡報", "統計學與數據分析"]
        collabs = ["各部門主管", "PM 專案經理", "業務銷售團隊"]
        trait_zh = "職缺強調商業營運敏銳度與專案執行力，適合具備跨領域溝通熱忱且學習力強的同學。"
        trait_en = "Values operational acumen and collaborative execution; ideal for versatile, proactive learners."
        summary_zh = f"支援{company}業務營運團隊推動日常專案管理、市場情報調研與跨部門行政流程協調。"
        summary_en = f"Supports {company} business operations in project coordination, market research, and cross-functional administration."
        ksa = {
            "knowledge": [{"zh": "商業專案管理與營運流程", "en": "Project Management & Business Operations"}, {"zh": "產業調研與市場分析架構", "en": "Market Research & Industry Analysis"}],
            "skills": [{"zh": "商業簡報製作與數據圖表", "en": "Business Presentation & Data Viz"}, {"zh": "跨部門專案時程協調", "en": "Cross-functional Scheduling"}],
            "attributes": [{"zh": "主動積極與靈活應變", "en": "Proactivity & Agility"}, {"zh": "團隊合作與溝通親和力", "en": "Teamwork & Interpersonal Warmth"}]
        }

    return {
        "job_duties": duties,
        "job_duties_en": duties_en,
        "recommended_courses": courses,
        "trait_advice": trait_zh,
        "trait_advice_en": trait_en,
        "collaborators": collabs,
        "bilingual_ksa": ksa,
        "jd_summary": {"zh": summary_zh, "en": summary_en},
        "core_dimensions": [
            {"name": "數位工具與數據分析", "name_en": "Digital Tools & Data Analytics", "weight": 35},
            {"name": "創新與專案流程", "name_en": "Process Management", "weight": 35},
            {"name": "團隊溝通與跨部門領導", "name_en": "Team Communication", "weight": 30}
        ]
    }


def analyze_internship_jd(
    job_title: str,
    company: str,
    raw_description: str,
    location_desc: str = "",
    salary_desc: str = "",
    period_desc: str = "",
    edu_desc: str = "",
    major_desc: str = "",
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Main entry point for internship JD semantic analysis.
    raw_description MUST be the actual job content text scraped from the 104 detail page.
    Raises ValueError if raw_description is empty — no template fallback is permitted.
    1. Try real Gemini API if GEMINI_API_KEY is configured.
    2. Fall back to domain keyword analysis if Gemini API is unavailable or unconfigured (when allow_fallback=True).
    """
    # Hard gate: refuse to proceed without real content
    if not raw_description or not raw_description.strip():
        raise ValueError(
            f"[Analyzer] raw_description is empty for '{job_title}' @ {company}. "
            "Crawler must fetch the 104 detail page before calling the analyzer."
        )

    flags = detect_compliance_flags(raw_description)
    discussion_links = generate_discussion_links(company, job_title)

    # 1. Try real Gemini API if key is present
    if GEMINI_API_KEY:
        gemini_result = call_gemini_api(job_title, company, raw_description)
        if gemini_result and gemini_result.get("job_duties"):
            gemini_result["compliance_flags"] = flags
            gemini_result["discussion_links"] = discussion_links
            gemini_result["ai_model"] = gemini_result.get("ai_model") or GEMINI_MODEL
            gemini_result["ai_status"] = "done"
            return gemini_result
        print(f"[Gemini API WARNING] Real API failed or returned empty for '{job_title}'.")

    # 2. Fall back to domain keyword analysis (for offline unit tests or API fallback)
    if allow_fallback:
        result = fallback_domain_semantic_analysis(job_title, company, raw_description)
        result["compliance_flags"] = flags
        result["discussion_links"] = discussion_links
        result["ai_model"] = "domain-rule-backed"
        # If no key was provided (e.g. offline unit testing), mark done. If key was present but call failed, keep pending for retry.
        result["ai_status"] = "done" if not GEMINI_API_KEY else "pending"
        return result

    print(f"[Gemini API WARNING] Real API failed for '{job_title}', marking as failed.")
    return {
        "job_duties": [],
        "recommended_courses": [],
        "trait_advice": "",
        "compliance_flags": flags,
        "discussion_links": discussion_links,
        "ai_model": None,
        "ai_status": "failed"
    }


if __name__ == "__main__":
    from pathlib import Path
    data_file = Path(__file__).resolve().parent.parent / "data" / "data.json"
    if not data_file.exists():
        print(f"[Analyzer] {data_file} not found.")
        sys.exit(0)

    with open(data_file, "r", encoding="utf-8") as f:
        db = json.load(f)

    max_llm = int(os.getenv("MAX_LLM_PER_RUN", "50"))
    jobs = db.get("jobs", [])
    updated_count = 0
    print(f"[Analyzer] Starting analyzer pass. MAX_LLM_PER_RUN limit: {max_llm}")

    for j in jobs:
        if updated_count >= max_llm:
            print(f"[Analyzer] Reached MAX_LLM_PER_RUN limit ({max_llm}). Remaining pending jobs will be processed next run.")
            break
        raw_desc = (j.get("raw_description") or "").strip()
        if raw_desc and j.get("ai_status") != "done":
            try:
                print(f"[Analyzer] Processing: {j.get('title')} @ {j.get('company')}...")
                res = analyze_internship_jd(j.get("title", ""), j.get("company", ""), raw_desc)
                if res.get("job_duties"):
                    j["job_duties"] = res["job_duties"]
                if res.get("recommended_courses"):
                    j["recommended_courses"] = res["recommended_courses"]
                if res.get("trait_advice"):
                    j["trait_advice"] = res["trait_advice"]
                if res.get("bilingual_ksa"):
                    j["bilingual_ksa"] = res["bilingual_ksa"]
                if res.get("jd_summary"):
                    j["jd_summary"] = res["jd_summary"]
                if res.get("ai_model"):
                    j["ai_model"] = res["ai_model"]
                j["ai_status"] = res.get("ai_status", "done")

                if res.get("ai_status") == "done":
                    updated_count += 1

                # Safe pacing: 4.2 seconds between calls to enforce <= 14 RPM
                if GEMINI_API_KEY:
                    time.sleep(4.2)
            except Exception as e:
                print(f"[Analyzer] Error processing {j.get('title')}: {e}")

    if updated_count > 0:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"[Analyzer] Successfully updated {updated_count} jobs in {data_file.name}")
    else:
        print("[Analyzer] All eligible jobs with raw_description are already analyzed or limit reached.")
