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
    name = re.sub(r"股份有限公司|有限公司|企業股份有限公司|科技股份有限公司|實業股份有限公司|co\.,?\s*ltd\.?|inc\.?|corp\.?", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", "", name)
    return name.lower().strip()


# Mandatory Intern keywords
INTERN_PATTERNS = [
    re.compile(r"實習", re.IGNORECASE),
    re.compile(r"實習生", re.IGNORECASE),
    re.compile(r"\bIntern(?:ship)?\b", re.IGNORECASE),
    re.compile(r"研習生", re.IGNORECASE),
    re.compile(r"培訓生", re.IGNORECASE),
    re.compile(r"\bTrainee\b", re.IGNORECASE),
    re.compile(r"\bCampus\b", re.IGNORECASE),
    re.compile(r"暑期", re.IGNORECASE),
    re.compile(r"學期", re.IGNORECASE),
    re.compile(r"學年", re.IGNORECASE),
    re.compile(r"學生", re.IGNORECASE),
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
    Checks if a job title matches internship criteria:
    1. Must match at least one INTERN keyword
    2. Must NOT match any exclude pattern
    """
    if not title:
        return False

    for pat in EXCLUDE_PATTERNS:
        if pat.search(title):
            return False

    has_intern = any(pat.search(title) for pat in INTERN_PATTERNS)
    return has_intern


INDEX_LABEL_MAP = {
    "TW50": "台灣 50",
    "MID100": "中型 100",
    "TPEX50": "富櫃 50",
    "TWSE": "上市",
    "TPEX": "上櫃",
}

# Major Financial Holdings Brand Stems to Stock Codes
FIN_HOLDINGS = [
    {"prefix": "富邦", "code": "2881"},
    {"prefix": "國泰", "code": "2882"},
    {"prefix": "中信", "code": "2891"},
    {"prefix": "中國信託", "code": "2891"},
    {"prefix": "元大", "code": "2885"},
    {"prefix": "玉山", "code": "2884"},
    {"prefix": "台新", "code": "2887"},
    {"prefix": "永豐", "code": "2890"},
    {"prefix": "兆豐", "code": "2886"},
    {"prefix": "第一", "code": "2892"},
    {"prefix": "華南", "code": "2880"},
    {"prefix": "合庫", "code": "5880"},
    {"prefix": "合作金庫", "code": "5880"},
    {"prefix": "凱基", "code": "2883"},
    {"prefix": "開發", "code": "2883"},
    {"prefix": "新光", "code": "2888"},
]

FIN_TYPES = ["銀行", "證券", "人壽", "產險", "產物", "保險", "投信", "期貨", "租賃", "金控", "資產管理", "商業銀行"]


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
    if not norm_name:
        return False, None, None, None, None

    # 1. Financial Holding Subsidiary Matching (e.g. 國泰世華銀行 -> 國泰金, 中國信託銀行 -> 中信金)
    for fin in FIN_HOLDINGS:
        if fin["prefix"] in norm_name:
            if any(t in norm_name for t in FIN_TYPES):
                parent_match = next((c for c in target_companies if c["code"] == fin["code"]), None)
                if parent_match:
                    raw_idx = parent_match.get("index", "TW50")
                    index_label = INDEX_LABEL_MAP.get(raw_idx, "台灣 50")
                    return True, fin["code"], index_label, parent_match.get("name"), parent_match.get("en")

    # 2. Direct match in target companies
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

    # 3. Check explicit subsidiaries
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
