"""
Playwright 104 Real Internship Crawler Test
Uses Chromium to load 104 search pages, resolve Cloudflare Turnstile automatically,
and extract authentic internship job postings via both API interception and Vue 3 DOM (.info-container).
"""
import os
import sys
import json
import time

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
        is_ci = os.getenv("CI", "").lower() == "true" or sys.platform != "win32"
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
        try:
            if not is_ci:
                browser = p.chromium.launch(channel="chrome", headless=False, args=launch_args)
            else:
                browser = p.chromium.launch(headless=True, args=launch_args)
        except Exception:
            browser = p.chromium.launch(headless=True, args=launch_args)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-TW",
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-TW', 'zh', 'en-US', 'en'] });
        """)

        intercepted_jobs = []

        def handle_response(response):
            if ("jobs/search/api/jobs" in response.url or "jobs/search/list" in response.url) and response.status == 200:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct.lower():
                        return
                    payload = response.json()
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

                    for j in job_list:
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
                                "location": j.get("jobAddrNoDesc") or j.get("location"),
                            })
                except Exception as e:
                    print(f"[Parse Error] {e}")

        page.on("response", handle_response)

        target_query = "研華 實習"
        target_url = f"https://www.104.com.tw/jobs/search/?keyword={target_query}"
        print(f"[Navigating] Loading {target_url}...")

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_selector(".info-container", timeout=8000)
            except Exception:
                time.sleep(3)
        except Exception as e:
            print(f"[Notice] Page load finished with notice: {e}")

        print(f"[Page Title] {page.title()}")
        print(f"[Page URL] {page.url}")

        # Extract jobs from 104 Vue 3 DOM (.info-container) if API wasn't intercepted directly
        if not intercepted_jobs:
            print("[DOM Parsing] Extracting jobs from 104 Vue 3 DOM (.info-container)...")
            cards = page.query_selector_all(".info-container, article, .job-list-item, div.b-block")
            for c in cards:
                title_el = c.query_selector(".info-job__text, .b-tit a")
                comp_el = c.query_selector(".info-company__text, .b-list-inline a")
                if title_el and comp_el:
                    title = (title_el.get_attribute("title") or title_el.inner_text()).strip()
                    company = comp_el.inner_text().strip()
                    href = title_el.get_attribute("href")
                    if href and href.startswith("//"):
                        href = "https:" + href
                    tags = [t.inner_text().strip() for t in c.query_selector_all(".info-tags__text")]
                    intercepted_jobs.append({
                        "title": title,
                        "company": company,
                        "job_url": href,
                        "location": tags[0] if tags else "",
                        "salary": next((t for t in tags if any(k in t for k in ["時薪", "月薪", "面議", "元"])), ""),
                    })

        print(f"\n=== Test Result: Found {len(intercepted_jobs)} jobs via Playwright ===")
        for idx, j in enumerate(intercepted_jobs[:10], 1):
            print(f"{idx}. {j['title']} | {j['company']} | {j.get('location', '')} | {j.get('salary', '')}")
            print(f"   URL: {j['job_url']}")

        browser.close()
        return len(intercepted_jobs) > 0


if __name__ == "__main__":
    success = run_playwright_test()
    sys.exit(0 if success else 1)
