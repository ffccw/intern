"""Failure-path checks that never contact 104, Gemini, or Google Sheets."""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyzer
import crawler
from public_data import private_file_for, stage_raw_descriptions
from quality_gate import validate_data_json, validate_public_backups
from review_links import verified_review_links


def api_response(result):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"candidates": [{"content": {"parts": [
                {"text": json.dumps(result)}
            ]}}]}).encode("utf-8")

    return Response()


class PipelineSafetyTests(unittest.TestCase):
    def test_current_104_dom_uses_direct_job_url_and_current_selectors(self):
        html = """
        <div class="info-container">
          <h2><a class="info-job" href="https://r.104.com.tw/m104?url=https%3A%2F%2Fwww.104.com.tw%2Fjob%2F8r06p%3Fjobsource%3Dsearch">
            <div class="info-name">產品實習生</div>
          </a></h2>
          <div class="info-company"><a>範例科技股份有限公司</a>
            <span data-gtm-joblist="職缺-產業-科技">資訊服務業</span></div>
          <div class="info-tags"><span class="info-tags__text">台北市</span>
            <span class="info-tags__text">時薪 220 元</span></div>
          <div class="info-content">協助產品需求整理與專案追蹤。</div>
        </div>
        <div class="info-container">
          <h2><a class="info-job" href="https://r.104.com.tw/m104?url=https%3A%2F%2Fevil.example%2Fjob%2Fbad">
            <div class="info-name">無效連結</div>
          </a></h2>
          <div class="info-company"><a>其他公司</a></div>
        </div>
        """
        jobs = crawler.parse_104_vue_dom_html(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["jobNo"], "8r06p")
        self.assertEqual(jobs[0]["link"]["job"], "https://www.104.com.tw/job/8r06p")
        self.assertEqual(jobs[0]["jobName"], "產品實習生")
        self.assertEqual(jobs[0]["custName"], "範例科技股份有限公司")
        self.assertEqual(jobs[0]["indcatDesc"], "資訊服務業")
        self.assertEqual(jobs[0]["jobAddrNoDesc"], "台北市")
        self.assertIn("專案追蹤", jobs[0]["description"])

    def test_search_diagnostic_reports_block_and_browser_parse_failure(self):
        class BlockedResponse:
            status_code = 403
            headers = {"content-type": "text/html"}

        class BlockedSession:
            def get(self, *_args, **_kwargs):
                return BlockedResponse()

        class EmptyBrowser:
            last_diagnostic = "browser HTTP 200, DOM containers 22, parsed jobs 0"

            def search_jobs(self, **_kwargs):
                return []

        output = io.StringIO()
        with patch.object(crawler, "get_session", return_value=BlockedSession()), \
             patch.object(crawler, "get_playwright_fallback", return_value=EmptyBrowser()), \
             redirect_stdout(output):
            self.assertEqual(crawler.fetch_104_search_api("實習"), [])
        self.assertIn("list: HTTP 403", output.getvalue())
        self.assertIn("DOM containers 22, parsed jobs 0", output.getvalue())

    def test_backup_gate_rejects_source_descriptions(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "data_backup_20261118.json"
            backup.write_text(json.dumps({"jobs": [{"raw_description": "Source text"}]}), encoding="utf-8")
            self.assertFalse(validate_public_backups(Path(directory)))
            backup.write_text(json.dumps({"jobs": [{"job_id": "104_a"}]}), encoding="utf-8")
            self.assertTrue(validate_public_backups(Path(directory)))

    def test_closure_requires_three_different_days_and_reopen_resets_count(self):
        job = {"status": "open", "miss_count": 0}
        self.assertFalse(crawler.record_closed_observation(job, "2026-11-18"))
        self.assertFalse(crawler.record_closed_observation(job, "2026-11-18"))
        self.assertEqual(job["miss_count"], 1)
        self.assertFalse(crawler.record_closed_observation(job, "2026-11-19"))
        self.assertTrue(crawler.record_closed_observation(job, "2026-11-20"))
        self.assertEqual(job["closed_date"], "2026-11-20")
        another = {"status": "open", "miss_count": 0}
        self.assertFalse(crawler.record_closed_observation(another, "2026-11-18"))
        self.assertFalse(crawler.record_closed_observation(another, "2026-11-20"))
        self.assertEqual(another["miss_count"], 1)

    def test_forum_search_pages_are_removed_and_canned_claims_become_pending(self):
        self.assertEqual(verified_review_links({
            "ptt_url": "https://www.ptt.cc/bbs/Tech_Job/search?q=intern", "ptt_verified": True,
            "dcard_url": "https://www.dcard.tw/f/job/p/12345", "dcard_verified": True,
        }), {"dcard_url": "https://www.dcard.tw/f/job/p/12345", "dcard_verified": True})
        with tempfile.TemporaryDirectory() as directory:
            job = {"job_id": "104_a", "title": "Finance intern", "ai_status": "done",
                   "education_req": {"level_desc": "大學部在學（學士生）", "source": "104"},
                   "experience_desc": "大學部在學（學士生實習計畫）",
                   "job_duties": ["參與軟體模組功能開發、API 介接與系統架構維護作業"],
                   "discussion_links": {"ptt_url": "https://www.ptt.cc/bbs/Tech_Job/search?q=intern"}}
            stage_raw_descriptions([job], Path(directory) / "raw.json")
            self.assertEqual(job["education_req"], {"verified": False})
            self.assertEqual(job["experience_desc"], "")
            self.assertEqual(job["discussion_links"], {})
            self.assertEqual(job["ai_status"], "pending")
            self.assertNotIn("job_duties", job)

    def test_monthly_spend_cap_stops_after_one_request_without_sleep(self):
        error = urllib.error.HTTPError(
            "https://example.invalid", 429, "quota", {},
            io.BytesIO(b'{"error":{"message":"Your project has exceeded its monthly spending cap."}}'),
        )
        budget = analyzer.GeminiRequestBudget(10, 3600)
        with patch.object(analyzer, "GEMINI_API_KEY", "test-key"), \
             patch.object(analyzer.urllib.request, "urlopen", side_effect=error) as urlopen, \
             patch.object(analyzer.time, "sleep") as sleep:
            with self.assertRaises(analyzer.GeminiQuotaExhausted):
                analyzer.call_gemini_api("Intern", "Company", "Real job description", budget)
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(budget.requests, 1)
        sleep.assert_not_called()

    def test_request_budget_is_shared_across_jobs(self):
        result = {
            "job_duties": ["Prepare reports"], "job_duties_en": ["Prepare reports"],
            "recommended_courses": ["Statistics"], "jd_summary": {"zh": "資料分析", "en": "Data analysis"},
            "bilingual_ksa": {category: [{"zh": "分析", "en": "Analysis"}]
                              for category in ("knowledge", "skills", "attributes")},
            "domain": "商業數據 / BI 分析",
        }
        budget = analyzer.GeminiRequestBudget(1, 3600)
        with patch.object(analyzer, "GEMINI_API_KEY", "test-key"), \
             patch.object(analyzer.urllib.request, "urlopen", return_value=api_response(result)) as urlopen:
            self.assertIsNotNone(analyzer.call_gemini_api("Intern", "Company", "Real job description", budget))
            with self.assertRaises(analyzer.GeminiBudgetReached):
                analyzer.call_gemini_api("Intern 2", "Company", "Another real description", budget)
        self.assertEqual(urlopen.call_count, 1)

    def test_monthly_cap_returns_failure_and_preserves_existing_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            data_file = Path(directory) / "data.json"
            private_file = Path(directory) / "raw_descriptions.json"
            jobs = [
                {"job_id": "104_a", "company": "A", "title": "Intern A", "url": "https://www.104.com.tw/job/a",
                 "status": "open", "ai_status": "done", "job_duties": ["Verified"]},
                {"job_id": "104_b", "company": "B", "title": "Intern B", "url": "https://www.104.com.tw/job/b",
                 "status": "open", "ai_status": "pending", "raw_description": "Real source details",
                 "job_duties": ["Unverified fallback"]},
            ]
            data_file.write_text(json.dumps({"meta": {"total_jobs": 2}, "jobs": jobs}), encoding="utf-8")
            error = urllib.error.HTTPError(
                "https://example.invalid", 429, "quota", {},
                io.BytesIO(b'{"error":{"message":"Your project has exceeded its monthly spending cap."}}'),
            )
            with patch.object(analyzer, "GEMINI_API_KEY", "test-key"), \
                 patch.object(analyzer.urllib.request, "urlopen", side_effect=error) as urlopen, \
                 patch.object(analyzer.time, "sleep") as sleep:
                code = analyzer.process_pending_jobs(data_file, private_file)
            published = json.loads(data_file.read_text(encoding="utf-8"))["jobs"]
            self.assertEqual(code, 2)
            self.assertEqual(len(published), 2)
            self.assertEqual(published[0]["job_duties"], ["Verified"])
            self.assertEqual(published[1]["ai_status"], "pending")
            self.assertNotIn("raw_description", published[1])
            self.assertNotIn("job_duties", published[1])
            self.assertEqual(urlopen.call_count, 1)
            sleep.assert_not_called()

    def test_private_store_is_outside_web_root_and_quality_gate_rejects_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "web"
            root.mkdir()
            self.assertFalse(private_file_for(root).is_relative_to(root))
            raw_job = {"job_id": "104_a", "company": "A", "title": "Intern",
                       "url": "https://www.104.com.tw/job/a", "status": "open", "ai_status": "pending",
                       "raw_description": "Real source details", "job_duties": ["Unverified"]}
            data_file = root / "data.json"
            data_file.write_text(json.dumps({"meta": {"total_jobs": 1}, "jobs": [raw_job]}), encoding="utf-8")
            self.assertFalse(validate_data_json(data_file, min_jobs=1))
            done_job = {"job_id": "104_done", "ai_status": "done", "raw_description": "Old source text"}
            private_file = Path(directory) / "private.json"
            descriptions = stage_raw_descriptions([raw_job, done_job], private_file)
            data_file.write_text(json.dumps({"meta": {"total_jobs": 1}, "jobs": [raw_job]}), encoding="utf-8")
            self.assertTrue(validate_data_json(data_file, min_jobs=1))
            self.assertNotIn("raw_description", raw_job)
            self.assertNotIn("job_duties", raw_job)
            self.assertEqual(descriptions, {"104_a": "Real source details"})
            self.assertNotIn("raw_description", done_job)

    def test_crawler_does_not_call_gemini(self):
        item = {"custName": "Example", "jobName": "Project Intern", "jobNo": "abc123",
                "salaryDesc": "Negotiable", "jobAddrNoDesc": "Taipei"}
        jobs = []
        with patch.object(crawler, "match_internship_title", return_value=True), \
             patch.object(crawler, "match_company_whitelist", return_value=(True, "1234", "上市", None, "Example")), \
             patch.object(crawler, "fetch_job_detail_cffi", return_value="Real source details for this internship"), \
             patch.object(crawler, "analyze_internship_jd", return_value={"ai_status": "pending"}) as analyze:
            self.assertTrue(crawler.process_single_api_job(item, None, jobs, set(), [], {}))
        self.assertEqual(len(jobs), 1)
        self.assertFalse(analyze.call_args.kwargs["use_gemini"])
        self.assertEqual(jobs[0]["ai_status"], "pending")

    def test_empty_104_search_aborts_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            companies_file = Path(directory) / "companies.json"
            companies_file.write_text("[]", encoding="utf-8")
            data_file = Path(directory) / "data.json"
            data_file.write_text(json.dumps({"jobs": [
                {"job_id": "104_a", "url": "https://www.104.com.tw/job/a", "ai_status": "done", "status": "open"}
            ]}), encoding="utf-8")
            with patch.object(crawler, "COMPANIES_FILE", companies_file), \
                 patch.object(crawler, "DATA_FILE", data_file), \
                 patch.object(crawler, "refresh_active_jobs", return_value={"date_updated": 1, "closed": 0}) as refresh, \
                 patch.object(crawler, "fetch_104_search_api", return_value=[]), \
                 patch.object(crawler, "load_private_descriptions", return_value={}), \
                 patch.object(crawler, "PLAYWRIGHT_MANAGER", None), \
                 patch.object(crawler, "save_unmatched_companies"), \
                 patch.object(crawler.time, "sleep"), \
                 patch.object(crawler, "update_database_and_csv") as publish:
                with self.assertRaises(RuntimeError):
                    crawler.crawl_live_internships()
            publish.assert_not_called()
            refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
