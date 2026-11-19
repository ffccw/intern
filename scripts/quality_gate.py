"""
Quality Gate Validation Module
Validates data integrity, completeness, and authenticity before git commit and push.
Exits with code 0 on PASS, code 1 on FAIL.
"""
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse

try:
    from public_data import PENDING_ANALYSIS_FIELDS
except ImportError:
    from scripts.public_data import PENDING_ANALYSIS_FIELDS
try:
    from review_links import verified_review_links
except ImportError:
    from scripts.review_links import verified_review_links

CANNED_SOFTWARE_DUTY = "參與軟體模組功能開發、API 介接與系統架構維護作業"


def validate_public_backups(backup_dir: Path) -> bool:
    """Reject source descriptions in any backup slated for repository publication."""
    for backup in sorted(backup_dir.glob("data_backup_*.json")):
        try:
            with backup.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            jobs = data.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("jobs must be a list")
            if any(not isinstance(job, dict) or "raw_description" in job for job in jobs):
                print(f"[Quality Gate FAIL] Backup contains source descriptions: {backup.name}")
                return False
        except (OSError, ValueError) as error:
            print(f"[Quality Gate FAIL] Backup cannot be validated: {backup.name}: {error}")
            return False
    return True


def validate_data_json(file_path: Path, min_jobs: int = 300) -> bool:
    print(f"[Quality Gate] Validating {file_path} (min_jobs={min_jobs})...")

    if not file_path.exists():
        print(f"[Quality Gate FAIL] File does not exist: {file_path}")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Quality Gate FAIL] Invalid JSON syntax: {e}")
        return False

    if not isinstance(data, dict):
        print("[Quality Gate FAIL] Root JSON must be an object/dict.")
        return False

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        print("[Quality Gate FAIL] 'jobs' field must be a list.")
        return False

    total_jobs = len(jobs)
    print(f"[Quality Gate] Total jobs in file: {total_jobs}")

    if total_jobs < min_jobs:
        print(f"[Quality Gate FAIL] Total jobs ({total_jobs}) dropped below safety floor threshold ({min_jobs}). Scraper may have failed!")
        return False

    if data.get("meta", {}).get("total_jobs") != total_jobs:
        print("[Quality Gate FAIL] meta.total_jobs does not match the jobs list")
        return False

    # Check required fields
    required_fields = ["job_id", "company", "title", "url", "status"]
    corrupted_count = 0
    canned_mismatch_count = 0
    seen_ids = set()

    for idx, j in enumerate(jobs):
        if not isinstance(j, dict):
            corrupted_count += 1
            continue

        for rf in required_fields:
            if not j.get(rf):
                corrupted_count += 1
                break

        job_id = j.get("job_id")
        if job_id in seen_ids:
            print(f"[Quality Gate FAIL] Duplicate job_id: {job_id}")
            return False
        seen_ids.add(job_id)

        if "raw_description" in j:
            print(f"[Quality Gate FAIL] Source description is present in public record: {job_id}")
            return False

        if j.get("ai_status") != "done" and any(field in j for field in PENDING_ANALYSIS_FIELDS):
            print(f"[Quality Gate FAIL] Unverified analysis is present in public record: {job_id}")
            return False

        parsed_url = urlparse(str(j.get("url") or ""))
        if parsed_url.scheme != "https" or parsed_url.netloc != "www.104.com.tw" or parsed_url.query or parsed_url.fragment or not re.fullmatch(r"/job/[A-Za-z0-9]+", parsed_url.path):
            print(f"[Quality Gate FAIL] Job does not have a direct 104 URL: {job_id}")
            return False

        if j.get("status") not in ("open", "closed"):
            print(f"[Quality Gate FAIL] Invalid status for {job_id}")
            return False

        education = j.get("education_req") or {}
        if not isinstance(education, dict) or (education.get("verified") is not True and (education.get("level") or education.get("level_desc") or education.get("source"))):
            print(f"[Quality Gate FAIL] Unverified education requirement presented as source fact: {job_id}")
            return False

        links = j.get("discussion_links") or {}
        if links != verified_review_links(links):
            print(f"[Quality Gate FAIL] Unverified or search-page forum link: {job_id}")
            return False

        # Authenticity check: Ensure non-software jobs do not have canned software engineer template
        title_lower = (j.get("title") or "").lower()
        duties = j.get("job_duties") or []
        if CANNED_SOFTWARE_DUTY in duties:
            is_sw_title = any(k in title_lower for k in ["軟體", "開發", "工程師", "programmer", "software", "developer", "backend", "frontend", "韌體"])
            if not is_sw_title:
                canned_mismatch_count += 1
                print(f"[Quality Gate WARNING] Job '{j.get('title')}' @ {j.get('company')} ({j.get('job_id')}) has mismatched canned software duty!")

    if corrupted_count > 0:
        print(f"[Quality Gate FAIL] Found {corrupted_count} corrupted job records missing required fields.")
        return False

    if canned_mismatch_count > 0:
        print(f"[Quality Gate WARNING] Found {canned_mismatch_count} jobs with mismatched canned duties. (Non-fatal warning for legacy data, but flagged)")

    print(f"[Quality Gate PASS] All {total_jobs} records validated successfully. Integrity verified.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Quality Gate for Internship Data")
    parser.add_argument("--file", type=str, default="", help="Path to data.json")
    parser.add_argument("--min-jobs", type=int, default=300, help="Minimum job count threshold")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    target_file = Path(args.file) if args.file else base_dir / "data" / "data.json"

    if validate_data_json(target_file, min_jobs=args.min_jobs) and validate_public_backups(base_dir / "backup"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
