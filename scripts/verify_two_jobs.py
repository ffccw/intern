"""
Verification script: fetch real JD from 104 detail pages for the two test cases,
run through the fixed analyzer, and print job_duties side-by-side.
Pass criteria:
  1. Both raw_descriptions are non-empty and different from each other
  2. Both job_duties lists are non-empty and different from each other
"""
import sys
import os
import json
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from crawler import fetch_job_detail
from analyzer import analyze_internship_jd

TEST_JOBS = [
    {
        "name": "鴻海倉儲管理師",
        "url": "https://www.104.com.tw/job/940g9",
        "company": "鴻海精密工業股份有限公司",
        "title": "【2026 CABG Server 實習生】-倉儲管理師 實習生 (土城)",
    },
    {
        "name": "東元電機資安實習生",
        "url": "https://www.104.com.tw/job/8v85i",
        "company": "東元電機股份有限公司",
        "title": "【2027實習計畫-搶先獲得預聘機會!】（學期）資安實習生",
    },
]


def main():
    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-TW"
        )

        for job in TEST_JOBS:
            print(f"\n{'='*60}")
            print(f"  Testing: {job['name']}")
            print(f"  URL: {job['url']}")
            print(f"{'='*60}")

            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
            """)

            try:
                raw_description = fetch_job_detail(page, job["url"])
            except RuntimeError as e:
                print(f"  ❌ FETCH FAILED: {e}")
                results.append({**job, "raw_description": "", "job_duties": [], "error": str(e)})
                page.close()
                continue
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            print(f"\n  [raw_description] ({len(raw_description)} chars):")
            print("  " + "\n  ".join(raw_description[:500].split("\n")))
            if len(raw_description) > 500:
                print("  ... (truncated)")

            try:
                analysis = analyze_internship_jd(
                    job_title=job["title"],
                    company=job["company"],
                    raw_description=raw_description,
                )
            except ValueError as e:
                print(f"  ❌ ANALYZER ERROR: {e}")
                results.append({**job, "raw_description": raw_description, "job_duties": [], "error": str(e)})
                continue

            duties = analysis.get("job_duties", [])
            print(f"\n  [job_duties]:")
            for i, d in enumerate(duties, 1):
                print(f"  {i}. {d}")

            results.append({
                **job,
                "raw_description": raw_description,
                "job_duties": duties,
                "error": None,
            })

        browser.close()

    # ===== PASS/FAIL CHECKS =====
    print(f"\n{'='*60}")
    print("  VERIFICATION RESULTS")
    print(f"{'='*60}")

    if len(results) < 2:
        print("❌ Could not collect both results.")
        sys.exit(1)

    r1, r2 = results[0], results[1]

    ok = True

    # Check 1: raw_descriptions non-empty
    for r in results:
        if not r["raw_description"]:
            print(f"❌ [{r['name']}] raw_description is EMPTY")
            ok = False
        else:
            print(f"✅ [{r['name']}] raw_description: {len(r['raw_description'])} chars")

    # Check 2: raw_descriptions are different
    if r1["raw_description"] and r2["raw_description"]:
        if r1["raw_description"].strip() == r2["raw_description"].strip():
            print("❌ raw_descriptions are IDENTICAL — crawler is returning the same content")
            ok = False
        else:
            print("✅ raw_descriptions are DIFFERENT ✓")

    # Check 3: job_duties non-empty
    for r in results:
        if not r["job_duties"]:
            print(f"❌ [{r['name']}] job_duties is EMPTY")
            ok = False
        else:
            print(f"✅ [{r['name']}] job_duties: {len(r['job_duties'])} items")

    # Check 4: job_duties are different
    d1 = r1.get("job_duties", [])
    d2 = r2.get("job_duties", [])
    if d1 and d2:
        if d1 == d2:
            print("❌ job_duties are IDENTICAL — Gemini still using template!")
            ok = False
        else:
            print("✅ job_duties are DIFFERENT ✓")

    print()
    if ok:
        print("✅ ALL CHECKS PASSED — fix is verified.")
    else:
        print("❌ SOME CHECKS FAILED — see above.")
        sys.exit(1)

    # Print final comparison
    print(f"\n{'='*60}")
    print("  SIDE-BY-SIDE COMPARISON")
    print(f"{'='*60}")
    for r in results:
        print(f"\n【{r['name']}】")
        for i, d in enumerate(r.get("job_duties", []), 1):
            print(f"  {i}. {d}")


if __name__ == "__main__":
    main()
