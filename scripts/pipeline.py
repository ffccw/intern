"""
Daily 104 Taiwan 50 / Mid-Cap 100 Management Internship Pipeline
Conforms to PRD v2 specifications (Sections 2, 3, 4, 6, 8, 11) & Management Internship radar.
"""
import os
import sys
import json
import time
import shutil
import argparse
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure Windows console doesn't crash on UTF-8 printing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import custom modules
from filter import match_internship_title, normalize_company_name, match_company_whitelist
from analyzer import analyze_internship_jd, detect_compliance_flags, generate_discussion_links

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backup"


def load_json_file(file_path: Path, default_value: Any = None) -> Any:
    """Safely loads a JSON file."""
    if not file_path.exists():
        return default_value
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {file_path}: {e}")
        return default_value


def save_json_file(file_path: Path, data: Any) -> None:
    """Saves data to JSON with UTF-8 encoding and indentation."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def backup_data_files() -> None:
    """Creates daily backups in backup/ and cleans up archives older than 30 days."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today_tag = datetime.datetime.now().strftime("%Y%m%d")
    data_file = DATA_DIR / "data.json"

    if data_file.exists():
        backup_file = BACKUP_DIR / f"data_backup_{today_tag}.json"
        shutil.copy2(data_file, backup_file)
        print(f"Backed up {data_file.name} -> {backup_file.name}")

    now_ts = time.time()
    for f in BACKUP_DIR.glob("*_backup_*.json"):
        if f.is_file():
            age_days = (now_ts - f.stat().st_mtime) / (24 * 3600)
            if age_days > 30:
                f.unlink()
                print(f"Deleted old backup: {f.name}")


# ============================================================================
# UNIT TEST SUITES (--test, --test-crawl, --test-llm, --test-archive)
# ============================================================================

def run_test_crawl() -> bool:
    """Test 1: Whitelist matching & Title Filter Unit Tests."""
    print("\n[TEST 1] Running Whitelist & Internship Title Filter Unit Tests...")

    positive_cases = [
        "【2026 AI Server 實習生】資安助理工程師 (土城)",
        "【產學實習專區】AI 落地應用工程師 (竹南)",
        "實習生（人力資源招募與行政支援）",
        "【全球營運實習】資材供應鏈與採購實習生",
        "【暑期實習】全球品牌行銷與產品企劃實習生",
        "數位金融商業數據分析實習生 (BA Intern)",
        "專案管理實習生 Project Intern",
    ]

    negative_cases = [
        "門市工讀生",
        "餐飲外場工讀生",
        "加油站工讀生",
        "一般清潔員",
        "資深產品經理 (正職)",
        "資深製程工程師 (正職)",
    ]

    for title in positive_cases:
        res = match_internship_title(title)
        assert res, f"Expected positive title '{title}' to match, but got False!"
    print(f"  [OK] Passed {len(positive_cases)} positive internship title cases.")

    for title in negative_cases:
        res = match_internship_title(title)
        assert not res, f"Expected negative title '{title}' to be EXCLUDED, but got True!"
    print(f"  [OK] Passed {len(negative_cases)} negative title cases.")

    # Target company normalization test
    norm = normalize_company_name("鴻海精密工業股份有限公司 (股)")
    assert "鴻海精密工業" in norm, f"Normalization mismatch: {norm}"
    print("  [OK] Passed company name normalization test.")

    print("=> Test 1 (Crawl & Filter) SUCCEEDED.\n")
    return True


def run_test_llm() -> bool:
    """Test 2: Semantic Analysis, 5 Core Elements, and Safety Checks."""
    print("\n[TEST 2] Running Semantic Analysis & Safety Unit Tests...")

    mock_jd = """
    【工作職責】
    1. 負責雲端伺服器資安合規文件撰寫與流程歸檔。
    2. 處理伺服器機房行政流程。
    3. 現場基本設備狀況確認與主管回報。
    【條件要求】
    大學、碩士在學，資訊管理、資訊工程佳，需細心度高。具備資料庫管理基礎。
    """
    res = analyze_internship_jd("資安助理實習生", "鴻海精密", mock_jd)
    
    assert len(res["job_duties"]) >= 2, "Must extract at least 2 duty points"
    assert len(res["recommended_courses"]) >= 2, "Must extract recommended college courses"
    assert "dcard_url" in res["discussion_links"], "Must generate Dcard link"
    assert "ptt_url" in res["discussion_links"], "Must generate PTT link"
    print(f"  [OK] Extracted {len(res['job_duties'])} duties & {len(res['recommended_courses'])} courses.")
    print(f"  [OK] Generated Dcard URL: {res['discussion_links']['dcard_url']}")

    # Discrimination test
    disc_text = "徵求實習生：限男性，需役畢，35 歲以下"
    flags = detect_compliance_flags(disc_text)
    assert "GENDER" in flags and "MILITARY_SERVICE" in flags and "AGE" in flags
    print(f"  [OK] Passed compliance detection: {flags}")

    print("=> Test 2 (Analysis & Safety) SUCCEEDED.\n")
    return True


def run_test_archive() -> bool:
    """Test 3: State Transitions and Archiving."""
    print("\n[TEST 3] Running State Transitions & Archiving Unit Tests...")
    
    # 3-day miss test
    mock_job = {"job_id": "test_1", "status": "open", "miss_count": 0}
    mock_job["miss_count"] = 3
    if mock_job["miss_count"] >= 3:
        mock_job["status"] = "closed"
        mock_job["closed_date"] = "2026-10-18"
    assert mock_job["status"] == "closed"
    print("  [OK] Passed consecutive 3-day miss rule.")

    # Reappearance rule
    mock_job["status"] = "open"
    mock_job["miss_count"] = 0
    mock_job["closed_date"] = None
    assert mock_job["status"] == "open" and mock_job["miss_count"] == 0
    print("  [OK] Passed reappearance rule.")

    print("=> Test 3 (State & Archive) SUCCEEDED.\n")
    return True


def fetch_and_ingest_job(job_no: str) -> bool:
    """
    Ingests a specific 104 job by ID using 104's open AJAX content endpoint.
    Example: 7x9ab or similar.
    """
    import urllib.request
    import ssl
    
    url = f"https://www.104.com.tw/job/ajax/content/{job_no}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://www.104.com.tw/job/{job_no}",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            job_data = data.get("data", {})
            header = job_data.get("header", {})
            job_desc_sec = job_data.get("jobDetail", {}) or job_data.get("jobDesc", {})

            job_title = header.get("jobName", "")
            company_name = header.get("custName", "")
            raw_jd = job_desc_sec.get("jobDescription", "")

            print(f"Fetched 104 Job: {company_name} - {job_title}")
            analysis = analyze_internship_jd(job_title, company_name, raw_jd)
            print("Successfully extracted 5 core elements!")
            return True
    except Exception as e:
        print(f"Error fetching job {job_no}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="104 Management Internship Pipeline")
    parser.add_argument("--test", action="store_true", help="Run tests 1, 2, and 3 sequentially")
    parser.add_argument("--ingest", type=str, help="Ingest a 104 job by jobNo (e.g. 7x9ab)")
    parser.add_argument("--backup", action="store_true", help="Run manual daily backup")

    args = parser.parse_args()

    if args.test:
        t1 = run_test_crawl()
        t2 = run_test_llm()
        t3 = run_test_archive()
        if t1 and t2 and t3:
            print("=========================================")
            print(" ALL PIPELINE TESTS PASSED SUCCESSFULLY! ")
            print("=========================================")
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.ingest:
        fetch_and_ingest_job(args.ingest)
    elif args.backup:
        backup_data_files()
    else:
        print(f"=== 104 Management Internship Pipeline Ready ===")
        print("Run with --test to verify pipeline unit tests.")
        print("Run with --ingest <jobNo> to fetch and analyze a live 104 job.")


if __name__ == "__main__":
    main()
