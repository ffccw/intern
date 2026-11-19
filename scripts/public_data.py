"""Keep source job descriptions out of the published job feed."""

import json
import hashlib
import tempfile
from pathlib import Path
from typing import Any, Dict, List

try:
    from storage import atomic_save_json
except ImportError:
    from scripts.storage import atomic_save_json
try:
    from review_links import verified_review_links
except ImportError:
    from scripts.review_links import verified_review_links

PENDING_ANALYSIS_FIELDS = (
    "domain", "job_duties", "job_duties_en", "recommended_courses",
    "trait_advice", "trait_advice_en", "bilingual_ksa", "jd_summary",
    "core_dimensions", "collaborators", "project_stages", "project_stages_en",
    "ai_model",
)

CANNED_SOFTWARE_DUTY = "參與軟體模組功能開發、API 介接與系統架構維護作業"
SOFTWARE_TITLE_WORDS = ("軟體", "開發", "工程師", "programmer", "software", "developer", "backend", "frontend", "韌體")


def load_private_descriptions(file_path: Path) -> Dict[str, str]:
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Private description store must be a JSON object")
    return {str(key): value for key, value in data.items() if isinstance(value, str)}


def private_file_for(base_dir: Path) -> Path:
    """Use storage outside the web root, including for local preview servers."""
    key = hashlib.sha256(str(base_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "pm-pjm-jobs-private" / key / "raw_descriptions.json"


def stage_raw_descriptions(jobs: List[Dict[str, Any]], file_path: Path) -> Dict[str, str]:
    """Remove source text from public records before saving them."""
    descriptions = load_private_descriptions(file_path)
    changed = False
    for job in jobs:
        job["discussion_links"] = verified_review_links(job.get("discussion_links"))
        if not isinstance(job.get("education_req"), dict) or job["education_req"].get("verified") is not True:
            job["education_req"] = {"verified": False}
        if job.get("experience_desc") in ("大學部在學（學士生實習計畫）", "在學學生（實習計畫）"):
            job["experience_desc"] = ""
        title = str(job.get("title") or "").lower()
        if CANNED_SOFTWARE_DUTY in (job.get("job_duties") or []) and not any(word in title for word in SOFTWARE_TITLE_WORDS):
            job["ai_status"] = "pending"
        job_id = str(job.get("job_id") or "")
        raw = job.pop("raw_description", None)
        if raw is not None:
            changed = True
        if job.get("ai_status") != "done":
            if raw and job_id:
                descriptions[job_id] = raw
            for field in PENDING_ANALYSIS_FIELDS:
                job.pop(field, None)
        elif job_id in descriptions:
            descriptions.pop(job_id)
            changed = True
    if changed:
        atomic_save_json(file_path, descriptions)
    return descriptions
