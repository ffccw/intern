import json
import time
import requests
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "data.json"
CSV_FILE = BASE_DIR / "data" / "google_sheets_import.csv"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwnzrqJFhIxjaJKWjrftSnRM_6TNzxmKGuBjEKSkh2Br52Ywc0i2FPSDDSUeBlj9vLe/exec"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.104.com.tw/"
}

def main():
    print("=== Updating 104 Real appearDate & Crawl Timestamp ===")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    jobs = db.get("jobs", [])
    print(f"Loaded {len(jobs)} jobs from {DATA_FILE}")

    success_count = 0
    for idx, job in enumerate(jobs, 1):
        url = job.get("url", "")
        job_code = url.rstrip("/").split("/")[-1].split("?")[0]
        
        real_date = None
        if job_code and len(job_code) >= 4:
            api_url = f"https://www.104.com.tw/api/jobs/{job_code}"
            try:
                res = requests.get(api_url, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    raw_date = data.get("data", {}).get("header", {}).get("appearDate")
                    if raw_date:
                        real_date = raw_date.replace("/", "-")
            except Exception as e:
                pass
        
        if real_date:
            job["appear_date"] = real_date
            success_count += 1
            print(f"[{idx}/{len(jobs)}] {job.get('company')} | {job.get('title')[:15]} -> 104更新: {real_date}")
        else:
            print(f"[{idx}/{len(jobs)}] {job.get('company')} -> keeping appear_date: {job.get('appear_date')}")

        # Ensure "抓到資料的時間" (scraped_at) is explicitly recorded as 2026-10-18
        if not job.get("scraped_at"):
            job["scraped_at"] = "2026-10-18 23:28:33"
        job["crawl_date"] = "2026-10-18"

        time.sleep(0.15)

    print(f"\n=> Successfully calibrated {success_count}/{len(jobs)} jobs with real 104 dates!")

    # 1. Save data.json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print("Saved updated data/data.json")

    # 2. Update CSV with '104職缺更新日期' and '抓到資料的時間'
    csv_headers = [
        "job_id", "公司名稱", "股票代號", "成分股指數", "職缺名稱", "實習地點",
        "實習待遇", "學歷要求", "工作職責一", "工作職責二", "工作職責三",
        "建議先修大學課程", "特質建議", "104原始連結", "Dcard避雷連結", "PTT評價連結", 
        "狀態", "104職缺更新日期", "抓到資料的時間"
    ]

    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for j in jobs:
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
                j.get("title"),
                j.get("location"),
                j.get("salary_desc"),
                j.get("education_req", {}).get("level_desc") or "大學部在學（學士生）",
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
    print("Saved updated data/google_sheets_import.csv")

    # 3. Auto-sync to Google Sheet via Webhook
    try:
        print("[Cloud DB] Syncing updated real dates to Google Sheets...")
        resp = requests.post(
            WEBHOOK_URL,
            data=json.dumps(jobs, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            allow_redirects=True,
            timeout=30
        )
        print("Google Sheet Sync HTTP Status:", resp.status_code)
        print("Google Sheet Sync Response:", resp.text)
    except Exception as e:
        print("[Cloud DB] Google Sheet Sync error:", e)

if __name__ == "__main__":
    main()
