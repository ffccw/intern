"""
Company and Job Title Filter module
Optimized for Taiwan 50, Mid-Cap 100, TPEx 50, and all Listed (TWSE) & OTC (TPEx) Internships.
Conforms to PRD Section 2.1 & student internship radar rules.
"""
import re
import unicodedata
from typing import Optional, Tuple, Dict, List, Any


def normalize_exact_corp_name(name: str) -> str:
    """
    Standardize company name while preserving industry qualifiers (e.g. 電子, 科技, 電線電纜, 石化, 實業)
    so distinct listed companies never collide during exact full-name matching.
    """
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"\(股\)公司|\(股\)|（股）公司|（股）", "", name)
    name = re.sub(
        r"股份有限公司|有限公司|co\.,?\s*ltd\.?|inc\.?|corp\.?|corporation|limited",
        "",
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"[\s\.\,]+", "", name)
    return name.lower().strip()


def normalize_company_name(name: str) -> str:
    """Standardize company name: removes corporate suffix, spaces, case."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"\(股\)|\（股\）", "", name)
    name = re.sub(
        r"股份有限公司|有限公司|企業股份有限公司|科技股份有限公司|實業股份有限公司|co\.,?\s*ltd\.?|inc\.?|corp\.?",
        "",
        name,
        flags=re.IGNORECASE,
    )
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
    re.compile(r"外場工讀", re.IGNORECASE),
    re.compile(r"內場工讀", re.IGNORECASE),
    re.compile(r"加油站?工讀", re.IGNORECASE),
    re.compile(r"加油員", re.IGNORECASE),
    re.compile(r"清潔員", re.IGNORECASE),
    re.compile(r"作業員", re.IGNORECASE),
    re.compile(r"產線包裝", re.IGNORECASE),
]


def match_internship_title(title: str) -> bool:
    """
    Checks if a job title matches internship criteria:
    1. Must match at least one INTERN keyword
    2. Must NOT match any exclude pattern or full-time executive role without intern keyword
    """
    if not title:
        return False

    for pat in EXCLUDE_PATTERNS:
        if pat.search(title):
            return False

    if any(k in title for k in ["資深", "正職", "主管", "處長", "副理", "協理"]) and "實習" not in title and "intern" not in title.lower():
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
    {"prefix": "開發金", "code": "2883"},
    {"prefix": "新光", "code": "2888"},
]

FIN_TYPES = [
    "銀行", "證券", "人壽", "產險", "產物", "保險",
    "投信", "期貨", "租賃", "金控", "資產管理", "商業銀行", "創投", "投顧"
]

DEFAULT_SUBSIDIARIES = {
    "緯穎科技服務股份有限公司": "3231",
    "研揚科技股份有限公司": "2395",
    "鴻騰精密科技股份有限公司": "2317",
    "啟碁科技股份有限公司": "3231",
    "廣達研究院": "2382",
    "廣明光電股份有限公司": "2382",
    "富邦媒體科技股份有限公司": "2881",
}

AGENCY_EXCLUSIONS = [
    "104未來無限整合招募中心",
    "104人力銀行",
    "藝珂人事顧問",
    "萬寶華企業管理顧問",
    "保聖那管理顧問",
    "才庫人力資源",
]

CORP_SUFFIX_PATTERN = re.compile(
    r"^(科技|電子|工業|電腦|光電|半導體|國際|企業|實業|精密|精密工業|金控|金融控股|資訊|電信|網路|生技|醫藥|化學|石化|電機|機械|控股|集團|台灣|臺灣)+$"
)

# Pre-indexed cache for O(1) lookup speed across 1,991 companies
_INDEX_CACHE: Dict[int, Dict[str, Any]] = {}


def _get_indexed_whitelist(target_companies: List[Dict[str, Any]]) -> Dict[str, Any]:
    cache_key = id(target_companies)
    if cache_key in _INDEX_CACHE and _INDEX_CACHE[cache_key]["len"] == len(target_companies):
        return _INDEX_CACHE[cache_key]

    code_map: Dict[str, Dict[str, Any]] = {}
    exact_name_map: Dict[str, Dict[str, Any]] = {}
    enriched_list: List[Dict[str, Any]] = []

    for comp in target_companies:
        c_code = comp.get("code", "")
        if c_code:
            code_map[c_code] = comp
        c_exact = normalize_exact_corp_name(comp.get("name", ""))
        s_exact = normalize_exact_corp_name(comp.get("short_name", ""))
        if c_exact and c_exact not in exact_name_map:
            exact_name_map[c_exact] = comp
        enriched_list.append({
            "comp": comp,
            "comp_exact": c_exact,
            "short_exact": s_exact,
            "short_name": comp.get("short_name", ""),
        })

    by_fullname_len = sorted(enriched_list, key=lambda x: len(x["comp_exact"]), reverse=True)
    by_short_len = sorted(enriched_list, key=lambda x: len(x["short_exact"]), reverse=True)

    entry = {
        "len": len(target_companies),
        "code_map": code_map,
        "exact_name_map": exact_name_map,
        "by_fullname_len": by_fullname_len,
        "by_short_len": by_short_len,
    }
    _INDEX_CACHE[cache_key] = entry
    return entry


def _extract_name_parts(raw_name: str) -> Tuple[str, List[str], List[str]]:
    normalized_raw = unicodedata.normalize("NFKC", raw_name or "").strip()
    paren_notes = re.findall(r"\(([^)]+)\)", normalized_raw)
    outside_paren = re.sub(r"\([^)]*\)", " ", normalized_raw).strip()
    tokens = [t.strip() for t in re.split(r"[_\-—/｜|]+", outside_paren) if t.strip()]
    main_name = tokens[-1] if tokens else outside_paren
    return main_name, tokens, paren_notes


def match_company_whitelist(
    company_name: str,
    target_companies: List[Dict[str, Any]],
    subsidiaries_dict: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Multi-pass company name matcher against Taiwan Listed (TWSE) & OTC (TPEx) companies,
    including TW50, Mid 100, and TPEx 50 constituents as well as known subsidiaries.
    Returns: (is_matched, stock_code, index_label, parent_company, company_en)
    """
    if not company_name or not company_name.strip():
        return False, None, None, None, None

    if any(agency in company_name for agency in AGENCY_EXCLUSIONS):
        return False, None, None, None, None

    idx_data = _get_indexed_whitelist(target_companies)
    code_map = idx_data["code_map"]
    exact_name_map = idx_data["exact_name_map"]

    merged_subs = dict(DEFAULT_SUBSIDIARIES)
    if subsidiaries_dict:
        merged_subs.update(subsidiaries_dict)

    main_name, tokens, paren_notes = _extract_name_parts(company_name)
    full_exact = normalize_exact_corp_name(company_name)
    main_exact = normalize_exact_corp_name(main_name)
    token_exacts = [normalize_exact_corp_name(t) for t in tokens if normalize_exact_corp_name(t)]

    if not full_exact and not main_exact:
        return False, None, None, None, None

    # =========================================================================
    # PASS 1A: O(1) Exact Full Registered Name Match on main_exact or full_exact
    # =========================================================================
    for candidate_key in (main_exact, full_exact):
        if candidate_key in exact_name_map:
            comp = exact_name_map[candidate_key]
            raw_idx = comp.get("index", "TWSE")
            return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), None, comp.get("en")

    # PASS 1B: Exact Full Registered Name Match on any split token (longest token first)
    for tok in sorted(token_exacts, key=len, reverse=True):
        if len(tok) >= 4 and tok in exact_name_map:
            comp = exact_name_map[tok]
            raw_idx = comp.get("index", "TWSE")
            return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), None, comp.get("en")

    # =========================================================================
    # PASS 2: Explicit Subsidiaries & Financial Holding Affiliates
    # =========================================================================
    for sub_name, parent_code in merged_subs.items():
        sub_exact = normalize_exact_corp_name(sub_name)
        if sub_exact and (sub_exact == main_exact or sub_exact in token_exacts or sub_exact in full_exact):
            parent_match = code_map.get(parent_code)
            raw_idx = parent_match.get("index", "TWSE") if parent_match else "TWSE"
            index_label = INDEX_LABEL_MAP.get(raw_idx, "上市")
            return (
                True,
                parent_code,
                index_label,
                parent_match["name"] if parent_match else sub_name,
                parent_match.get("en") if parent_match else None,
            )

    for fin in FIN_HOLDINGS:
        if fin["prefix"] in full_exact:
            if any(t in full_exact for t in FIN_TYPES):
                if fin["prefix"] == "永豐" and any(x in full_exact for x in ["永豐餘", "永豐實"]):
                    continue
                parent_match = code_map.get(fin["code"])
                if parent_match:
                    raw_idx = parent_match.get("index", "TW50")
                    index_label = INDEX_LABEL_MAP.get(raw_idx, "台灣 50")
                    return True, fin["code"], index_label, parent_match.get("name"), parent_match.get("en")

    # =========================================================================
    # PASS 3: Full Registered Name Containment (Longest full name first, len >= 4)
    # =========================================================================
    for item in idx_data["by_fullname_len"]:
        comp_exact = item["comp_exact"]
        if len(comp_exact) >= 4 and (comp_exact in main_exact or comp_exact in full_exact):
            comp = item["comp"]
            raw_idx = comp.get("index", "TWSE")
            return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), None, comp.get("en")

    # =========================================================================
    # PASS 4: Short-Name Matching (Longest short_name first + Strict Boundary Guards)
    # =========================================================================
    for item in idx_data["by_short_len"]:
        comp = item["comp"]
        short_name = item["short_name"]
        short_exact = item["short_exact"]
        if not short_exact or len(short_exact) < 2:
            continue

        if short_name == "聯電" and any(x in full_exact for x in ["群聯", "精聯", "台聯電", "聯電訊"]):
            continue
        if short_name == "台塑" and any(x in full_exact for x in ["台塑化", "台塑石化", "台塑勝高", "台勝科"]):
            continue
        if short_name == "統一" and any(x in full_exact for x in ["統一超", "統一實", "統一證", "統一綜合證券"]):
            continue
        if short_name == "長榮" and any(x in full_exact for x in ["長榮航", "長榮鋼", "長榮國際儲運", "榮運", "李長榮"]):
            continue
        if short_name == "欣興" and "欣銓" in full_exact:
            continue
        if short_name == "中華電" and "電線" in full_exact:
            continue
        if short_name == "中鋼" and any(x in full_exact for x in ["中鋼碳素", "中鋼構", "中鋼保全"]):
            continue
        if short_name == "台灣大" and "台灣大學" in full_exact:
            continue

        # Case A: Exact short name match on main name or a prefix token
        if main_exact == short_exact or short_exact in token_exacts:
            raw_idx = comp.get("index", "TWSE")
            return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), None, comp.get("en")

        # Case B: Short name at the start of main_exact followed strictly by standard corporate/industry words
        if main_exact.startswith(short_exact):
            remainder = main_exact[len(short_exact):]
            if remainder and CORP_SUFFIX_PATTERN.match(remainder):
                raw_idx = comp.get("index", "TWSE")
                return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), None, comp.get("en")

    # =========================================================================
    # PASS 5: Check Parenthetical Group Notes (e.g. "XX公司（廣達關係企業）")
    # =========================================================================
    for note in paren_notes:
        if any(k in note for k in ["關係企業", "集團", "子公司", "金控"]):
            cleaned_note = re.sub(r"關係企業|集團|子公司", "", note).strip()
            note_exact = normalize_exact_corp_name(cleaned_note)
            if len(note_exact) >= 2:
                for item in idx_data["by_short_len"]:
                    if note_exact == item["short_exact"] or note_exact == item["comp_exact"]:
                        comp = item["comp"]
                        raw_idx = comp.get("index", "TWSE")
                        return True, comp["code"], INDEX_LABEL_MAP.get(raw_idx, "上市"), comp.get("name"), comp.get("en")

    return False, None, None, None, None
