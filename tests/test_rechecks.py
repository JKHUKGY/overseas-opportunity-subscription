"""Status rechecks and endings through complete collection runs."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any

from opportunity_intake import Config, SQLiteStore, collect
from tests.test_collection import NOW, Source, project


def listing(identifier: int = 42, status: str = "open") -> dict[str, Any]:
    item = project(identifier)
    item["seo_url"] = f"illustration/portrait-{identifier}"
    item["frontend_project_status"] = status
    return item


class RecheckSource(Source):
    def __init__(self, projects: list[dict[str, Any]], details: dict[str, dict[str, Any]]) -> None:
        super().__init__(projects)
        self.details = details
        self.checked: list[str] = []

    def detail(self, project_id: str, timeout: float) -> dict[str, Any]:
        self.checked.append(project_id)
        return self.details[project_id]


class RecheckTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_disappeared_search_candidate_is_rechecked_and_changed_content_invalidates_processing(self) -> None:
        import json
        import sqlite3

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            saved = store.candidates()[0]
            saved.update(processing_status="reviewed", summary="Old summary", classification="drawing")
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("UPDATE candidates SET payload = ?", (json.dumps(saved),))
            changed = listing()
            changed["description"] = "Changed portrait commission"
            source = RecheckSource([], {"42": changed})
            report = collect(Config(queries=("portrait",), recheck_limit=1), store, source, now=lambda: NOW + timedelta(hours=1))
            saved = store.candidates()[0]
            self.assertEqual(source.checked, ["42"])
            self.assertEqual(saved["last_status_verified_at"], "2026-10-20T13:00:00+00:00")
            self.assertEqual(saved["content_version"], 2)
            self.assertEqual(saved["processing_status"], "pending")
            self.assertIsNone(saved["summary"])
            self.assertEqual(report.rechecks_succeeded, 1)
            self.assertEqual(report.pending_recheck_count, 0)
            self.assertEqual(report.requests_attempted, 2)

    def test_shared_request_cap_and_persisted_rotation_include_failed_candidates(self) -> None:
        from opportunity_intake.source import SourceError

        class FirstFails(RecheckSource):
            def detail(self, project_id: str, timeout: float) -> dict[str, Any]:
                self.checked.append(project_id)
                if project_id == "42":
                    raise SourceError("http_error", 404)
                return self.details[project_id]

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(i) for i in (42, 43, 44)], {}), now=lambda: NOW)
        source = FirstFails([], {str(i): listing(i) for i in (42, 43, 44)})
        for identifier in ("42", "43", "44", "42"):
            with SQLiteStore(self.database) as store:
                report = collect(Config(max_requests=1, recheck_limit=3), store, source, now=lambda: NOW + timedelta(days=1))
                self.assertEqual(source.checked[-1], identifier)
                self.assertEqual(report.requests_attempted, 1)
                self.assertTrue(report.truncated)
                self.assertEqual(report.pending_recheck_count, 2)
                self.assertEqual(len(store.candidates()), 3)
                if identifier == "42":
                    self.assertEqual(report.rechecks_failed, 1)
                    self.assertEqual(store.candidates()[0]["status"], "无法核实")
                    self.assertIsNone(store.candidates()[0]["last_status_verified_at"])

    def test_closed_project_leaves_only_minimal_ended_record_and_is_not_rediscovered(self) -> None:
        import json

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            report = collect(Config(queries=("portrait",)), store,
                             RecheckSource([listing()], {"42": listing(status="closed")}), now=lambda: NOW + timedelta(hours=1))
            self.assertEqual(store.candidates(), [])
            self.assertEqual(report.confirmed_ended_count, 1)
            self.assertEqual(report.ended_record_hits, 1)
            records = store.ended_records()
            self.assertEqual(len(records), 1)
            self.assertEqual(set(records[0]), {"source", "id", "url", "deleted_at", "reason"})
            self.assertEqual(records[0]["reason"], "source_closed")
            self.assertEqual(records[0]["deleted_at"], "2026-10-20T13:00:00+00:00")
            self.assertNotIn("Paid portrait", json.dumps(records + store.runs()))
        with SQLiteStore(self.database) as store:
            source = RecheckSource([listing()], {})
            report = collect(Config(), store, source, now=lambda: NOW + timedelta(days=1))
            self.assertEqual(source.checked, [])
            self.assertEqual(report.ended_record_hits, 2)
            self.assertEqual(len(store.ended_records()), 1)
            self.assertEqual(store.candidates(), [])

    def test_ended_write_failure_preserves_details_and_retry_succeeds(self) -> None:
        import sqlite3
        from opportunity_intake import StorageError

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            before = store.candidates()
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("CREATE TRIGGER reject_ending BEFORE INSERT ON ended_records BEGIN SELECT RAISE(ABORT, 'injected'); END")
            with self.assertRaises(StorageError):
                collect(Config(), store, RecheckSource([], {"42": listing(status="closed")}), now=lambda: NOW)
            self.assertEqual(store.candidates(), before)
            self.assertEqual(store.ended_records(), [])
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("DROP TRIGGER reject_ending")
            report = collect(Config(), store, RecheckSource([], {"42": listing(status="closed")}), now=lambda: NOW)
            self.assertEqual(report.confirmed_ended_count, 1)
            self.assertEqual(store.candidates(), [])

    def test_process_exit_after_ended_commit_hides_details_and_next_run_finishes_cleanup(self) -> None:
        import subprocess
        import sys

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
        script = '''
import os, sys
from pathlib import Path
from opportunity_intake import Config, SQLiteStore, collect
from tests.test_collection import NOW
from tests.test_rechecks import listing, RecheckSource
class InterruptedStore(SQLiteStore):
    def cleanup_ended(self):
        if self.ended_records():
            os._exit(77)
        return super().cleanup_ended()
with InterruptedStore(Path(sys.argv[1])) as store:
    collect(Config(), store, RecheckSource([], {"42": listing(status="closed")}), now=lambda: NOW)
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.database)], capture_output=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.candidates(), [])
            self.assertEqual(len(store.ended_records()), 1)
            self.assertEqual(store.runs()[-1]["status"], "running")
            source = RecheckSource([listing()], {})
            report = collect(Config(), store, source, now=lambda: NOW)
            self.assertEqual(report.recovered_deletions, 1)
            self.assertEqual(source.checked, [])
            self.assertEqual(store.candidates(), [])
            self.assertEqual(len(store.ended_records()), 1)

    def test_tracking_variants_are_excluded_but_identity_parameters_are_preserved(self) -> None:
        with SQLiteStore(self.database) as store:
            original = listing()
            original["seo_url"] += "?project=42&utm_source=old#top"
            collect(Config(recheck_limit=0), store, RecheckSource([original], {}), now=lambda: NOW)
            collect(Config(), store, RecheckSource([], {"42": listing(status="closed")}), now=lambda: NOW)
            alias = listing(999)
            alias["seo_url"] = "illustration/portrait-42?project=42&utm_campaign=new"
            distinct = listing(43)
            distinct["seo_url"] = "illustration/portrait-42?project=43"
            source = RecheckSource([alias, distinct], {})
            report = collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(report.ended_record_hits, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["43"])
            self.assertEqual(source.checked, [])

    def test_ambiguous_states_keep_candidates_and_do_not_forge_verification(self) -> None:
        for status in ("active", "awaiting_acceptance", "work_in_progress", "no_freelancer_selected", "new_unknown_enum"):
            with self.subTest(status=status), SQLiteStore(self.database.with_name(status + ".sqlite3")) as store:
                collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
                collect(Config(queries=("portrait",)), store, RecheckSource([], {"42": listing()}), now=lambda: NOW)
                ambiguous = listing(status=status)
                ambiguous.update(bid_stats={"bid_count": 999}, description="We are choosing among applicants.", time_submitted=1)
                report = collect(Config(queries=("portrait",)), store, RecheckSource([], {"42": ambiguous}), now=lambda: NOW + timedelta(days=5))
                saved = store.candidates()[0]
                self.assertEqual(saved["status"], "无法核实")
                self.assertEqual(saved["last_status_verified_at"], NOW.isoformat())
                self.assertEqual(report.rechecks_unresolved, 1)
                self.assertEqual(report.status, "partial")
                self.assertEqual(store.ended_records(), [])

    def test_real_http_detail_endpoint_and_complete_status_use_same_run(self) -> None:
        import json
        import subprocess
        import sys
        from tests.test_failures import http_source

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            paths: list[str] = []
            replies: list[tuple[int, dict[str, str], bytes]] = [(200, {}, json.dumps({"status": "success", "result": listing(status="complete")}).encode()),
                       (200, {}, b'{"status":"success","result":{"projects":[]}}')]
            with http_source(replies, paths=paths) as source:
                report = collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(paths[0], "/42/?full_description=true")
            self.assertTrue(paths[1].startswith("/?query=portrait&"))
            self.assertEqual(report.confirmed_ended_count, 1)
            self.assertEqual(store.ended_records()[0]["reason"], "source_complete")
        result = subprocess.run([sys.executable, "-m", "opportunity_intake", "ended", "--state", str(self.database)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]["id"], "42")

    def test_mismatched_detail_identity_cannot_close_another_candidate(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            report = collect(Config(), store, RecheckSource([], {"42": listing(43, "closed")}), now=lambda: NOW)
            self.assertEqual(report.errors, [{"kind": "invalid_response", "http_status": None}])
            self.assertEqual(report.rechecks_failed, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])
            self.assertIsNone(store.candidates()[0]["last_status_verified_at"])
            self.assertEqual(store.ended_records(), [])

    def test_detail_rate_limit_persists_cooldown_and_stops_search(self) -> None:
        from opportunity_intake.source import SourceError

        class Limited(RecheckSource):
            def detail(self, project_id: str, timeout: float) -> dict[str, Any]:
                raise SourceError("http_error", 429, retry_after="120")

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise AssertionError("No search after rate limit")

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            report = collect(Config(), store, Limited([], {}), now=lambda: NOW)
            self.assertEqual(report.next_allowed_at, "2026-10-20T12:02:00+00:00")
            self.assertEqual(report.requests_attempted, 1)
        with SQLiteStore(self.database) as store:
            report = collect(Config(), store, RecheckSource([], {}), now=lambda: NOW + timedelta(seconds=119))
            self.assertEqual(report.status, "skipped")
            self.assertEqual(report.requests_attempted, 0)

    def test_detail_and_search_share_remaining_time_budget(self) -> None:
        class Timed(RecheckSource):
            elapsed = 0.0
            timeouts: list[float]

            def __init__(self) -> None:
                super().__init__([], {"42": listing()})
                self.timeouts = []

            def detail(self, project_id: str, timeout: float) -> dict[str, Any]:
                self.timeouts.append(timeout)
                self.elapsed += 3
                return super().detail(project_id, timeout)

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                self.timeouts.append(timeout)
                self.elapsed += 2
                return []

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            source = Timed()
            report = collect(Config(max_requests=9, max_seconds=5, request_timeout=4), store, source, now=lambda: NOW, clock=lambda: source.elapsed)
            self.assertEqual(source.timeouts, [4, 2])
            self.assertEqual(report.requests_attempted, 2)
            self.assertEqual(report.status, "partial")
            self.assertTrue(report.truncated)

    def test_ending_retains_verified_url_when_previous_search_had_no_url(self) -> None:
        with SQLiteStore(self.database) as store:
            missing = listing()
            missing.pop("seo_url")
            collect(Config(recheck_limit=0), store, RecheckSource([missing], {}), now=lambda: NOW)
            collect(Config(), store, RecheckSource([], {"42": listing(status="closed")}), now=lambda: NOW)
            self.assertEqual(store.ended_records()[0]["url"], "https://www.freelancer.com/projects/illustration/portrait-42")
