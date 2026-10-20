"""Failure and recovery acceptance tests at the complete collection boundary."""

import tempfile
import unittest
import json
import threading
import subprocess
import sys
import sqlite3
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

from opportunity_intake import Config, SQLiteStore, collect
from opportunity_intake.source import FreelancerSource, SourceError
from tests.test_collection import NOW, Source, project


@contextmanager
def http_source(replies: list[tuple[int, dict[str, str], bytes]], *,
                stall: bool = False, stall_body: bool = False) -> Iterator[FreelancerSource]:
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if stall:
                release.wait()
                return
            status, headers, body = replies.pop(0)
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if stall_body:
                release.wait()
                return
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A bounded client may reject the response before its body.

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield FreelancerSource("test-secret", base_url=f"http://127.0.0.1:{server.server_port}/")
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join()


class FailureTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = Path(__file__).resolve().parents[1] / "temp"
        scratch.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_retry_after_survives_restart_and_skips_until_due(self) -> None:
        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="120")

        class NoAccess(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise AssertionError("Source must not be accessed during cooldown")

        with SQLiteStore(self.database) as store:
            limited = collect(Config(), store, Limited([]), now=lambda: NOW)
            self.assertEqual(limited.next_allowed_at, "2026-10-20T12:02:00+00:00")
            self.assertEqual(limited.requests_attempted, 1)
        with SQLiteStore(self.database) as store:
            skipped = collect(Config(), store, NoAccess([]), now=lambda: NOW + timedelta(seconds=119))
            self.assertEqual(skipped.status, "skipped")
            self.assertEqual(skipped.requests_attempted, 0)
            self.assertEqual(store.runs()[-1]["next_allowed_at"], limited.next_allowed_at)
            resumed = collect(Config(queries=("portrait",)), store, Source([project()]), now=lambda: NOW + timedelta(seconds=120))
            self.assertEqual(resumed.status, "success")
            self.assertIsNone(resumed.next_allowed_at)
            self.assertEqual(len(store.candidates()), 1)

    def test_http_date_retry_after_is_respected_without_retaining_error_body(self) -> None:
        replies = [(429, {"Retry-After": "Tue, 20 Oct 2026 12:05:00 GMT"}, b"test-secret private error body")]
        with http_source(replies) as source, SQLiteStore(self.database) as store:
            report = collect(Config(), store, source, now=lambda: NOW)
            self.assertEqual(report.next_allowed_at, "2026-10-20T12:05:00+00:00")
            self.assertNotIn("test-secret", json.dumps(store.runs()))
            self.assertNotIn("private error body", json.dumps(store.runs()))

    def test_process_exit_preserves_completed_page_and_exposes_unfinished_run(self) -> None:
        script = """
import os, sys
from pathlib import Path
from opportunity_intake import Config, SQLiteStore, collect
from tests.test_collection import NOW, project
class Interrupted:
    def search(self, query, limit, offset, timeout):
        if offset:
            os._exit(77)
        return [project(42)]
with SQLiteStore(Path(sys.argv[1])) as store:
    collect(Config(queries=("portrait",), limit=1, pages=2), store, Interrupted(), now=lambda: NOW)
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.database)], capture_output=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        with SQLiteStore(self.database) as store:
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])
            unfinished = store.runs()[0]
            self.assertEqual(unfinished["status"], "running")
            self.assertIsNone(unfinished["finished_at"])
            self.assertEqual(unfinished["requests_succeeded"], 1)
            self.assertEqual(unfinished["requests"][-1]["status"], "running")
            report = collect(Config(queries=("portrait",)), store, Source([project(42), project(43)]), now=lambda: NOW + timedelta(hours=1))
            self.assertEqual(report.unfinished_run_ids, [unfinished["id"]])
            self.assertEqual((report.new_count, report.duplicate_count), (1, 1))
            self.assertEqual(len(store.candidates()), 2)
            self.assertEqual(store.candidates()[0]["first_seen_at"], NOW.isoformat())

    def test_all_request_budgets_are_shared_and_report_cutoff(self) -> None:
        class Timed(Source):
            elapsed = 0.0
            timeouts: list[float]

            def __init__(self) -> None:
                self.timeouts = []

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                self.timeouts.append(timeout)
                self.elapsed += 3
                return [project(len(self.timeouts))]

        source = Timed()
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("portrait",), limit=1, pages=10, max_requests=10, request_timeout=4, max_seconds=5),
                             store, source, now=lambda: NOW, clock=lambda: source.elapsed)
            self.assertEqual(source.timeouts, [4, 2])
            self.assertEqual(report.status, "partial")
            self.assertTrue(report.truncated)
            self.assertEqual(len(store.candidates()), 2)
            self.assertEqual(report.requests_attempted, 2)
            source = Timed()
            report = collect(Config(queries=("portrait",), limit=1, pages=10, max_requests=1),
                             store, source, now=lambda: NOW, clock=lambda: source.elapsed)
            self.assertEqual(report.requests_attempted, 1)
            self.assertTrue(report.truncated)

    def test_deadline_reached_during_last_request_is_reported(self) -> None:
        class Timed(Source):
            elapsed = 0.0

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                self.elapsed += timeout
                return [project()]

        source = Timed([])
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("portrait",), max_seconds=1), store, source, now=lambda: NOW, clock=lambda: source.elapsed)
            self.assertEqual(report.status, "partial")
            self.assertTrue(report.truncated)
            self.assertEqual(len(store.candidates()), 1)

    def test_http_failures_are_distinct_and_stop_remaining_requests(self) -> None:
        cases = [(401, b"private", "http_error"), (403, b"private", "http_error"),
                 (503, b"private", "http_error"), (200, b"not-json", "invalid_json"),
                 (200, b'{"status":"success","result":{"projects":null}}', "invalid_response")]
        for index, (status, body, kind) in enumerate(cases):
            with self.subTest(status=status, kind=kind), http_source([(status, {}, body)]) as source:
                with SQLiteStore(self.database.with_name(f"error-{index}.sqlite3")) as store:
                    collect(Config(), store, Source([project()]), now=lambda: NOW)
                    previous = store.candidates()
                    report = collect(Config(), store, source, now=lambda: NOW)
                    self.assertEqual(report.status, "failed")
                    self.assertEqual(report.requests_attempted, 1)
                    self.assertEqual(report.requests_failed, 1)
                    self.assertEqual(report.errors[0]["kind"], kind)
                    self.assertEqual(report.errors[0]["http_status"], status if status != 200 else None)
                    self.assertEqual(store.candidates(), previous)
                    self.assertNotIn("private", json.dumps(store.runs()))

    def test_zero_partial_and_invalid_records_preserve_successful_data(self) -> None:
        valid = json.dumps({"status": "success", "result": {"projects": [project(43), None, {"id": True}]}}).encode()
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            before = store.candidates()
            zero = collect(Config(), store, Source([]), now=lambda: NOW)
            self.assertEqual(zero.status, "success")
            self.assertEqual(zero.received_count, 0)
            self.assertEqual(store.candidates(), before)
            with http_source([(200, {}, valid), (500, {}, b"private")]) as source:
                partial = collect(Config(), store, source, now=lambda: NOW)
            self.assertEqual(partial.status, "partial")
            self.assertEqual((partial.requests_succeeded, partial.requests_failed, partial.invalid_count), (1, 1, 2))
            self.assertEqual(partial.errors, [{"kind": "http_error", "http_status": 500}])
            self.assertEqual([row["id"] for row in store.candidates()], ["42", "43"])
            self.assertEqual(store.candidates()[0], before[0])

    def test_timeout_and_transport_failure_preserve_prior_page(self) -> None:
        for kind in ("timeout", "transport_error"):
            class Failing(Source):
                def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                    if offset:
                        raise SourceError(kind)
                    return [project()]

            with self.subTest(kind=kind), SQLiteStore(self.database) as store:
                report = collect(Config(queries=("portrait",), limit=1, pages=2), store, Failing([]), now=lambda: NOW)
                self.assertEqual(report.status, "partial")
                self.assertEqual(report.errors, [{"kind": kind, "http_status": None}])
                self.assertEqual(len(store.candidates()), 1)
                self.assertEqual(store.runs()[-1]["requests"][-1]["status"], "failed")

    def test_backoff_grows_to_bound_and_success_resets_it(self) -> None:
        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="invalid")

        current = NOW
        with SQLiteStore(self.database) as store:
            for delay in (60, 120, 240, 480, 960, 1920, 3600, 3600):
                report = collect(Config(), store, Limited([]), now=lambda: current)
                current += timedelta(seconds=delay)
                self.assertEqual(report.next_allowed_at, current.isoformat())
                self.assertEqual(report.requests_attempted, 1)
            collect(Config(), store, Source([]), now=lambda: current)
            report = collect(Config(), store, Limited([]), now=lambda: current)
            self.assertEqual(report.next_allowed_at, (current + timedelta(seconds=60)).isoformat())

    def test_numeric_and_missing_retry_after_from_http(self) -> None:
        for index, (headers, delay) in enumerate([({"Retry-After": "37"}, 37), ({}, 60)]):
            with http_source([(429, headers, b"private")]) as source:
                with SQLiteStore(self.database.with_name(f"limit-{index}.sqlite3")) as store:
                    report = collect(Config(), store, source, now=lambda: NOW)
                    self.assertEqual(report.next_allowed_at, (NOW + timedelta(seconds=delay)).isoformat())
                    self.assertEqual(report.status, "failed")

    def test_existing_processing_state_survives_refresh(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            candidate = store.candidates()[0]
            candidate.update(processing_status="reviewed", status="已结束", last_status_verified_at=NOW.isoformat())
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("UPDATE candidates SET payload = ?", (json.dumps(candidate),))
            collect(Config(), store, Source([project()]), now=lambda: NOW + timedelta(hours=1))
            updated = store.candidates()[0]
            for field in ("first_seen_at", "processing_status", "status", "last_status_verified_at"):
                self.assertEqual(updated[field], candidate[field])
            self.assertEqual(updated["last_read_at"], (NOW + timedelta(hours=1)).isoformat())

    def test_actual_http_timeout_is_bounded_and_reported(self) -> None:
        with http_source([], stall=True) as source, SQLiteStore(self.database) as store:
            report = collect(Config(request_timeout=0.1), store, source, now=lambda: NOW)
            self.assertEqual(report.status, "failed")
            self.assertEqual(report.errors, [{"kind": "timeout", "http_status": None}])
            self.assertEqual(report.requests_attempted, 1)

    def test_existing_version_one_database_is_migrated_without_losing_data(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            candidates, runs = store.candidates(), store.runs()
        with sqlite3.connect(str(self.database)) as legacy:
            legacy.execute("DROP TABLE source_limits")
            legacy.execute("PRAGMA user_version = 1")
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.candidates(), candidates)
            self.assertEqual(store.runs(), runs)
            report = collect(Config(), store, Source([]), now=lambda: NOW)
            self.assertEqual(report.status, "success")

    def test_invalid_limits_reject_complete_cli_run_without_creating_state(self) -> None:
        for name in ("--max-seconds", "--request-timeout"):
            for value in ("0", "-1", "True", "nan", "inf", str(10 ** 1000)):
                with self.subTest(name=name, value=value[:20]):
                    result = subprocess.run(
                        [sys.executable, "-m", "opportunity_intake", "run", "--state", str(self.database), name, value],
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(self.database.exists())

    def test_http_looking_error_body_cannot_override_rate_limit_headers(self) -> None:
        replies = [(429, {"Retry-After": "120"}, b"HTTP/1.1 503 private proxy error body")]
        with http_source(replies) as source, SQLiteStore(self.database) as store:
            report = collect(Config(), store, source, now=lambda: NOW)
            self.assertEqual(report.errors, [{"kind": "http_error", "http_status": 429}])
            self.assertEqual(report.next_allowed_at, (NOW + timedelta(seconds=120)).isoformat())

    def test_rate_limit_headers_survive_oversized_error_body(self) -> None:
        with http_source([(429, {"Retry-After": "120"}, b"x" * 2097153)]) as source:
            with SQLiteStore(self.database) as store:
                report = collect(Config(), store, source, now=lambda: NOW)
                self.assertEqual(report.errors, [{"kind": "http_error", "http_status": 429}])
                self.assertEqual(report.next_allowed_at, (NOW + timedelta(seconds=120)).isoformat())
                skipped = collect(Config(), store, source, now=lambda: NOW + timedelta(seconds=119))
                self.assertEqual(skipped.status, "skipped")
                self.assertEqual(skipped.requests_attempted, 0)

    def test_invalid_unicode_record_does_not_discard_valid_neighbor(self) -> None:
        malformed = project(43)
        malformed["description"] = "bad surrogate: \ud800"
        body = json.dumps({"status": "success", "result": {"projects": [project(), malformed]}}).encode()
        with http_source([(200, {}, body)]) as source, SQLiteStore(self.database) as store:
            report = collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(report.status, "partial")
            self.assertEqual(report.invalid_count, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])

    def test_rate_limit_headers_survive_body_timeout(self) -> None:
        with http_source([(429, {"Retry-After": "120"}, b"body")], stall_body=True) as source:
            with SQLiteStore(self.database) as store:
                report = collect(Config(request_timeout=0.1), store, source, now=lambda: NOW)
                self.assertEqual(report.errors, [{"kind": "http_error", "http_status": 429}])
                self.assertEqual(report.next_allowed_at, (NOW + timedelta(seconds=120)).isoformat())
