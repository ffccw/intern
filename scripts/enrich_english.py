import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "data.json"

# Translation helper for job titles
def translate_job_title(company: str, title: str) -> str:
    t = title
    # Remove tags like 【...】 or [ ... ]
    tags = re.findall(r'[【\[（(]([^】\]）)]+)[】\]）)]', t)
    core = re.sub(r'[【\[（(][^】\]）)]+[】\]）)]', ' ', t)
    core = re.sub(r'[-–—~]{2,}', ' ', core)
    core = re.sub(r'\s+', ' ', core).strip()

    prefix = ""
    if any("2026" in tag for tag in tags):
        prefix = "[2026] "
    elif any("2027" in tag for tag in tags):
        prefix = "[2027] "

    # Rule-based title mapper
    if "股務代理" in t:
        return f"{prefix}Stock Affairs Agency Operations Intern"
    if "國際金融種子" in t or "金融交易" in t:
        return f"{prefix}International Financial Trading Seed Intern"
    if "法遵" in t or "法務" in t:
        return f"{prefix}Legal & Compliance Specialist Intern"
    if "採購" in t:
        return f"{prefix}Procurement & Supply Management Intern"
    if "資安" in t:
        return f"{prefix}Cybersecurity Assistant Engineer Intern"
    if "人資" in t or "HR" in t:
        if "數據分析" in t or "系統" in t:
            return f"{prefix}HR Training Analytics & Platform Intern"
        return f"{prefix}Human Resources & Talent Development Intern"
    if "AI" in t and ("雲端" in t or "Server" in t):
        return f"{prefix}AI Cloud & Server Project Operations Intern"
    if "ESG" in t or "永續" in t:
        return f"{prefix}ESG Sustainability & Brand Marketing Intern"
    if "行銷" in t or "Marketing" in t:
        return f"{prefix}Brand Marketing & Growth Intern"
    if "營運" in t or "門市" in t or "超商" in t:
        return f"{prefix}Retail Operations & Store Management Intern"
    if "數位" in t or "數據" in t:
        return f"{prefix}Business Data Analytics & Automation Intern"
    if "財會" in t or "會計" in t or "財務" in t:
        return f"{prefix}Financial Accounting & Cost Control Intern"
    if "軟體" in t or "SW" in t or "Java" in t:
        return f"{prefix}Software Development Project Intern"
    if "硬體" in t or "HW" in t or "SMT" in t:
        return f"{prefix}Hardware Engineering & Pilot Operations Intern"
    if "專案" in t or "PM" in t or "PjM" in t:
        return f"{prefix}Project Management & PMO Support Intern"
    if "企劃" in t:
        return f"{prefix}Strategic Business Planning Intern"
    if "業務" in t:
        return f"{prefix}Sales Operations & Client Success Intern"

    # Fallback to English company + Intern
    clean_core = re.sub(r'[^\w\s]', '', core)
    return f"{prefix}{clean_core} Intern" if "Intern" not in clean_core else f"{prefix}{clean_core}"

# English duties mappings
DUTY_EN_MAP = {
    "參與專案日常進度追蹤與時程控管": "Track project timeline milestones and monitor daily schedule deliverables",
    "跨職能團隊溝通協調與週會會議紀錄彙整": "Facilitate cross-functional communication and synthesize weekly review minutes",
    "協助主管交付之數據整理與分析報告撰寫": "Analyze operational metrics datasets and compile analytical executive reports",
    "規劃並落實產品/專案流程測試與驗證": "Plan and execute workflow acceptance tests and solution validations",
    "維護內部知識庫與標準作業流程 (SOP) 文件": "Maintain internal documentation and Standard Operating Procedures (SOP)",
    "執行市場競品動態調研與用戶反饋整理": "Conduct competitive market benchmarking and organize user feedback insights"
}

# English trait advice mappings
TRAIT_EN_MAP = {
    "職缺特別註明「細心度高」，適合沉穩細心、重視流程細節的同學（偏內向數據優勢）。": "Emphasizes high attention to detail; suited for students who value structured workflows and data precision (introverted analytical strengths).",
    "職缺強調團隊溝通與進度控管，適合具備良好同理心與抗壓協調能力的同學。": "Prioritizes team coordination and milestone management; ideal for students with strong empathy and stress resilience.",
    "職缺要求跨部門溝通與創新提案能力，適合熱情主動、樂於表達想法的同學（偏外向社交優勢）。": "Values cross-departmental coordination and creative proposals; best fit for proactive, expressive communicators."
}

def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    jobs = db.get("jobs", [])
    print(f"Loaded {len(jobs)} jobs from {DATA_FILE}")

    for idx, j in enumerate(jobs, 1):
        # 1. Authentic English Title
        en_title = translate_job_title(j.get("company_en") or j.get("company", ""), j.get("title", ""))
        j["title_en"] = en_title

        # 2. English Job Duties
        duties_zh = j.get("job_duties", [])
        duties_en = []
        for d in duties_zh:
            en_d = DUTY_EN_MAP.get(d)
            if not en_d:
                # Fallback translation
                if "進度" in d or "時程" in d:
                    en_d = "Track project timeline milestones and monitor daily schedule deliverables"
                elif "跨職能" in d or "會議" in d or "溝通" in d:
                    en_d = "Facilitate cross-functional communication and synthesize review minutes"
                elif "數據" in d or "報告" in d:
                    en_d = "Analyze operational metrics datasets and compile analytical reports"
                else:
                    en_d = "Support business unit operations and milestone project execution"
            duties_en.append(en_d)
        j["job_duties_en"] = duties_en

        # 3. English Trait Advice
        trait_zh = j.get("trait_advice", "")
        trait_en = TRAIT_EN_MAP.get(trait_zh)
        if not trait_en:
            if "細心" in trait_zh:
                trait_en = "Emphasizes high attention to detail; suited for students who value structured workflows and data precision."
            elif "外向" in trait_zh or "表達" in trait_zh:
                trait_en = "Values proactive cross-departmental coordination and creative proposals (expressive communication strengths)."
            else:
                trait_en = "Prioritizes team coordination and milestone management; ideal for students with strong empathy and cross-unit alignment."
        j["trait_advice_en"] = trait_en

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"Successfully enriched all {len(jobs)} jobs with authentic English titles, duties, and trait advice!")

if __name__ == "__main__":
    main()
