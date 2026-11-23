"""
104 Listed & OTC Internship Crawler
Features:
- Internship-only search, followed by an exact TWSE/TPEx company whitelist check
- Standard HTTP requests with a normal Playwright rendered-page fallback (.info-container)
- Enforces strict internship title rules and eliminates non-intern full-time jobs
- Multi-pass company whitelist matching across all 1,991 TWSE & TPEx companies (zero short-name collision)
- Records unmatched internship companies to data/unmatched_companies.json for subsidiary review
"""
import os
import sys
import json
import time
import datetime
import csv
import urllib.request
import urllib.parse
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

import requests

HEADERS_104 = {
    "User-Agent": "pm-pjm-internship-monitor/1.0 (educational, non-commercial)",
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

HTTP_SESSION = None
PLAYWRIGHT_MANAGER = None


def get_session():
    global HTTP_SESSION
    if HTTP_SESSION is None:
        HTTP_SESSION = requests.Session()
    return HTTP_SESSION


# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
COMPANIES_FILE = DATA_DIR / "target_companies.json"
DATA_FILE = DATA_DIR / "data.json"
CSV_FILE = DATA_DIR / "google_sheets_import.csv"
SUBSIDIARIES_FILE = DATA_DIR / "subsidiaries.json"
UNMATCHED_FILE = DATA_DIR / "unmatched_companies.json"

sys.path.insert(0, str(BASE_DIR / "scripts"))
from analyzer import analyze_internship_jd
from filter import match_company_whitelist, match_internship_title, normalize_company_name, is_issuer_employer, INDEX_LABEL_MAP
from public_data import load_private_descriptions, private_file_for, stage_raw_descriptions
from storage import atomic_save_json

PRIVATE_DESCRIPTIONS_FILE = private_file_for(BASE_DIR)

UNMATCHED_COMPANIES: Dict[str, Dict[str, Any]] = {}


def direct_104_job_url(href: str) -> str:
    """Resolve a 104 tracking link without publishing its redirect URL."""
    if not isinstance(href, str):
        return ""
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/job/"):
        href = "https://www.104.com.tw" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme == "https" and parsed.netloc == "r.104.com.tw":
        href = urllib.parse.parse_qs(parsed.query).get("url", [""])[0]
        parsed = urllib.parse.urlparse(href)
    if (parsed.scheme != "https" or parsed.netloc != "www.104.com.tw"
            or not re.fullmatch(r"/job/[A-Za-z0-9]+", parsed.path)):
        return ""
    return f"https://www.104.com.tw{parsed.path}"


def search_items_from_payload(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """Return None for an unknown response schema, [] for a valid empty list."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "jobs"):
            if isinstance(data.get(key), list):
                return data[key]
    return None


def build_104_search_url(
    path: str,
    jobcat: Optional[str] = None,
    page: int = 1,
    order: int = 15,
) -> str:
    """Build an internship-only 104 search URL without keyword-search parameters."""
    params = {
        "ro": "0",
        "rostatus": "1024",
        "order": str(order),
        "asc": "0",
        "page": str(page),
        "mode": "s",
        "jobsource": "2018indexpoc",
    }
    if jobcat:
        params["jobcat"] = jobcat
    return f"https://www.104.com.tw{path}?{urllib.parse.urlencode(params)}"


def parse_104_vue_dom_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Parses 104's Vue 3 search result DOM (.info-container) into standardized API item dicts.
    Works even when 104 renders via SSR or changes internal XHR endpoint paths.
    """
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, "html.parser")
    containers = soup.select(".info-container")
    extracted: List[Dict[str, Any]] = []

    for c in containers:
        title_el = c.select_one("h2 a.info-job") or c.select_one("a.info-job") or c.select_one(".info-job__text")
        comp_el = c.select_one(".info-company > a") or c.select_one(".info-company__text")
        if not title_el or not comp_el:
            continue

        name_el = title_el.select_one(".info-name") or title_el
        job_name = name_el.get("title") or name_el.get_text(" ", strip=True)
        anchor = title_el if title_el.name == "a" else title_el.find_parent("a", href=True)
        clean_link = direct_104_job_url(anchor.get("href", "") if anchor else "")
        if not job_name or not clean_link:
            continue
        job_no = clean_link.rsplit("/", 1)[-1]

        cust_name = comp_el.get_text(strip=True)
        industry_el = c.select_one('.info-company [data-gtm-joblist^="職缺-產業-"]') or c.select_one(".info-company-addon-type")
        industry_desc = industry_el.get_text(strip=True) if industry_el else "科技製造與資訊服務業"

        tags = [t.get_text(strip=True) for t in c.select(".info-tags__text") if t.get_text(strip=True)]
        location = tags[0] if len(tags) > 0 else ""
        salary_desc = "待遇面議"
        for t in tags:
            if any(k in t for k in ["時薪", "月薪", "年薪", "面議", "元"]):
                salary_desc = t
                break

        desc_el = c.select_one(".info-content") or c.select_one(".info-description")
        desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

        extracted.append({
            "jobNo": job_no,
            "jobName": job_name,
            "custName": cust_name,
            "indcatDesc": industry_desc,
            "jobAddrNoDesc": location,
            "salaryDesc": salary_desc,
            "description": desc_text,
            "link": {"job": clean_link},
            "appearDate": datetime.date.today().strftime("%Y%m%d"),
        })

    return extracted


class Playwright104Fallback:
    """
    Renders the normal 104 search page and extracts its visible job cards.
    The browser context does not hide automation or transfer challenge cookies.
    """
    def __init__(self):
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.available = True
        self.last_diagnostic = "browser not started"

    def ensure_started(self) -> bool:
        if not self.available:
            return False
        if self.page is not None:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            is_ci = os.getenv("CI", "").lower() == "true" or sys.platform != "win32"
            launch_args = ["--no-sandbox"]
            try:
                if not is_ci:
                    self.browser = self.pw.chromium.launch(
                        channel="chrome",
                        headless=True,
                        args=launch_args,
                    )
                else:
                    self.browser = self.pw.chromium.launch(headless=True, args=launch_args)
            except Exception:
                self.browser = self.pw.chromium.launch(headless=True, args=launch_args)

            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="zh-TW",
            )
            self.page = self.context.new_page()
            print("    [Playwright] Browser fallback engine initialized successfully.")
            return True
        except Exception as e:
            print(f"    [Playwright] Could not initialize browser fallback: {e}")
            self.last_diagnostic = f"browser initialization: {type(e).__name__}"
            self.available = False
            return False

    def search_jobs(self, jobcat: Optional[str] = None, page_num: int = 1, order: int = 15) -> List[Dict[str, Any]]:
        if not self.ensure_started():
            return []

        intercepted_items: List[Dict[str, Any]] = []

        def on_response(response):
            if ("jobs/search/api/jobs" in response.url or "jobs/search/list" in response.url) and response.status == 200:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct.lower():
                        items = search_items_from_payload(response.json())
                        if items:
                            intercepted_items.extend(items)
                except Exception:
                    pass

        self.page.on("response", on_response)
        search_url = build_104_search_url("/jobs/search/", jobcat=jobcat, page=page_num, order=order)
        try:
            navigation = self.page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            http_status = navigation.status if navigation else "no response"
            try:
                self.page.wait_for_selector(".info-container", timeout=6000)
            except Exception:
                self.page.wait_for_timeout(2000)

            if intercepted_items:
                self.last_diagnostic = f"browser HTTP {http_status}, intercepted {len(intercepted_items)} jobs"
                return intercepted_items

            # Parse Vue 3 DOM (.info-container) directly if XHR wasn't intercepted
            html = self.page.content()
            dom_items = parse_104_vue_dom_html(html)
            containers = len(BeautifulSoup(html, "html.parser").select(".info-container"))
            self.last_diagnostic = (
                f"browser HTTP {http_status}, DOM containers {containers}, parsed jobs {len(dom_items)}"
            )
            return dom_items
        except Exception as e:
            self.last_diagnostic = f"browser search: {type(e).__name__}: {str(e)[:120]}"
            print(f"    [Playwright Search Error] {e}")
            return []
        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:
                pass

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass
        self.page = None
        self.browser = None
        self.pw = None


def get_playwright_fallback() -> Playwright104Fallback:
    global PLAYWRIGHT_MANAGER
    if PLAYWRIGHT_MANAGER is None:
        PLAYWRIGHT_MANAGER = Playwright104Fallback()
    return PLAYWRIGHT_MANAGER


def fetch_104_search_api(jobcat: Optional[str] = None, page: int = 1, order: int = 15) -> List[Dict[str, Any]]:
    """
    Queries 104 search API with JSON content-type verification.
    If the JSON endpoint is unavailable, falls back to normal page rendering and
    Vue 3 DOM (.info-container) parsing. A blocked request is not bypassed.
    """
    s = get_session()
    req_headers = dict(HEADERS_104)
    req_headers["Referer"] = build_104_search_url("/jobs/search/", jobcat=jobcat, page=page, order=order)
    diagnostics = []

    # 1. Try the search-list endpoint.
    list_url = build_104_search_url("/jobs/search/list", jobcat=jobcat, page=page, order=order)
    try:
        r = s.get(list_url, headers=req_headers, timeout=10)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and "json" in ct:
            items = search_items_from_payload(r.json())
            if items is not None:
                return items
            diagnostics.append("list: unknown JSON schema")
        else:
            diagnostics.append(f"list: HTTP {r.status_code}, content-type {ct[:40]}")
    except Exception as error:
        diagnostics.append(f"list: {type(error).__name__}: {str(error)[:100]}")

    # 2. Try the alternate search endpoint only after a paced retry.
    time.sleep(3.5)
    api_url = build_104_search_url("/jobs/search/api/jobs", jobcat=jobcat, page=page, order=order)
    try:
        r = s.get(api_url, headers=req_headers, timeout=10)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and "json" in ct:
            items = search_items_from_payload(r.json())
            if items is not None:
                return items
            diagnostics.append("api/jobs: unknown JSON schema")
        else:
            diagnostics.append(f"api/jobs: HTTP {r.status_code}, content-type {ct[:40]}")
    except Exception as error:
        diagnostics.append(f"api/jobs: {type(error).__name__}: {str(error)[:100]}")

    # 3. Render the regular search page if both JSON endpoints are unavailable.
    time.sleep(3.5)
    pw_fallback = get_playwright_fallback()
    items = pw_fallback.search_jobs(jobcat=jobcat, page_num=page, order=order)
    if items:
        return items
    diagnostics.append(f"page fallback: {pw_fallback.last_diagnostic}")
    query_label = f"jobcat={jobcat}" if jobcat else "all internships"
    raise RuntimeError(
        f"104 search response could not be verified for {query_label}, page {page}: {'; '.join(diagnostics)}"
    )


def fetch_job_detail_http(job_url: str) -> str:
    """
    Extracts raw work content using a standard HTTP request to the 104 job detail endpoint.
    """
    clean_url = job_url.split("?")[0].rstrip("/")
    job_no = clean_url.split("/")[-1]
    if not job_no:
        return ""
    api_url = f"https://www.104.com.tw/job/ajax/content/{job_no}"
    s = get_session()
    headers = dict(HEADERS_104)
    headers["Referer"] = clean_url
    try:
        r = s.get(api_url, headers=headers, timeout=8)
        if r.status_code == 200 and "json" in r.headers.get("content-type", "").lower():
            data = r.json()
            job_detail = data.get("data", {}).get("jobDetail", {})
            desc = job_detail.get("jobDescription", "").strip()
            condition = data.get("data", {}).get("condition", {})
            other = condition.get("other", "").strip()
            combined = desc
            if other:
                combined += "\n\n[其他條件]\n" + other
            if len(combined.strip()) >= 20:
                return combined.strip()
    except Exception:
        pass
    return ""


def fetch_job_detail(page=None, job_url: str = "") -> str:
    clean_url = job_url.split("?")[0].rstrip("/")
    http_result = fetch_job_detail_http(clean_url)
    if http_result and len(http_result.strip()) >= 20:
        return http_result.strip()
    if page is not None:
        try:
            page.goto(clean_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            desc_el = page.query_selector(".job-description__content, .job-description")
            if desc_el:
                txt = desc_el.inner_text().strip()
                if len(txt) >= 20:
                    return txt
        except Exception:
            pass
    return ""


def record_closed_observation(job: Dict[str, Any], today_str: str) -> bool:
    """Count one confirmed closure per day; never count transport errors."""
    if job.get("last_miss_date") != today_str:
        previous = job.get("last_miss_date")
        try:
            consecutive = (datetime.date.fromisoformat(today_str) - datetime.date.fromisoformat(previous)).days == 1
        except (TypeError, ValueError):
            consecutive = False
        job["miss_count"] = (int(job.get("miss_count") or 0) + 1) if consecutive else 1
        job["last_miss_date"] = today_str
    if job["miss_count"] >= 3:
        job["status"] = "closed"
        job["closed_date"] = today_str
        return True
    return False


def refresh_active_jobs(jobs: List[Dict[str, Any]], deadline: Optional[float] = None) -> Dict[str, int]:
    today_str = datetime.date.today().isoformat()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    stats = {"checked": 0, "date_updated": 0, "closed": 0, "still_open": 0}

    print(f"\n[Active Refresh] Checking {len(jobs)} existing jobs for 104 employer updates/closures...")
    for idx, job in enumerate(jobs, 1):
        if deadline is not None and time.monotonic() >= deadline:
            raise RuntimeError("Crawler time limit reached during active job refresh")
        # Normalize legacy index label if present
        if job.get("index_type") == "上櫃富櫃 50":
            job["index_type"] = "富櫃 50"

        if job.get("status") == "closed":
            continue

        url = job.get("url", "")
        job_no = url.rstrip("/").split("/")[-1].split("?")[0]
        if not job_no:
            continue

        stats["checked"] += 1
        api_url = f"https://www.104.com.tw/job/ajax/content/{job_no}"
        s = get_session()
        headers = dict(HEADERS_104)
        headers["Referer"] = url
        try:
            time.sleep(3.5)
            resp = s.get(api_url, headers=headers, timeout=8)
            if resp.status_code == 200 and "json" in resp.headers.get("content-type", "").lower():
                data = resp.json()
                payload = data.get("data", {})
                if isinstance(payload, dict) and payload.get("switch") == "off":
                    if record_closed_observation(job, today_str):
                        stats["closed"] += 1
                        print(f"  [Job Closed] {job.get('company')} | {job.get('title')} (switch=off x3)")
                    continue
                elif isinstance(payload, dict) and payload.get("switch") == "on":
                    job["status"] = "open"
                    job["last_seen_date"] = today_str
                    job["miss_count"] = 0
                    job["last_miss_date"] = None
                    stats["still_open"] += 1

                raw_appear = str(payload.get("header", {}).get("appearDate") or "")
                if "/" in raw_appear:
                    new_appear = raw_appear.replace("/", "-")
                elif len(raw_appear) == 8 and raw_appear.isdigit():
                    new_appear = f"{raw_appear[:4]}-{raw_appear[4:6]}-{raw_appear[6:8]}"
                else:
                    new_appear = raw_appear

                if new_appear and new_appear != job.get("appear_date"):
                    print(f"  [Employer Update Detected] {job.get('company')} | {job.get('title')}: {job.get('appear_date')} -> {new_appear}")
                    job["appear_date"] = new_appear
                    job["scraped_at"] = now_str
                    job["crawl_date"] = today_str
                    stats["date_updated"] += 1
            elif resp.status_code in [404, 410]:
                if record_closed_observation(job, today_str):
                    stats["closed"] += 1
                    print(f"  [Job Closed] {job.get('company')} | {job.get('title')} (HTTP {resp.status_code} x3)")
        except Exception:
            pass
    print(f"[Active Refresh Complete] Checked: {stats['checked']}, Dates Updated: {stats['date_updated']}, Closed: {stats['closed']}, Open: {stats['still_open']}\n")
    return stats


def get_job_region(location_str: str) -> str:
    """Normalize location text into standard Taiwan regions."""
    loc = (location_str or "").strip()
    if not loc:
        return ""
    if any(k in loc for k in ["苗栗", "台中", "臺中", "彰化", "南投", "雲林"]):
        return "中部"
    if any(k in loc for k in ["嘉義", "台南", "臺南", "高雄", "屏東"]):
        return "南部"
    if any(k in loc for k in ["花蓮", "台東", "臺東", "澎湖", "金門", "連江"]):
        return "東部/離島"
    if any(k in loc for k in ["遠端", "在家", "remote"]):
        return "全遠端"
    return "北部"


def recent_search_item(item: Dict[str, Any], cutoff: datetime.date) -> bool:
    """Keep only 104 search results whose appearance date is within the recent window."""
    raw_date = str(item.get("appearDate") or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(raw_date, fmt).date() >= cutoff
        except ValueError:
            continue
    return False


def process_single_api_job(
    item: Dict[str, Any],
    context: Any,
    scraped_jobs: List[Dict[str, Any]],
    seen_job_urls: set,
    target_companies: List[Dict[str, Any]],
    subsidiaries_dict: Dict[str, str],
) -> bool:
    cust_name = (item.get("custName") or "").strip()
    job_name = (item.get("jobName") or "").strip()

    # 1. STRICT INTERNSHIP TITLE GUARD
    if not match_internship_title(job_name):
        return False

    # 2. MATCH AGAINST ALL LISTED (TWSE) & OTC (TPEx) ENTERPRISES
    is_matched, stock_code, index_label, parent_comp, comp_en = match_company_whitelist(
        cust_name, target_companies, subsidiaries_dict
    )
    # The matcher also recognizes affiliated subsidiaries for older project use.
    # This crawler's approved scope is the listed/OTC issuer as the actual employer.
    if not is_matched or parent_comp or not is_issuer_employer(cust_name, stock_code, target_companies):
        if cust_name and cust_name not in UNMATCHED_COMPANIES:
            UNMATCHED_COMPANIES[cust_name] = {
                "company": cust_name,
                "sample_title": job_name,
                "seen_at": datetime.date.today().isoformat(),
            }
        return False

    raw_link = (item.get("link", {}) if isinstance(item.get("link"), dict) else {}).get("job") or item.get("jobNo") or ""
    if str(raw_link).startswith("//"):
        clean_url = f"https:{raw_link}"
    elif str(raw_link).startswith("http"):
        clean_url = str(raw_link)
    elif raw_link:
        clean_url = f"https://www.104.com.tw/job/{raw_link}"
    else:
        return False

    clean_url = clean_url.split("?")[0].rstrip("/")

    raw_appear = str(item.get("appearDate") or "")
    if len(raw_appear) == 8 and raw_appear.isdigit():
        new_appear = f"{raw_appear[:4]}-{raw_appear[4:6]}-{raw_appear[6:8]}"
    elif "/" in raw_appear:
        new_appear = raw_appear.replace("/", "-")
    else:
        new_appear = raw_appear or ""

    today_str = datetime.date.today().isoformat()

    if clean_url in seen_job_urls:
        for existing_job in scraped_jobs:
            if existing_job.get("url", "").split("?")[0].rstrip("/") == clean_url:
                existing_job["last_seen_date"] = today_str
                existing_job["status"] = "open"
                existing_job["miss_count"] = 0
                existing_job["last_miss_date"] = None
                if new_appear and new_appear != existing_job.get("appear_date"):
                    print(f"    [Date Updated via Search] {job_name}: {existing_job.get('appear_date')} -> {new_appear}")
                    existing_job["appear_date"] = new_appear
                    existing_job["scraped_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    existing_job["crawl_date"] = today_str
                break
        return False

    seen_job_urls.add(clean_url)
    job_no = item.get("jobNo", "") or clean_url.rstrip("/").split("/")[-1]
    salary_desc = item.get("salaryDesc", "待遇面議")
    location = item.get("jobAddrNoDesc", "")

    # Fetch Real JD
    print(f"    [Detail] Fetching {clean_url} [{index_label}] {cust_name}...")
    raw_description = ""
    try:
        time.sleep(3.5)
        raw_description = fetch_job_detail_http(clean_url)
        if raw_description:
            print(f"    [Detail] Got {len(raw_description)} chars of raw JD via HTTP")
    except Exception as fetch_err:
        print(f"    [Notice] Detail fetch fallback for {clean_url}: {fetch_err}")

    if not raw_description or len(raw_description.strip()) < 15:
        item_desc = str(item.get("description") or "").strip()
        if len(item_desc) < 15:
            seen_job_urls.discard(clean_url)
            print(f"    [Detail] No usable source description for {clean_url}; skipping")
            return False
        raw_description = item_desc

    # Run analyzer
    analysis = analyze_internship_jd(
        job_title=job_name,
        company=cust_name,
        raw_description=raw_description,
        location_desc=location,
        salary_desc=salary_desc,
        use_gemini=False,
    )

    community_links = {}  # Only manually reviewed article links may be published.

    appear_date = new_appear if new_appear else time.strftime("%Y-%m-%d")
    scraped_at = time.strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "job_id": f"104_{job_no}",
        "url": clean_url,
        "company": cust_name,
        "company_en": comp_en or cust_name,
        "stock_code": stock_code or "",
        "index_type": index_label,
        "domain": analysis.get("domain", "專案管理 / 策略營運"),
        "region": get_job_region(location),
        "parent_company": parent_comp,
        "industry": item.get("indcatDesc", "科技製造與資訊服務業"),
        "title": job_name,
        "title_zh": job_name,
        "title_en": analysis.get("title_en", job_name),
        "role_type": "Intern",
        "location": location,
        "salary_desc": salary_desc,
        "experience_desc": "",
        "status": "open",
        "first_seen_date": today_str,
        "last_seen_date": today_str,
        "appear_date": appear_date,
        "scraped_at": scraped_at,
        "crawl_date": today_str,
        "closed_date": None,
        "miss_count": 0,
        "ai_status": analysis.get("ai_status", "pending"),
        "ai_model": analysis.get("ai_model"),
        "raw_description": raw_description,
        "education_req": {"verified": False},
        "job_duties": analysis.get("job_duties") or analysis.get("duties", []),
        "job_duties_en": analysis.get("job_duties_en", []),
        "recommended_courses": analysis.get("recommended_courses", []),
        "trait_advice": analysis.get("trait_advice", ""),
        "trait_advice_en": analysis.get("trait_advice_en", ""),
        "bilingual_ksa": analysis.get("bilingual_ksa"),
        "jd_summary": analysis.get("jd_summary"),
        "collaborators": analysis.get("collaborators", []),
        "core_dimensions": analysis.get("core_dimensions", []),
        "discussion_links": community_links,
    }

    scraped_jobs.append(record)
    print(f"  [Found New Internship] {job_name} | {cust_name} ({stock_code}) [{index_label}]")
    print(f"    104 URL: {clean_url}")
    return True


def save_unmatched_companies():
    if not UNMATCHED_COMPANIES:
        return
    existing = []
    if UNMATCHED_FILE.exists():
        try:
            with open(UNMATCHED_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    existing = loaded
        except Exception:
            pass
    by_name = {item["company"]: item for item in existing if isinstance(item, dict) and "company" in item}
    by_name.update(UNMATCHED_COMPANIES)
    with open(UNMATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(by_name.values()), f, ensure_ascii=False, indent=2)


def crawl_live_internships(max_companies: Optional[int] = None, max_jobs: Optional[int] = None) -> List[Dict[str, Any]]:
    print("=== Starting 104 Verified Live Internship Crawler ===")
    deadline = time.monotonic() + max(1, int(os.getenv("MAX_CRAWL_SECONDS_PER_RUN", "14400")))

    with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
        target_companies = json.load(f)

    if max_companies:
        target_companies = target_companies[:max_companies]

    total_comps = len(target_companies)
    print(f"[Config] Scanning against {total_comps} Listed (TWSE) & OTC (TPEx) target enterprises...")

    # Load existing verified jobs if present so we can merge
    scraped_jobs = []
    seen_job_urls = set()
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                for j in old_data.get("jobs", []):
                    if j.get("index_type") == "上櫃富櫃 50":
                        j["index_type"] = "富櫃 50"
                    clean_u = j.get("url", "").split("?")[0].rstrip("/")
                    if clean_u:
                        seen_job_urls.add(clean_u)
                        scraped_jobs.append(j)
            print(f"[Baseline] Loaded {len(scraped_jobs)} existing verified jobs.")
        except Exception:
            pass

    initial_job_count = len(scraped_jobs)

    # Check the broad search before spending time refreshing existing records.
    preflight_items = fetch_104_search_api(None, page=1, order=15)
    if not preflight_items:
        if PLAYWRIGHT_MANAGER is not None:
            PLAYWRIGHT_MANAGER.close()
        raise RuntimeError("104 broad search returned zero results; refusing to refresh or publish")

    subsidiaries_dict = {}
    if SUBSIDIARIES_FILE.exists():
        try:
            with open(SUBSIDIARIES_FILE, "r", encoding="utf-8") as sf:
                subsidiaries_dict = json.load(sf)
        except Exception:
            pass

    total_raw_items_seen = 0

    try:
        max_pages = max(1, min(20, int(os.getenv("MAX_104_SEARCH_PAGES_PER_RUN", "20"))))
        recent_days = max(1, min(30, int(os.getenv("RECENT_JOB_DAYS", "7"))))
        recent_cutoff = datetime.date.today() - datetime.timedelta(days=recent_days)
        print(f"\n[Daily Search] Looking back {recent_days} days, at most {max_pages} pages; stopping after 2 pages without recent listings.")
        print(f"[Strategy 1] Matching against all {total_comps} Listed (TWSE), OTC (TPEx), TW50, Mid 100, and TPEx 50 companies...")

        pages_without_recent = 0
        for page_idx in range(1, max_pages + 1):
            if time.monotonic() >= deadline:
                raise RuntimeError("Crawler time limit reached during daily search")
            api_items = preflight_items if page_idx == 1 else fetch_104_search_api(None, page=page_idx, order=15)
            if not api_items:
                print(f"  [Search] No more results at page {page_idx}; stopping.")
                break

            total_raw_items_seen += len(api_items)
            recent_items = [item for item in api_items if recent_search_item(item, recent_cutoff)]
            pages_without_recent = 0 if recent_items else pages_without_recent + 1
            sweep_found = 0
            for item in recent_items:
                if process_single_api_job(item, None, scraped_jobs, seen_job_urls, target_companies, subsidiaries_dict):
                    sweep_found += 1

            print(f"  [Daily Search] Page {page_idx}: {len(recent_items)}/{len(api_items)} recent listings; {sweep_found} new issuer internships.")
            if pages_without_recent >= 2:
                print("  [Daily Search] Two consecutive pages had no recent listings; stopping.")
                break
            if page_idx < max_pages:
                time.sleep(3.5)

    finally:
        if PLAYWRIGHT_MANAGER is not None:
            PLAYWRIGHT_MANAGER.close()

    new_added = len(scraped_jobs) - initial_job_count
    print(f"\n=== Crawl Summary ===")
    print(f"  Raw 104 listings scanned : {total_raw_items_seen}")
    print(f"  Existing jobs preserved  : {initial_job_count}")
    print(f"  Newly added internships  : {new_added}")
    print(f"  Total verified jobs in DB: {len(scraped_jobs)}")
    if total_raw_items_seen == 0:
        raise RuntimeError("0 raw listings returned from 104; refusing to publish an unverified crawl")

    save_unmatched_companies()
    update_database_and_csv(scraped_jobs)

    return scraped_jobs


def update_database_and_csv(new_jobs: List[Dict[str, Any]]):
    """
    Saves authentic scraped records into data.json and google_sheets_import.csv.
    """
    if not new_jobs:
        return

    stage_raw_descriptions(new_jobs, PRIVATE_DESCRIPTIONS_FILE)

    db_data = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "meta": {
            "title": "104 台灣 50 / 中型 100 / 富櫃 50 與上市櫃企業實習雷達",
            "target_scope": "全台上市 (TWSE)、上櫃 (TPEx)、台灣 50 (0050)、中型 100 (0051) 與富櫃 50 指標企業實習",
            "total_jobs": len(new_jobs),
            "google_sheet_sync": "https://docs.google.com/spreadsheets/d/1wv5PEYIZk7S-bJP1M7S1XPKvXCXAwEqtBFPcFNmZMDI/edit?usp=sharing",
        },
        "jobs": new_jobs,
    }

    atomic_save_json(DATA_FILE, db_data)

    csv_headers = [
        "job_id", "公司名稱", "股票代號", "成分股指數", "專業領域", "實習地區", "職缺名稱", "實習地點",
        "實習待遇", "條件要求", "工作職責一", "工作職責二", "工作職責三",
        "建議先修大學課程", "特質建議", "104原始連結", "Dcard避雷連結", "PTT評價連結",
        "狀態", "104職缺更新日期", "抓到資料的時間"
    ]

    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for j in new_jobs:
            duties = j.get("job_duties", [])
            d1 = duties[0] if len(duties) > 0 else ""
            d2 = duties[1] if len(duties) > 1 else ""
            d3 = duties[2] if len(duties) > 2 else ""
            courses = "、".join(j.get("recommended_courses", []))
            disc = j.get("discussion_links") or {}
            writer.writerow([
                j.get("job_id"),
                j.get("company"),
                j.get("stock_code"),
                j.get("index_type"),
                j.get("domain") or "",
                j.get("region") or get_job_region(j.get("location", "")),
                j.get("title"),
                j.get("location"),
                j.get("salary_desc"),
                j.get("experience_desc"),
                d1, d2, d3,
                courses,
                j.get("trait_advice"),
                j.get("url"),
                disc.get("dcard_url") or "",
                disc.get("ptt_url") or "",
                j.get("status"),
                j.get("appear_date"),
                j.get("scraped_at"),
            ])


if __name__ == "__main__":
    crawl_live_internships()
