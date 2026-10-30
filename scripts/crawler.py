"""
104 Taiwan 50 / Mid-Cap 100 / TPEx 50 Verified Live Internship Crawler
Bypasses Cloudflare automatically, enforces strict internship title rules,
eliminates non-intern full-time jobs, resolves company disambiguation (e.g. Phison vs UMC),
and saves checkpoint progress in real time.
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

sys.path.insert(0, str(BASE_DIR / "scripts"))
from analyzer import analyze_internship_jd
from filter import match_company_whitelist, normalize_company_name, INDEX_LABEL_MAP

COMMUNITY_CACHE: Dict[str, Dict[str, Optional[str]]] = {}


def search_community_reviews(company_name: str, short_name: str) -> Dict[str, Optional[str]]:
    """
    Search PTT and Dcard for genuine intern reviews.
    """
    cache_key = short_name or company_name
    if cache_key in COMMUNITY_CACHE:
        return COMMUNITY_CACHE[cache_key]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": "over18=1"
    }
    ptt_url = None
    dcard_url = None
    dcard_label = None

    # 1. PTT Search in Tech_Job
    try:
        query_kw = short_name or company_name[:4]
        ptt_req = urllib.request.Request(
            f"https://www.ptt.cc/bbs/Tech_Job/search?q={urllib.parse.quote(query_kw)}",
            headers=headers
        )
        with urllib.request.urlopen(ptt_req, timeout=3) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            matches = re.findall(r'<div class="title">\s*<a href="([^"]+)">([^<]+)</a>', html)
            if matches:
                for href, title in matches:
                    if any(k in title for k in ["實習", "面試", "心得", "請益"]):
                        ptt_url = f"https://www.ptt.cc{href}"
                        break
                if not ptt_url and matches:
                    ptt_url = f"https://www.ptt.cc{matches[0][0]}"
    except Exception:
        pass

    # 2. Dcard Search via DuckDuckGo
    try:
        ddg_kw = f"site:dcard.tw/f/ {short_name or company_name} 實習"
        ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(ddg_kw)}"
        ddg_req = urllib.request.Request(ddg_url, headers=headers)
        with urllib.request.urlopen(ddg_req, timeout=3) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            matches = re.findall(r'uddg=(https%3A%2F%2Fwww\.dcard\.tw%2Ff%2F[^&]+)', html)
            if matches:
                decoded = urllib.parse.unquote(matches[0])
                if "/p/" in decoded:
                    dcard_url = decoded
                    dcard_label = f"Dcard {short_name}實習心得"
    except Exception:
        pass

    result = {
        "dcard_label": dcard_label,
        "dcard_url": dcard_url,
        "ptt_url": ptt_url
    }
    COMMUNITY_CACHE[cache_key] = result
    return result


def fetch_job_detail(page=None, job_url: str = "") -> str:
    """
    Extracts the raw work-content text from 104 job detail page.
    Strategy 1: Fast direct query to 104 official content Ajax endpoint (/job/ajax/content/{job_no}).
    Strategy 2: Playwright DOM & XPath extraction if Ajax is blocked or returns empty.
    Returns stripped plain text or raises RuntimeError if all methods fail.
    """
    clean_url = job_url.split("?")[0].rstrip("/")
    job_no = clean_url.split("/")[-1]

    # Strategy 1: Direct 104 content API
    if job_no:
        try:
            api_url = f"https://www.104.com.tw/job/ajax/content/{job_no}"
            req = urllib.request.Request(
                api_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Referer": clean_url
                }
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                job_detail = data.get("data", {}).get("jobDetail", {})
                desc = job_detail.get("jobDescription", "").strip()
                condition = data.get("data", {}).get("condition", {})
                other = condition.get("other", "").strip()
                combined = desc
                if other:
                    combined += f"\n\n[其他條件]\n{other}"
                if len(combined.strip()) >= 20:
                    return combined.strip()
        except Exception:
            pass

    # Strategy 2: Playwright DOM extraction fallback
    if page is not None:
        try:
            page.goto(clean_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
        except Exception as e:
            raise RuntimeError(f"[fetch_job_detail] Failed to load {clean_url}: {e}")

        # Try to locate by visible heading text "工作內容" or "職務內容"
        for heading_text in ["工作內容", "職務內容", "工作職責", "工作說明"]:
            try:
                locator = page.locator(
                    f"//h2[contains(text(), '{heading_text}')]/..//p | "
                    f"//h3[contains(text(), '{heading_text}')]/..//p | "
                    f"//dt[contains(text(), '{heading_text}')]/../dd | "
                    f"//span[contains(text(), '{heading_text}')]/..//p"
                )
                count = locator.count()
                if count > 0:
                    texts = [locator.nth(i).inner_text().strip() for i in range(count)]
                    raw_text = "\n".join(t for t in texts if t)
                    if len(raw_text.strip()) >= 20:
                        return re.sub(r"\n{3,}", "\n\n", raw_text).strip()
            except Exception:
                pass

        # Try CSS selectors
        for sel in ["section.job-description-table", "div.job-description-table", "div.job-description", "[data-v-content]"]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    raw_text = el.inner_text().strip()
                    if len(raw_text) >= 20:
                        return re.sub(r"\n{3,}", "\n\n", raw_text).strip()
            except Exception:
                pass

        # Try embedded JSON in HTML
        try:
            content = page.content()
            for pattern in [
                r'"description"\s*:\s*"((?:[^"\\]|\\.)+)"',
                r'"jobDescription"\s*:\s*"((?:[^"\\]|\\.)+)"',
                r'"content"\s*:\s*"((?:[^"\\]|\\.){50,})"',
            ]:
                m = re.search(pattern, content)
                if m:
                    candidate = m.group(1).encode().decode("unicode_escape").strip()
                    candidate = re.sub(r"<[^>]+>", " ", candidate)
                    candidate = re.sub(r"\s+", " ", candidate).strip()
                    if len(candidate) > 30:
                        return candidate
        except Exception:
            pass

    raise RuntimeError(
        f"[fetch_job_detail] Could not extract work content from {clean_url}."
    )


def refresh_active_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Checks all existing active jobs against 104 official API to:
    1. Update appear_date when employers re-post or edit JDs (e.g. 10/14 -> 10/21)
    2. Detect closed/expired jobs (switch == 'off' or 404/410) and mark status='closed'
    3. Update last_seen_date to today
    """
    today_str = datetime.date.today().isoformat()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    stats = {"checked": 0, "date_updated": 0, "closed": 0, "still_open": 0}

    print(f"\n[Active Refresh] Checking {len(jobs)} existing jobs for 104 employer updates/closures...")
    for idx, job in enumerate(jobs, 1):
        if job.get("status") == "closed":
            continue

        url = job.get("url", "")
        job_no = url.rstrip("/").split("/")[-1].split("?")[0]
        if not job_no:
            continue

        stats["checked"] += 1
        api_url = f"https://www.104.com.tw/job/ajax/content/{job_no}"
        try:
            req = urllib.request.Request(
                api_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Referer": url
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                payload = data.get("data", {})
                is_on = payload.get("switch") == "on"

                if not is_on:
                    job["status"] = "closed"
                    job["closed_date"] = today_str
                    stats["closed"] += 1
                    print(f"  [Job Closed] {job.get('company')} | {job.get('title')} (switch=off)")
                    continue

                # Still open
                job["status"] = "open"
                job["last_seen_date"] = today_str
                job["miss_count"] = 0
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

        except urllib.error.HTTPError as e:
            if e.code in [404, 410]:
                job["status"] = "closed"
                job["closed_date"] = today_str
                stats["closed"] += 1
                print(f"  [Job Closed] {job.get('company')} | {job.get('title')} (HTTP {e.code})")
        except Exception:
            pass

        time.sleep(0.1)

    print(f"[Active Refresh Complete] Checked: {stats['checked']}, Dates Updated: {stats['date_updated']}, Closed: {stats['closed']}, Open: {stats['still_open']}\n")
    return stats




def get_job_region(location_str: str) -> str:
    """Normalize location text into standard Taiwan regions."""
    loc = (location_str or "").strip()
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
    cust_name = item.get("custName", "").strip()
    job_name = item.get("jobName", "").strip()

    # 1. STRICT INTERNSHIP TITLE GUARD
    job_lower = job_name.lower()
    is_intern = any(k in job_lower for k in ["實習", "intern", "工讀", "研習生"])
    if not is_intern:
        return False

    if any(k in job_name for k in ["資深", "正職", "主管", "處長", "副理", "協理"]) and "實習" not in job_name:
        return False

    if any(k in job_lower for k in ["限碩士", "碩士以上", "研究所在學限定"]):
        return False

    if any(k in job_name for k in ["門市工讀", "餐飲工讀", "加油員", "清潔員", "作業員", "產線包裝"]):
        return False

    # 2. MATCH AGAINST ALL LISTED & OTC ENTERPRISES
    is_matched, stock_code, index_label, parent_comp, comp_en = match_company_whitelist(
        cust_name, target_companies, subsidiaries_dict
    )
    if not is_matched:
        return False

    raw_link = item.get("link", {}).get("job") or item.get("jobNo") or ""
    if str(raw_link).startswith("//"):
        clean_url = f"https:{raw_link}"
    elif str(raw_link).startswith("http"):
        clean_url = str(raw_link)
    elif raw_link:
        clean_url = f"https://www.104.com.tw/job/{raw_link}"
    else:
        return False

    clean_url = clean_url.split("?")[0]

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
            if existing_job.get("url", "").split("?")[0] == clean_url:
                existing_job["last_seen_date"] = today_str
                existing_job["status"] = "open"
                existing_job["miss_count"] = 0
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
    detail_page = context.new_page()
    detail_page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
    """)
    try:
        raw_description = fetch_job_detail(detail_page, clean_url)
        print(f"    [Detail] Got {len(raw_description)} chars of raw JD")
    except RuntimeError as fetch_err:
        print(f"    [Warning] {fetch_err} — skipping job.")
        detail_page.close()
        seen_job_urls.discard(clean_url)
        return False
    finally:
        try:
            detail_page.close()
        except Exception:
            pass

    # Run analyzer
    analysis = analyze_internship_jd(
        job_title=job_name,
        company=cust_name,
        raw_description=raw_description,
        location_desc=location,
        salary_desc=salary_desc
    )

    community_links = search_community_reviews(cust_name, cust_name[:4])

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
        "location": location or "大台北地區 / 新竹園區",
        "salary_desc": salary_desc,
        "experience_desc": "大學部在學（學士生實習計畫）",
        "status": "open",
        "first_seen_date": today_str,
        "last_seen_date": today_str,
        "appear_date": appear_date,
        "scraped_at": scraped_at,
        "closed_date": None,
        "miss_count": 0,
        "ai_status": "pending",
        "raw_description": raw_description,
        "education_req": {
            "level": "ba",
            "level_desc": "大學部在學（學士生）",
            "majors": ["MAJ_BUS", "MAJ_CS", "MAJ_IE"],
            "major_required": False,
            "source": "104"
        },
        "job_duties": analysis.get("job_duties") or analysis.get("duties", []),
        "recommended_courses": analysis.get("recommended_courses", ["人工智慧與商業應用", "商管程式設計 / Python", "資料庫管理"]),
        "trait_advice": analysis.get("trait_advice", "適合具備團隊溝通熱忱、處事細心嚴謹並渴望累積企業實務經驗之同學。"),
        "discussion_links": community_links
    }

    scraped_jobs.append(record)
    print(f"  [Found Internship] {job_name} | {cust_name} [{index_label}]")
    print(f"    104 URL: {clean_url}")
    return True


def crawl_live_internships(max_companies: Optional[int] = None, max_jobs: Optional[int] = None) -> List[Dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    print("=== Starting 104 Verified Live Internship Crawler ===")
    
    with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
        target_companies = json.load(f)

    if max_companies:
        target_companies = target_companies[:max_companies]

    total_comps = len(target_companies)
    print(f"[Config] Scanning {total_comps} target enterprises...")

    # Load existing verified jobs if present so we can merge
    scraped_jobs = []
    seen_job_urls = set()
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                for j in old_data.get("jobs", []):
                    clean_u = j.get("url", "").split("?")[0]
                    if clean_u:
                        seen_job_urls.add(clean_u)
                        scraped_jobs.append(j)
            print(f"[Baseline] Preserving {len(scraped_jobs)} existing verified jobs.")
        except Exception:
            pass

    # Run active refresh on existing jobs first to detect closures & updated appear dates
    if scraped_jobs:
        refresh_stats = refresh_active_jobs(scraped_jobs)
        if refresh_stats.get("date_updated", 0) > 0 or refresh_stats.get("closed", 0) > 0:
            update_database_and_csv(scraped_jobs)
            print(f"[Active Refresh] Saved {refresh_stats['date_updated']} date update(s) & {refresh_stats['closed']} closure(s) to database.")

    is_ci = os.getenv("CI") == "true" or sys.platform != "win32"
    launch_kwargs = {
        "headless": is_ci or os.getenv("HEADLESS", "false").lower() == "true",
        "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    }
    if not is_ci:
        launch_kwargs["channel"] = "chrome"

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-TW"
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        current_api_jobs = []

        def handle_response(response):
            url = response.url
            if ("jobs/search/list" in url or "jobs/search/api/jobs" in url) and response.status == 200:
                try:
                    payload = json.loads(response.body().decode("utf-8", errors="ignore"))
                    d = payload.get("data")
                    items = []
                    if isinstance(d, dict):
                        items = d.get("list", [])
                    elif isinstance(d, list):
                        items = d
                    if items:
                        current_api_jobs.extend(items)
                        print(f"    [Net Intercept] Intercepted {len(items)} jobs from 104 search API ({url.split('?')[0]})")
                except Exception:
                    pass

        page.on("response", handle_response)

        subsidiaries_dict = {}
        if SUBSIDIARIES_FILE.exists():
            try:
                with open(SUBSIDIARIES_FILE, "r", encoding="utf-8") as sf:
                    subsidiaries_dict = json.load(sf)
            except Exception:
                pass

        # Split into priority index constituents (TW50, MID100, TPEX50) and broad pool
        priority_companies = [c for c in target_companies if c.get("index") in ("TW50", "MID100", "TPEX50")]
        print(f"[Strategy 1] Scanning {len(priority_companies)} flagship index constituents directly...")

        for idx, comp in enumerate(priority_companies, 1):
            if max_jobs and len(scraped_jobs) >= max_jobs:
                print(f"[Done] Reached maximum requested jobs limit: {max_jobs}")
                break

            short_name = comp.get("short_name", "")
            full_name = comp.get("name", "")
            raw_idx = comp.get("index", "")
            index_label = INDEX_LABEL_MAP.get(raw_idx, "上市")

            print(f"[{idx}/{len(priority_companies)}] Checking {full_name} ({short_name}) [{index_label}]...")

            current_api_jobs.clear()
            search_query = f"{short_name} 實習"
            target_url = f"https://www.104.com.tw/jobs/search/?keyword={urllib.parse.quote(search_query)}"

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                for _ in range(7):
                    if current_api_jobs:
                        break
                    page.wait_for_timeout(500)
            except Exception:
                page.wait_for_timeout(1000)

            comp_jobs_found = 0
            for item in current_api_jobs:
                if process_single_api_job(item, context, scraped_jobs, seen_job_urls, target_companies, subsidiaries_dict):
                    comp_jobs_found += 1

            if comp_jobs_found > 0:
                update_database_and_csv(scraped_jobs)
                print(f"  [Checkpoint] Database updated, total verified jobs now: {len(scraped_jobs)}")

        # Strategy 2: Deep full-market sweep across all 1,991 Listed (TWSE) and OTC (TPEx) enterprises
        # Multi-query sweep across high-yield internship categories
        market_sweep_queries = [
            ("實習", 25, 15),     # 25 pages latest updated
            ("實習", 15, 1),      # 15 pages relevance
            ("實習生", 20, 15),   # 20 pages
            ("intern", 20, 15),   # 20 pages
            ("研習生", 10, 15),   # 10 pages
            ("工程實習", 10, 15), # 10 pages engineering
            ("研發實習", 10, 15), # 10 pages R&D
        ]
        print(f"\n[Strategy 2] Running deep market sweep across {len(market_sweep_queries)} high-yield internship queries...")

        for gq, max_pages, order_val in market_sweep_queries:
            if max_jobs and len(scraped_jobs) >= max_jobs:
                break
            print(f"\n[Broad Sweep] Searching 104 for '{gq}' (order={order_val}, scanning up to {max_pages} pages)...")
            for page_idx in range(1, max_pages + 1):
                if max_jobs and len(scraped_jobs) >= max_jobs:
                    break
                current_api_jobs.clear()
                target_url = f"https://www.104.com.tw/jobs/search/?keyword={urllib.parse.quote(gq)}&page={page_idx}&order={order_val}"
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                    for _ in range(7):
                        if current_api_jobs:
                            break
                        page.wait_for_timeout(500)
                except Exception:
                    page.wait_for_timeout(1000)

                sweep_found = 0
                for item in current_api_jobs:
                    if process_single_api_job(item, context, scraped_jobs, seen_job_urls, target_companies, subsidiaries_dict):
                        sweep_found += 1

                if sweep_found > 0:
                    update_database_and_csv(scraped_jobs)
                    print(f"  [Sweep Checkpoint] Saved {sweep_found} new job(s) from page {page_idx}, total now: {len(scraped_jobs)}")

        browser.close()

    print(f"\n=> Successfully scraped {len(scraped_jobs)} LIVE internships from target companies!")
    update_database_and_csv(scraped_jobs)
    
    # Auto-sync to Google Sheets via Webhook
    try:
        from sync_to_sheets import sync
        print("[Cloud DB] Triggering automatic sync to Google Sheets...")
        sync()
    except Exception as e:
        print("[Cloud DB] Sync to Google Sheets notice:", e)

    return scraped_jobs


def update_database_and_csv(new_jobs: List[Dict[str, Any]]):
    """
    Saves authentic scraped records into data.json and google_sheets_import.csv.
    """
    if not new_jobs:
        return

    # Update data.json
    db_data = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "meta": {
            "title": "104 台灣 50 / 中型 100 / 富櫃 50 管院頂尖實習雷達",
            "target_scope": "台灣 50 (0050)、中型 100 (0051) 與上櫃富櫃 50 指標企業管理學院相關實習",
            "total_jobs": len(new_jobs),
            "google_sheet_sync": "https://docs.google.com/spreadsheets/d/1wv5PEYIZk7S-bJP1M7S1XPKvXCXAwEqtBFPcFNmZMDI/edit?usp=sharing"
        },
        "jobs": new_jobs
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)

    # Update google_sheets_import.csv
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
                j.get("domain") or "專案管理 / 策略營運",
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
                j.get("scraped_at")
            ])


if __name__ == "__main__":
    crawl_live_internships()
