"""
Batch Reprocessor for all jobs in data/data.json
1. Identifies all jobs missing raw_description or needing authentic regeneration.
2. Crawls 104 detail page for real work content using fetch_job_detail (Ajax API + Playwright fallback).
3. Analyzes via Gemini with strict raw_description ground-truth enforcement.
4. Updates job_duties, recommended_courses, trait_advice, etc.
5. Checkpoint-saves data.json continuously.
6. Summarizes results: total reprocessed, list of failures (if any).
"""
import sys
import os
import json
import time
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

DATA_FILE = BASE_DIR / "data" / "data.json"


def main():
    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found!")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    jobs = db.get("jobs", [])
    total_jobs = len(jobs)
    print(f"Total jobs in database: {total_jobs}")

    # Identify jobs needing re-processing
    targets = []
    for idx, j in enumerate(jobs):
        raw_desc = (j.get("raw_description") or "").strip()
        # If raw_description is empty or less than 20 chars, it needs real crawling
        if not raw_desc or len(raw_desc) < 20:
            targets.append((idx, j))

    print(f"Jobs needing real raw_description & Gemini re-analysis: {len(targets)}")

    if not targets:
        print("All jobs already have valid raw_description!")
        return

    from playwright.sync_api import sync_playwright

    success_count = 0
    failed_jobs = []

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
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        for count, (job_idx, job) in enumerate(targets, 1):
            title = job.get("title", "")
            company = job.get("company", "")
            url = job.get("url", "")
            print(f"[{count}/{len(targets)}] Processing: {title} @ {company}")
            print(f"    URL: {url}")

            # Step 1: Fetch real JD
            raw_description = ""
            try:
                raw_description = fetch_job_detail(page=page, job_url=url)
            except Exception as e:
                print(f"    ❌ Crawl Failed: {e}")
                failed_jobs.append({
                    "title": title,
                    "url": url,
                    "company": company,
                    "error": str(e)
                })
                continue

            if not raw_description or len(raw_description.strip()) < 20:
                print("    ❌ Empty or too short raw_description extracted.")
                failed_jobs.append({
                    "title": title,
                    "url": url,
                    "company": company,
                    "error": "Extracted text was empty or too short"
                })
                continue

            print(f"    ✅ Fetched JD ({len(raw_description)} chars)")

            # Step 2: Analyze with Gemini / Analyzer
            try:
                analysis = analyze_internship_jd(
                    job_title=title,
                    company=company,
                    raw_description=raw_description,
                    location_desc=job.get("location", ""),
                    salary_desc=job.get("salary_desc", "")
                )
            except Exception as e:
                print(f"    ❌ Analyzer Failed: {e}")
                failed_jobs.append({
                    "title": title,
                    "url": url,
                    "company": company,
                    "error": f"Analyzer error: {e}"
                })
                continue

            # Step 3: Update job record in-memory
            job["raw_description"] = raw_description
            job["job_duties"] = analysis.get("job_duties") or analysis.get("duties", [])
            job["job_duties_en"] = analysis.get("job_duties_en", [])
            job["recommended_courses"] = analysis.get("recommended_courses", [])
            job["trait_advice"] = analysis.get("trait_advice", "")
            job["trait_advice_en"] = analysis.get("trait_advice_en", "")
            if analysis.get("title_en"):
                job["title_en"] = analysis.get("title_en")
            if analysis.get("jd_summary"):
                job["jd_summary"] = analysis.get("jd_summary")
            if analysis.get("bilingual_ksa"):
                job["bilingual_ksa"] = analysis.get("bilingual_ksa")
            if analysis.get("collaborators"):
                job["collaborators"] = analysis.get("collaborators")
            if analysis.get("core_dimensions"):
                job["core_dimensions"] = analysis.get("core_dimensions")
            job["ai_status"] = "done"

            success_count += 1
            print(f"    ✅ Successfully re-analyzed ({len(job['job_duties'])} duties)")

            # Step 4: Checkpoint save every job
            try:
                db["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"    ⚠️ Warning: checkpoint save failed: {e}")

            # Polite spacing for Gemini RPM limit & 104 server
            time.sleep(1.8)

        browser.close()

    # Final summary report
    print("\n" + "=" * 60)
    print("BATCH REPROCESSING COMPLETED")
    print("=" * 60)
    print(f"Total jobs evaluated: {len(targets)}")
    print(f"Successfully reprocessed: {success_count}")
    print(f"Failed to fetch raw_description: {len(failed_jobs)}")

    if failed_jobs:
        print("\n=== FAILED JOBS LIST ===")
        for f in failed_jobs:
            print(f"- Title: {f['title']}")
            print(f"  URL: {f['url']}")
            print(f"  Company: {f['company']}")
            print(f"  Reason: {f['error']}\n")
    else:
        print("\nAll jobs successfully fetched and reprocessed with authentic content!")


if __name__ == "__main__":
    main()
