"""
Playwright 104 Real Internship Crawler Test
Uses headless Chromium to load 104 search pages, resolve Cloudflare Turnstile automatically,
and intercept or extract authentic internship job postings.
"""
import sys
import json
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_playwright_test():
    try:
        from playwright.sync_api import sync_playwright
        print("[Status] Playwright is installed. Launching Chromium...")
    except ImportError:
        print("[Error] Playwright is not installed in the current Python environment.")
        print("[Action Required] Need to run: pip install playwright && playwright install chromium")
        return False

    with sync_playwright() as p:
        # Launch real installed Google Chrome
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-TW"
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.navigator.chrome = {
                runtime: {}
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-TW', 'zh', 'en-US', 'en']
            });
        """)

        intercepted_jobs = []
        intercepted_requests = []
        def handle_response(response):
            if "jobs/search/api/jobs" in response.url:
                print(f"[API CHECK] Status: {response.status} | URL: {response.url}")
                if response.status == 400:
                    try:
                        print(f"[400 Body] {response.body().decode('utf-8')}")
                    except Exception as e:
                        print(f"[400 Error reading] {e}")
            if "jobs/search/api/jobs" in response.url and response.status == 200 and "keyword=" in response.url:
                print(f"[API HIT 200 KEYWORD] {response.url[:100]}")
                try:
                    raw_bytes = response.body()
                    payload = json.loads(raw_bytes.decode("utf-8"))
                    print(f"[Payload Type] {type(payload)}, keys: {list(payload.keys()) if isinstance(payload, dict) else 'N/A'}")
                    if isinstance(payload, list):
                        job_list = payload
                    elif isinstance(payload, dict):
                        d = payload.get("data")
                        if isinstance(d, list):
                            job_list = d
                        elif isinstance(d, dict):
                            job_list = d.get("list", [])
                        else:
                            job_list = payload.get("jobs", [])
                    else:
                        job_list = []
                    
                    print(f"[Success] Extracted {len(job_list)} raw jobs from 104!")
                    for j in job_list[:10]:
                        if isinstance(j, dict):
                            raw_link = j.get("link", {}).get("job") or j.get("jobNo") or ""
                            if str(raw_link).startswith("//"):
                                clean_url = f"https:{raw_link}"
                            elif str(raw_link).startswith("http"):
                                clean_url = str(raw_link)
                            elif raw_link:
                                clean_url = f"https://www.104.com.tw/job/{raw_link}"
                            else:
                                clean_url = None
                            
                            intercepted_jobs.append({
                                "title": j.get("jobName") or j.get("title"),
                                "company": j.get("custName") or j.get("companyName"),
                                "job_url": clean_url,
                                "salary": j.get("salaryDesc"),
                                "location": j.get("jobAddrNoDesc") or j.get("location")
                            })
                except Exception as e:
                    print(f"[Parse Error] {e}")

        page.on("response", handle_response)

        target_query = "研華 實習"
        target_url = f"https://www.104.com.tw/jobs/search/?keyword={target_query}"
        print(f"[Navigating] Loading {target_url}...")

        try:
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)
        except Exception as e:
            print(f"[Notice] Page load timeout or finished with: {e}")

        print(f"[Network Requests] Total {len(intercepted_requests)} requests. Looking for API calls:")
        for r in intercepted_requests:
            if any(k in r for k in ["list", "ajax", "api", "query", "search/"]):
                print(f"  -> {r}")

        print(f"[Page Title] {page.title()}")
        print(f"[Page URL] {page.url}")
        with open("scripts/playwright_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"[Debug] Saved page content to scripts/playwright_debug.html (Length: {len(page.content())})")

        # Check DOM if API wasn't intercepted directly
        if not intercepted_jobs:
            print("[DOM Parsing] Extracting jobs directly from rendered DOM elements...")
            cards = page.query_selector_all("article, .job-list-item, div.b-block")
            for c in cards:
                title_el = c.query_selector(".b-tit a, .info-job__text")
                comp_el = c.query_selector(".b-list-inline a, .info-company__text")
                if title_el and comp_el:
                    title = title_el.inner_text().strip()
                    company = comp_el.inner_text().strip()
                    href = title_el.get_attribute("href")
                    if href and href.startswith("//"):
                        href = "https:" + href
                    intercepted_jobs.append({
                        "title": title,
                        "company": company,
                        "job_url": href
                    })

        print(f"\n=== Test Result: Found {len(intercepted_jobs)} jobs via Playwright ===")
        for idx, j in enumerate(intercepted_jobs[:5], 1):
            print(f"{idx}. {j['title']} | {j['company']}")
            print(f"   URL: {j['job_url']}")

        browser.close()
        return len(intercepted_jobs) > 0

if __name__ == "__main__":
    success = run_playwright_test()
    sys.exit(0 if success else 1)
