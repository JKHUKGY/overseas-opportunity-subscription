import tempfile
import unittest
import json
import subprocess
import sys
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_intake import Config, SQLiteStore, StorageError, collect


NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def project(project_id: int = 42) -> dict[str, Any]:
    return {
        "id": project_id,
        "seo_url": "illustration/character-portrait",
        "title": "Draw a character portrait",
        "description": "Paid portrait commission, one character.",
        "time_submitted": 1792454400,
        "budget": {"minimum": 50, "maximum": 100},
        "currency": {"code": "USD"},
        "type": "fixed",
        "status": "active",
        "frontend_project_status": "open",
        "owner": {"email": "private@example.test"},
    }


class Source:
    def __init__(self, projects: list[dict[str, Any]]) -> None:
        self.projects = projects

    def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
        return self.projects[offset:offset + limit]


class CollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = Path(__file__).resolve().parents[1] / "temp"
        scratch.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_collect_persists_candidate_and_readable_report(self) -> None:
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("illustration",)), store, Source([project()]), now=lambda: NOW)
            self.assertEqual(report.new_count, 1)
            self.assertEqual(report.status, "success")
            saved = store.candidates()[0]
            self.assertEqual(saved["title"], "Draw a character portrait")
            self.assertEqual(saved["first_seen_at"], "2026-10-20T12:00:00+00:00")
            self.assertEqual(saved["budget_min"], 50)
            self.assertEqual(saved["processing_status"], "pending")
            self.assertNotIn("owner", saved)
            self.assertEqual(store.runs()[0]["id"], report.id)

    def test_budget_stops_after_one_request_and_reports_truncation(self) -> None:
        with SQLiteStore(self.database) as store:
            report = collect(Config(max_requests=1), store, Source([project()]), now=lambda: NOW)
            self.assertEqual(report.requests_attempted, 1)
            self.assertTrue(report.truncated)
            self.assertEqual(report.status, "partial")

    def test_unknown_fields_remain_unknown_without_losing_other_candidates(self) -> None:
        unknown = {"id": 99, "time_submitted": 1e100}
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("illustration",)), store, Source([project(), unknown]), now=lambda: NOW)
            saved = {row["id"]: row for row in store.candidates()}
            self.assertEqual(report.new_count, 2)
            self.assertIsNone(saved["99"]["published_at"])
            self.assertIsNone(saved["99"]["url"])
            self.assertIsNone(saved["99"]["budget_min"])
            self.assertIsNone(saved["99"]["description"])

    def test_http_source_runs_through_collection_without_retaining_account_data(self) -> None:
        from opportunity_intake.source import FreelancerSource

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = json.dumps({"status": "success", "result": {"projects": [project()]}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            source = FreelancerSource(base_url=f"http://127.0.0.1:{server.server_port}/")
            with SQLiteStore(self.database) as store:
                report = collect(Config(queries=("illustration",)), store, source, now=lambda: NOW)
                self.assertEqual(report.requests_succeeded, 1)
                self.assertEqual(store.candidates()[0]["id"], "42")
                self.assertNotIn("private@example.test", json.dumps(store.candidates()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_source_failure_preserves_saved_candidates_and_reports_failure(self) -> None:
        from opportunity_intake.source import SourceError

        class Unavailable(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 403)

        with SQLiteStore(self.database) as store:
            collect(Config(queries=("illustration",)), store, Source([project()]), now=lambda: NOW)
            report = collect(Config(), store, Unavailable([]), now=lambda: NOW)
            self.assertEqual(report.status, "failed")
            self.assertEqual(report.requests_attempted, 1)
            self.assertEqual(report.requests_failed, 1)
            self.assertEqual(len(store.candidates()), 1)
            self.assertEqual(store.runs()[-1]["errors"], [{"kind": "http_error", "http_status": 403}])

    def test_invalid_configuration_is_rejected_before_access(self) -> None:
        for arguments in [("--query", ""), ("--max-requests", "0"), ("--limit", "-1"),
                          ("--pages", "True"), ("--request-timeout", "nan"), ("--max-seconds", "inf")]:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-m", "opportunity_intake", "run", "--state", str(self.database), *arguments],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.database.exists())

    def test_overlap_and_restart_preserve_identity_and_cli_readback(self) -> None:
        with SQLiteStore(self.database) as store:
            first = collect(Config(), store, Source([project(42), project(43)]), now=lambda: NOW)
            self.assertEqual((first.new_count, first.duplicate_count, first.unique_count), (2, 2, 2))
        later = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        with SQLiteStore(self.database) as store:
            second = collect(Config(queries=("portrait",)), store, Source([project(43), project(44)]), now=lambda: later)
            self.assertEqual((second.new_count, second.duplicate_count), (1, 1))
        result = subprocess.run([sys.executable, "-m", "opportunity_intake", "list", "--state", str(self.database)],
                                capture_output=True, text=True, check=True)
        saved = {row["id"]: row for row in json.loads(result.stdout)}
        self.assertEqual(set(saved), {"42", "43", "44"})
        self.assertEqual(saved["43"]["first_seen_at"], "2026-10-20T12:00:00+00:00")
        self.assertEqual(saved["43"]["last_read_at"], "2026-10-21T12:00:00+00:00")

    def test_corrupt_state_is_rejected_without_reset(self) -> None:
        self.database.write_bytes(b"this is not a database")
        with self.assertRaises(StorageError):
            SQLiteStore(self.database)
        self.assertEqual(self.database.read_bytes(), b"this is not a database")

    def test_storage_write_failure_rolls_back_and_can_be_retried(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(queries=("illustration",)), store, Source([project()]), now=lambda: NOW)
            # Inject a storage-boundary fault; assertions only use public reads.
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("CREATE TRIGGER reject_write BEFORE INSERT ON candidates WHEN NEW.id = '2' BEGIN SELECT RAISE(ABORT, 'injected write failure'); END")
            with self.assertRaises(StorageError):
                collect(Config(queries=("illustration",)), store, Source([project(1), project(2)]), now=lambda: NOW)
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])
            # The failed batch rolls back; its durable start marker remains detectable.
            self.assertEqual(len(store.runs()), 2)
            self.assertEqual(store.runs()[-1]["status"], "running")
            self.assertEqual(store.runs()[-1]["new_count"], 0)
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("DROP TRIGGER reject_write")
            report = collect(Config(queries=("illustration",)), store, Source([project(1), project(2)]), now=lambda: NOW)
            self.assertEqual(report.new_count, 2)
            self.assertEqual(len(store.candidates()), 3)

    def test_invalid_identity_is_counted_without_losing_valid_candidate(self) -> None:
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("illustration",)), store,
                             Source([project(), {"id": True}, {"title": "missing id"}]), now=lambda: NOW)
            self.assertEqual(report.invalid_count, 2)
            self.assertEqual(report.status, "partial")
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])

    def test_saved_report_distinguishes_actual_queries_and_pages(self) -> None:
        class PagedSource(Source):
            def __init__(self, results: dict[tuple[str, int], list[dict[str, Any]]]) -> None:
                self.results = results

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                return self.results[(query, offset)]

        cases = [
            ({("illustration", 0): [project(42), project(43)], ("illustration", 2): [project(44)]},
             [("illustration", 0, 2), ("illustration", 2, 1)]),
            ({("illustration", 0): [project(42)], ("portrait", 0): [project(43), project(44)]},
             [("illustration", 0, 1), ("portrait", 0, 2)]),
        ]
        for index, (responses, expected) in enumerate(cases):
            with SQLiteStore(self.database.with_name(f"scope-{index}.sqlite3")) as store:
                report = collect(Config(limit=2, pages=2), store, PagedSource(responses), now=lambda: NOW)
                self.assertEqual(report.received_count, 3)
                self.assertEqual(report.status, "partial")
                requests = store.runs()[0]["requests"]
                self.assertEqual([(r["query"], r["offset"], r["received_count"]) for r in requests], expected)
                self.assertTrue(all(r["status"] == "success" and r["limit"] == 2 for r in requests))


if __name__ == "__main__":
    unittest.main()
