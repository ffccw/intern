"""
104 Taiwan 50 / Mid-Cap 100 / TPEx 50 / Listed & OTC Verified Live Internship Crawler
Features:
- Dual-Engine Search: TLS-impersonated API (curl_cffi) + Automatic Playwright Browser & Vue 3 DOM Fallback (.info-container)
- Syncs Cloudflare clearance cookies from Playwright to curl_cffi session automatically
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

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests as cffi_requests
    HAS_CURL_CFFI = False

HEADERS_104 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

CURL_SESSION = None
PLAYWRIGHT_MANAGER = None


def get_session():
    global CURL_SESSION
    if CURL_SESSION is None:
        if HAS_CURL_CFFI:
            CURL_SESSION = cffi_requests.Session(impersonate="chrome124")
            try:
                CURL_SESSION.get(
                    "https://www.104.com.tw/jobs/search/?keyword=%E5%AF%A6%E7%BF%92&order=15",
                    headers=HEADERS_104,
                    timeout=8,
                )
            except Exception:
                pass
        else:
            CURL_SESSION = cffi_requests.Session()
    return CURL_SESSION


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
from filter import match_company_whitelist, match_internship_title, normalize_company_name, INDEX_LABEL_MAP
from public_data import load_private_descriptions, private_file_for, stage_raw_descriptions
from storage import atomic_save_json

PRIVATE_DESCRIPTIONS_FILE = private_file_for(BASE_DIR)

UNMATCHED_COMPANIES: Dict[str, Dict[str, Any]] = {}


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
        title_el = c.select_one(".info-job__text")
        comp_el = c.select_one(".info-company__text")
        if not title_el or not comp_el:
            continue

        job_name = title_el.get("title") or title_el.get_text(strip=True)
        href = title_el.get("href") or ""
        if href.startswith("//"):
            href = "https:" + href
        clean_link = href.split("?")[0].rstrip("/")
        job_no = clean_link.split("/job/")[-1] if "/job/" in clean_link else ""

        cust_name = comp_el.get_text(strip=True)
        industry_el = c.select_one(".info-company-addon-type")
        industry_desc = industry_el.get_text(strip=True) if industry_el else "科技製造與資訊服務業"

        tags = [t.get_text(strip=True) for t in c.select(".info-tags__text") if t.get_text(strip=True)]
        location = tags[0] if len(tags) > 0 else ""
        salary_desc = "待遇面議"
        for t in tags:
            if any(k in t for k in ["時薪", "月薪", "年薪", "面議", "元"]):
                salary_desc = t
                break

        desc_el = c.select_one(".info-description")
        desc_text = desc_el.get_text(strip=True) if desc_el else ""

        extracted.append({
            "jobNo": job_no,
            "jobName": job_name,
            "custName": cust_name,
            "indcatDesc": industry_desc,
            "jobAddrNoDesc": location,
            "salaryDesc": salary_desc,
            "description": desc_text,
            "link": {"job": clean_link or href},
            "appearDate": datetime.date.today().strftime("%Y%m%d"),
        })

    return extracted


class Playwright104Fallback:
    """
    Manages a reusable Playwright browser context to bypass Cloudflare Turnstile/JS Challenge,
    sync clearance cookies back to curl_cffi, and extract jobs via network interception + Vue 3 DOM.
    """
    def __init__(self):
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.available = True

    def ensure_started(self) -> bool:
        if not self.available:
            return False
        if self.page is not None:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            is_ci = os.getenv("CI", "").lower() == "true" or sys.platform != "win32"
            launch_Args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            try:
                if not is_ci:
                    self.browser = self.pw.chromium.launch(
                        channel="chrome",
                        headless=True,
                        args=launch_Args,
                    )
                else:
                    self.browser = self.pw.chromium.launch(headless=True, args=launch_Args)
            except Exception:
                self.browser = self.pw.chromium.launch(headless=True, args=launch_Args)

            self.context = self.browser.new_context(
                user_agent=HEADERS_104["User-Agent"],
                viewport={"width": 1280, "height": 800},
                locale="zh-TW",
            )
            self.page = self.context.new_page()
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
            """)
            print("    [Playwright] Browser fallback engine initialized successfully.")
            return True
        except Exception as e:
            print(f"    [Playwright] Could not initialize browser fallback: {e}")
            self.available = False
            return False

    def search_jobs(self, keyword: str, page_num: int = 1, order: int = 15) -> List[Dict[str, Any]]:
        if not self.ensure_started():
            return []

        intercepted_items: List[Dict[str, Any]] = []

        def on_response(response):
            if ("jobs/search/api/jobs" in response.url or "jobs/search/list" in response.url) and response.status == 200:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct.lower():
                        payload = response.json()
                        data = payload.get("data", [])
                        items = data if isinstance(data, list) else data.get("list", [])
                        if items and isinstance(items, list):
                            intercepted_items.extend(items)
                except Exception:
                    pass

        self.page.on("response", on_response)
        search_url = (
            f"https://www.104.com.tw/jobs/search/"
            f"?ro=0&kwop=7&keyword={urllib.parse.quote(keyword)}"
            f"&expansionType=area,spec,com,job,wf,wktm&order={order}&asc=0&page={page_num}&mode=s&jobsource=2018indexpoc"
        )
        try:
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            try:
                self.page.wait_for_selector(".info-container", timeout=6000)
            except Exception:
                self.page.wait_for_timeout(2000)

            # Sync solved Cloudflare cookies back to curl_cffi session
            s = get_session()
            for ck in self.context.cookies():
                try:
                    s.cookies.set(ck["name"], ck["value"], domain=ck.get("domain", ".104.com.tw"))
                except Exception:
                    pass

            if intercepted_items:
                return intercepted_items

            # Parse Vue 3 DOM (.info-container) directly if XHR wasn't intercepted
            html = self.page.content()
            dom_items = parse_104_vue_dom_html(html)
            return dom_items
        except Exception as e:
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


def fetch_104_search_api(keyword: str, page: int = 1, order: int = 15) -> List[Dict[str, Any]]:
    """
    Queries 104 search API with JSON content-type verification.
    If blocked by Cloudflare HTML challenge or HTTP 400/403, automatically falls back
    to Playwright browser extraction & Vue 3 DOM (.info-container) parsing.
    """
    s = get_session()
    encoded_kw = urllib.parse.quote(keyword)
    req_headers = dict(HEADERS_104)
    req_headers["Referer"] = f"https://www.104.com.tw/jobs/search/?ro=0&keyword={encoded_kw}&order={order}&page={page}"

    # 1. Try 104 /jobs/search/list with full query params and X-Requested-With
    list_url = (
        f"https://www.104.com.tw/jobs/search/list"
        f"?ro=0&kwop=7&keyword={encoded_kw}"
        f"&expansionType=area,spec,com,job,wf,wktm"
        f"&page={page}&order={order}&asc=0&mode=s&jobsource=2018indexpoc"
    )
    try:
        r = s.get(list_url, headers=req_headers, timeout=10)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and "json" in ct:
            payload = r.json()
            data = payload.get("data", {})
            items = data if isinstance(data, list) else data.get("list", [])
            if items:
                return items
    except Exception:
        pass

    # 2. Try 104 /jobs/search/api/jobs endpoint
    api_url = (
        f"https://www.104.com.tw/jobs/search/api/jobs"
        f"?ro=0&kwop=7&keyword={encoded_kw}"
        f"&expansionType=area,spec,com,job,wf,wktm"
        f"&page={page}&order={order}&asc=0&mode=s&jobsource=2018indexpoc"
    )
    try:
        r = s.get(api_url, headers=req_headers, timeout=10)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and "json" in ct:
            payload = r.json()
            data = payload.get("data", [])
            items = data if isinstance(data, list) else data.get("list", [])
            if items:
                return items
    except Exception:
        pass

    # 3. Automatic Playwright + Vue 3 DOM Fallback when Cloudflare blocks raw HTTP
    pw_fallback = get_playwright_fallback()
    items = pw_fallback.search_jobs(keyword=keyword, page_num=page, order=order)
    return items


def fetch_job_detail_cffi(job_url: str) -> str:
    """
    Extracts raw work-content using TLS-impersonated direct query to 104 official content Ajax endpoint.
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
    cffi_res = fetch_job_detail_cffi(clean_url)
    if cffi_res and len(cffi_res.strip()) >= 20:
        return cffi_res.strip()
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
        time.sleep(0.05)
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
    if not is_matched:
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
        raw_description = fetch_job_detail_cffi(clean_url)
        if raw_description:
            print(f"    [Detail] Got {len(raw_description)} chars of raw JD via cffi")
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

    # Run active refresh on existing jobs first to detect closures & updated appear dates
    if scraped_jobs:
        previously_open = sum(job.get("status") == "open" for job in scraped_jobs)
        refresh_stats = refresh_active_jobs(scraped_jobs, deadline=deadline)
        if refresh_stats.get("closed", 0) > max(10, int(previously_open * 0.2)):
            raise RuntimeError("Abnormal number of jobs closed in one crawl; refusing to publish")
        if refresh_stats.get("date_updated", 0) > 0 or refresh_stats.get("closed", 0) > 0:
            print(f"[Active Refresh] Staged {refresh_stats['date_updated']} date update(s) & {refresh_stats['closed']} closure(s) for validation.")

    # Temporary source text may disappear between runs. Re-fetch pending jobs when needed.
    staged_descriptions = load_private_descriptions(PRIVATE_DESCRIPTIONS_FILE)
    pending_limit = max(1, int(os.getenv("MAX_LLM_PER_RUN", "50")))
    attempted_pending = 0
    for job in scraped_jobs:
        if time.monotonic() >= deadline:
            raise RuntimeError("Crawler time limit reached during pending job refresh")
        if attempted_pending >= pending_limit:
            break
        job_id = str(job.get("job_id") or "")
        if job.get("ai_status") == "done" or not job_id:
            continue
        if job.get("raw_description") or staged_descriptions.get(job_id):
            continue
        attempted_pending += 1
        try:
            raw = fetch_job_detail_cffi(job.get("url", ""))
            if raw and len(raw.strip()) >= 15:
                job["raw_description"] = raw
        except Exception as error:
            print(f"[Pending Detail] Could not refresh {job_id}: {error}")

    subsidiaries_dict = {}
    if SUBSIDIARIES_FILE.exists():
        try:
            with open(SUBSIDIARIES_FILE, "r", encoding="utf-8") as sf:
                subsidiaries_dict = json.load(sf)
        except Exception:
            pass

    total_raw_items_seen = 0

    try:
        # Strategy 1: Comprehensive Full-Market Sweep across all 1,991 Listed (TWSE) & OTC (TPEx) Enterprises
        market_sweep_queries = [
            ("實習", 25, 15),       # Latest updated internships
            ("實習", 15, 1),        # Relevance sorted internships
            ("intern", 20, 15),     # Tech & Multinational interns
            ("實習生", 20, 15),     # Campus programs
            ("研習生", 10, 15),     # R&D trainees
            ("工程實習", 15, 15),   # Engineering / Semiconductor
            ("軟體實習", 15, 15),   # Software / Cloud / AI
            ("研發實習", 10, 15),   # Tech R&D
            ("行銷實習", 10, 15),   # Marketing & Brand
            ("數據實習", 10, 15),   # Data & BI
            ("商業實習", 10, 15),   # Business Analysis
            ("專案實習", 10, 15),   # PM & Operations
            ("財務實習", 10, 15),   # Finance & Accounting
            ("人資實習", 10, 15),   # HR & Recruiting
            ("法務實習", 8, 15),    # Legal & IP
        ]
        print(f"\n[Strategy 1] Running full-market sweep across {len(market_sweep_queries)} internship categories...")
        print(f"[Strategy 1] Matching against all {total_comps} Listed (TWSE), OTC (TPEx), TW50, Mid 100, and TPEx 50 companies...")

        for gq, max_pages, order_val in market_sweep_queries:
            if time.monotonic() >= deadline:
                raise RuntimeError("Crawler time limit reached during market sweep")
            print(f"\n[Market Sweep] Query: '{gq}' (order={order_val}, scanning up to {max_pages} pages)...")
            for page_idx in range(1, max_pages + 1):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Crawler time limit reached during market sweep")
                api_items = fetch_104_search_api(gq, page=page_idx, order=order_val)
                if not api_items:
                    print(f"  [Search] No more results for '{gq}' at page {page_idx}, moving to next query.")
                    break

                total_raw_items_seen += len(api_items)
                sweep_found = 0
                for item in api_items:
                    if process_single_api_job(item, None, scraped_jobs, seen_job_urls, target_companies, subsidiaries_dict):
                        sweep_found += 1

                if sweep_found > 0:
                    print(f"  [Sweep Progress] Staged {sweep_found} new job(s) from '{gq}' p.{page_idx}, total now: {len(scraped_jobs)}")

                time.sleep(0.15)

        # Strategy 2: Flagship Target Enterprise Top-Up (TW50 / MID100 / TPEX50 leaders)
        flagship_checks = [
            "台積電", "聯發科", "鴻海", "華碩", "廣達", "富邦", "國泰", "台達電",
            "緯創", "研華", "微星", "技嘉", "宏碁", "欣興", "聯詠", "瑞昱", "群創",
            "日月光", "元大", "中信", "長榮", "玉山", "友達", "力積電", "智邦",
            "仁寶", "和碩", "英業達", "世界先進", "台新", "永豐", "兆豐", "光寶科",
            "群聯", "元太", "環球晶", "穩懋", "信驊", "力旺", "創意", "緯穎"
        ]
        print(f"\n[Strategy 2] Running targeted checks on {len(flagship_checks)} flagship enterprises...")
        for comp_name in flagship_checks:
            if time.monotonic() >= deadline:
                raise RuntimeError("Crawler time limit reached during company checks")
            search_query = f"{comp_name} 實習"
            api_items = fetch_104_search_api(search_query, page=1, order=15)
            if not api_items:
                api_items = fetch_104_search_api(search_query, page=1, order=1)

            total_raw_items_seen += len(api_items or [])
            topup_found = 0
            for item in (api_items or []):
                if process_single_api_job(item, None, scraped_jobs, seen_job_urls, target_companies, subsidiaries_dict):
                    topup_found += 1
            if topup_found > 0:
                print(f"  [Top-Up Progress] Staged {topup_found} new job(s) for {comp_name}, total now: {len(scraped_jobs)}")
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
