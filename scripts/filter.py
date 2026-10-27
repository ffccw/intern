"""
Company and Job Title Filter module
Optimized for Taiwan 50 & Mid-Cap 100 Management College Internships.
Conforms to PRD Section 2.1 & student internship radar rules.
"""
import re
import unicodedata
from typing import Optional, Tuple, Dict, Set, List, Any


def normalize_company_name(name: str) -> str:
    """Standardize company name: removes corporate suffix, spaces, case."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"\(股\)|\（股\）", "", name)
    name = re.sub(r"股份有限公司|有限公司|企業股份有限公司|科技股份有限公司|實業股份有限公司", "", name)
    name = re.sub(r"\s+", "", name)
    return name.lower().strip()


# Mandatory Intern keywords
INTERN_PATTERNS = [
    re.compile(r"實習", re.IGNORECASE),
    re.compile(r"實習生", re.IGNORECASE),
    re.compile(r"\bIntern(?:ship)?\b", re.IGNORECASE),
    re.compile(r"研習生", re.IGNORECASE),
]

# Management College domains keywords
MGMT_PATTERNS = [
    re.compile(r"專案", re.IGNORECASE),
    re.compile(r"產品", re.IGNORECASE),
    re.compile(r"\bPM\b", re.IGNORECASE),
    re.compile(r"\bPjM\b", re.IGNORECASE),
    re.compile(r"\bProject\b", re.IGNORECASE),
    re.compile(r"\bProduct\b", re.IGNORECASE),
    re.compile(r"行銷", re.IGNORECASE),
    re.compile(r"品牌", re.IGNORECASE),
    re.compile(r"企劃", re.IGNORECASE),
    re.compile(r"\bMarketing\b", re.IGNORECASE),
    re.compile(r"\bBrand\b", re.IGNORECASE),
    re.compile(r"商業", re.IGNORECASE),
    re.compile(r"營運", re.IGNORECASE),
    re.compile(r"分析", re.IGNORECASE),
    re.compile(r"\bBusiness\b", re.IGNORECASE),
    re.compile(r"\bOperations?\b", re.IGNORECASE),
    re.compile(r"\bAnalyst\b", re.IGNORECASE),
    re.compile(r"\bBA\b", re.IGNORECASE),
    re.compile(r"採購", re.IGNORECASE),
    re.compile(r"供應鏈", re.IGNORECASE),
    re.compile(r"資材", re.IGNORECASE),
    re.compile(r"\bProcurement\b", re.IGNORECASE),
    re.compile(r"\bSupply\s*Chain\b", re.IGNORECASE),
    re.compile(r"人資", re.IGNORECASE),
    re.compile(r"招募", re.IGNORECASE),
    re.compile(r"行政", re.IGNORECASE),
    re.compile(r"\bHR\b", re.IGNORECASE),
    re.compile(r"資訊管理", re.IGNORECASE),
    re.compile(r"資安", re.IGNORECASE),
    re.compile(r"AI\s*落地", re.IGNORECASE),
]

# Non-management exclusions (frontline manual labor / restaurant / retail clerks)
EXCLUDE_PATTERNS = [
    re.compile(r"門市工讀", re.IGNORECASE),
    re.compile(r"餐飲工讀", re.IGNORECASE),
    re.compile(r"加油員", re.IGNORECASE),
    re.compile(r"清潔員", re.IGNORECASE),
    re.compile(r"作業員", re.IGNORECASE),
    re.compile(r"產線包裝", re.IGNORECASE),
]


def match_internship_title(title: str) -> bool:
    """
    Checks if a job title matches Taiwan 50 / Mid-100 Management Internship criteria:
    1. Must match at least one INTERN keyword
    2. Must match at least one Management domain keyword
    3. Must NOT match any exclude pattern
    """
    if not title:
        return False

    for pat in EXCLUDE_PATTERNS:
        if pat.search(title):
            return False

    has_intern = any(pat.search(title) for pat in INTERN_PATTERNS)
    has_mgmt = any(pat.search(title) for pat in MGMT_PATTERNS)

    return has_intern and has_mgmt


INDEX_LABEL_MAP = {
    "TW50": "台灣 50",
    "MID100": "中型 100",
    "TPEX50": "富櫃 50",
    "TWSE": "上市",
    "TPEX": "上櫃",
}


def match_company_whitelist(
    company_name: str,
    target_companies: List[Dict[str, Any]],
    subsidiaries_dict: Dict[str, str],
) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Matches company name against Taiwan Listed (TWSE) & OTC (TPEx) companies,
    including TW50, Mid 100, and TPEx 50 constituents as well as known subsidiaries.
    Returns: (is_matched, stock_code, index_label, parent_company, company_en)
    """
    norm_name = normalize_company_name(company_name)

    # 1. Direct match in target companies
    for comp in target_companies:
        short_name = comp.get("short_name", "")
        # Negative Disambiguation Rules:
        if short_name == "聯電" and "群聯" in norm_name:
            continue
        if short_name == "台塑" and "台塑化" in norm_name:
            continue
        if short_name == "統一" and ("統一超" in norm_name or "統一實" in norm_name):
            continue
        if short_name == "長榮" and "長榮航" in norm_name:
            continue
        if short_name == "欣興" and "欣銓" in norm_name:
            continue

        comp_norm = normalize_company_name(comp.get("name", ""))
        short_norm = normalize_company_name(short_name)
        if not comp_norm and not short_norm:
            continue

        matched = False
        if comp_norm and (norm_name == comp_norm or (len(comp_norm) >= 3 and comp_norm in norm_name) or (len(norm_name) >= 3 and norm_name in comp_norm)):
            matched = True
        elif short_norm and len(short_norm) >= 2 and short_norm in norm_name:
            matched = True

        if matched:
            raw_idx = comp.get("index", "TWSE")
            index_label = INDEX_LABEL_MAP.get(raw_idx, "上市")
            return True, comp["code"], index_label, None, comp.get("en")

    # 2. Check subsidiaries
    for sub_name, parent_code in subsidiaries_dict.items():
        sub_norm = normalize_company_name(sub_name)
        if sub_norm in norm_name or norm_name in sub_norm:
            parent_match = next((c for c in target_companies if c["code"] == parent_code), None)
            raw_idx = parent_match.get("index", "TWSE") if parent_match else "TWSE"
            index_label = INDEX_LABEL_MAP.get(raw_idx, "上市")
            return (
                True,
                parent_code,
                index_label,
                parent_match["name"] if parent_match else sub_name,
                parent_match.get("en") if parent_match else None,
            )

    return False, None, None, None, None
