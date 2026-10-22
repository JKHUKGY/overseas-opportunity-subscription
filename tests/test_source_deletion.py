"""Source-requested erasure through its public entry and complete intake runs."""

import tempfile
import unittest
from pathlib import Path

from opportunity_intake import Config, SQLiteStore, collect
from tests.test_collection import NOW
from tests.test_rechecks import RecheckSource, listing


class SourceDeletionTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_delete_active_candidate_is_persistent_isolated_and_repeatable(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            remaining = store.candidates()[1]
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.candidates_deleted, 1)
            self.assertEqual(result.ended_records_deleted, 0)
            self.assertEqual(store.candidates(), [remaining])
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.candidates(), [remaining])
            again = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(again.candidates_deleted, 0)
            self.assertEqual(again.status, "complete")
            report = collect(Config(recheck_limit=0), store, RecheckSource([listing(42)], {}), now=lambda: NOW)
            self.assertEqual(report.new_count, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["42", "43"])

    def test_source_deletion_releases_ended_exclusion_without_touching_other_endings(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            collect(Config(recheck_limit=2, max_requests=3, queries=("portrait",)), store,
                    RecheckSource([], {str(i): listing(i, "closed") for i in (42, 43)}), now=lambda: NOW)
            kept = store.ended_records()[1]
            excluded = collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            self.assertEqual(excluded.ended_record_hits, 4)
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.ended_records_deleted, 1)
            self.assertEqual(store.ended_records(), [kept])
        with SQLiteStore(self.database) as store:
            source = RecheckSource([listing(42), listing(43)], {})
            report = collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(report.new_count, 1)
            self.assertEqual(report.ended_record_hits, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["42"])
            self.assertEqual(source.checked, [])

    def test_id_or_url_deletes_tracking_aliases_but_preserves_identity_parameters(self) -> None:
        for selector in ({"project_id": "42"}, {"url": "https://www.freelancer.com/projects/portrait?project=42&utm_medium=request#top"}):
            with self.subTest(selector=selector), SQLiteStore(self.database.with_name(next(iter(selector)) + ".sqlite3")) as store:
                original, alias, distinct = listing(42), listing(99), listing(43)
                original["seo_url"] = "portrait?project=42&utm_source=old"
                alias["seo_url"] = "portrait?project=42&utm_campaign=new#details"
                distinct["seo_url"] = "portrait?project=43"
                collect(Config(recheck_limit=0), store, RecheckSource([original, alias, distinct], {}), now=lambda: NOW)
                result = store.delete_source_data("Freelancer", **selector)
                self.assertEqual(result.candidates_deleted, 2)
                self.assertEqual([row["id"] for row in store.candidates()], ["43"])
                report = collect(Config(recheck_limit=0), store, RecheckSource([original, alias], {}), now=lambda: NOW)
                self.assertEqual(report.new_count, 2)

    def test_deletion_redacts_history_identity_and_removes_only_matching_recheck_cursor(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            collect(Config(queries=("portrait",)), store, RecheckSource([], {"42": listing(42)}), now=lambda: NOW)
            totals = [(run["received_count"], run["unique_count"]) for run in store.runs()]
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.history_entries_redacted, 3)
            self.assertEqual(result.recheck_cursors_deleted, 1)
            self.assertEqual([(run["received_count"], run["unique_count"]) for run in store.runs()], totals)
            for run in store.runs():
                self.assertFalse(any(row.get("id") == "42" for field in ("candidate_results", "requests") for row in run[field]))
            self.assertEqual(store.runs()[0]["candidate_results"][0]["id"], "43")
            self.assertEqual(store.runs()[1]["redacted_detail_requests"], 1)
            repeated = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(repeated.history_entries_redacted, 0)
            collect(Config(recheck_limit=0), store, RecheckSource([listing(41)], {}), now=lambda: NOW)
            source = RecheckSource([], {"41": listing(41)})
            collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(source.checked, ["41"])
            # Deleting an unobserved candidate leaves another project's cursor intact.
            other = store.delete_source_data("Freelancer", project_id="43")
            self.assertEqual(other.recheck_cursors_deleted, 0)

    def test_invalid_selectors_are_rejected_without_changing_saved_data(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            before = store.candidates(), store.runs()
            for source, selector in (
                ("Freelancer", {}),
                ("Freelancer", {"project_id": "42", "url": "https://www.freelancer.com/projects/portrait-42"}),
                ("", {"project_id": "42"}),
                (" Freelancer", {"project_id": "42"}),
                ("Freelancer", {"project_id": ""}),
                ("Freelancer", {"url": "portrait-42"}),
                ("Freelancer", {"url": "file:///tmp/portrait"}),
                ("Freelancer", {"url": "https://"}),
            ):
                with self.subTest(source=source, selector=selector), self.assertRaises(ValueError):
                    store.delete_source_data(source, **selector)
                self.assertEqual((store.candidates(), store.runs()), before)

    def test_cli_deletes_by_url_reports_counts_and_rejects_missing_selector_or_state(self) -> None:
        import json
        import subprocess
        import sys

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
        args = [sys.executable, "-m", "opportunity_intake", "delete-source", "--state", str(self.database), "--source", "Freelancer"]
        invalid = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        with SQLiteStore(self.database) as store:
            self.assertEqual(len(store.candidates()), 1)
        result = subprocess.run(args + ["--url", "https://www.freelancer.com/projects/illustration/portrait-42?utm_source=request"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["candidates_deleted"], 1)
        self.assertEqual(json.loads(result.stdout)["status"], "complete")
        self.assertNotIn("portrait-42", result.stdout)
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.candidates(), [])
        missing = self.database.with_name("missing.sqlite3")
        failed = subprocess.run(args + ["--state", str(missing), "--project-id", "42"], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertFalse(missing.exists())

    def test_failed_deletion_rolls_back_hidden_details_endings_and_history_then_retries(self) -> None:
        import sqlite3
        from opportunity_intake import StorageError

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("CREATE TRIGGER stop_cleanup BEFORE DELETE ON candidates BEGIN SELECT RAISE(ABORT, 'injected'); END")
            with self.assertRaises(StorageError):
                collect(Config(), store, RecheckSource([], {"42": listing(42, "closed")}), now=lambda: NOW)
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute("DROP TRIGGER stop_cleanup")
                fault.execute("CREATE TRIGGER stop_redaction BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT, 'sensitive injected message'); END")
            before = store.candidates(), store.ended_records(), store.runs()
            with self.assertRaises(StorageError) as raised:
                store.delete_source_data("Freelancer", url="https://www.freelancer.com/projects/illustration/portrait-42")
            self.assertNotIn("sensitive", str(raised.exception))
            self.assertIn("rolled back", str(raised.exception))
            self.assertEqual((store.candidates(), store.ended_records(), store.runs()), before)
        with sqlite3.connect(str(self.database)) as fault:
            fault.execute("DROP TRIGGER stop_redaction")
        with SQLiteStore(self.database) as store:
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.candidates_deleted, 1)
            self.assertEqual(result.ended_records_deleted, 1)
            self.assertEqual(result.recheck_cursors_deleted, 1)
            self.assertEqual([row["id"] for row in store.candidates()], ["43"])
            self.assertEqual(store.ended_records(), [])

    def test_matching_identity_in_another_source_and_shared_cooldown_are_preserved(self) -> None:
        import json
        import sqlite3
        from opportunity_intake.source import SourceError

        class Limited(RecheckSource):
            def detail(self, project_id: str, timeout: float) -> dict[str, object]:
                raise SourceError("http_error", 429, retry_after="120")

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
            other = dict(store.candidates()[0], source="Other")
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("INSERT INTO candidates VALUES (?, ?, ?)", ("Other", "42", json.dumps(other)))
            collect(Config(), store, Limited([], {}), now=lambda: NOW)
            cooldown = store.source_limit()
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.candidates_deleted, 1)
            self.assertEqual(store.candidates(), [other])
            self.assertEqual(store.source_limit(), cooldown)

    def test_process_exit_mid_transaction_rolls_back_and_reopened_deletion_succeeds(self) -> None:
        import sqlite3
        import subprocess
        import sys

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing(42), listing(43)], {}), now=lambda: NOW)
            before = store.candidates(), store.runs()
        with sqlite3.connect(str(self.database)) as fault:
            fault.execute("CREATE TRIGGER crash_deletion AFTER DELETE ON candidates BEGIN SELECT injected_exit(); END")
        script = '''
import os, sqlite3, sys
from pathlib import Path
from unittest.mock import patch
from opportunity_intake import SQLiteStore
connect = sqlite3.connect
def fault_connection(*args, **kwargs):
    db = connect(*args, **kwargs)
    db.create_function("injected_exit", 0, lambda: os._exit(77))
    return db
with patch("sqlite3.connect", fault_connection):
    with SQLiteStore(Path(sys.argv[1])) as store:
        store.delete_source_data("Freelancer", project_id="42")
'''
        exited = subprocess.run([sys.executable, "-c", script, str(self.database)], capture_output=True, text=True)
        self.assertEqual(exited.returncode, 77, exited.stderr)
        with SQLiteStore(self.database) as store:
            self.assertEqual((store.candidates(), store.runs()), before)
        with sqlite3.connect(str(self.database)) as fault:
            fault.execute("DROP TRIGGER crash_deletion")
        with SQLiteStore(self.database) as store:
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.candidates_deleted, 1)
            source = RecheckSource([listing(42)], {"43": listing(43)})
            report = collect(Config(queries=("portrait",)), store, source, now=lambda: NOW)
            self.assertEqual(source.checked, ["43"])
            self.assertEqual(report.new_count, 1)

    def test_process_exit_after_commit_can_be_retried_without_repeating_deletion(self) -> None:
        import subprocess
        import sys

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, RecheckSource([listing()], {}), now=lambda: NOW)
        script = '''
import os, sys
from pathlib import Path
from opportunity_intake import SQLiteStore
with SQLiteStore(Path(sys.argv[1])) as store:
    store.delete_source_data("Freelancer", project_id="42")
    os._exit(78)
'''
        exited = subprocess.run([sys.executable, "-c", script, str(self.database)], capture_output=True, text=True)
        self.assertEqual(exited.returncode, 78, exited.stderr)
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.candidates(), [])
            result = store.delete_source_data("Freelancer", project_id="42")
            self.assertEqual(result.candidates_deleted, 0)
            self.assertEqual(result.history_entries_redacted, 0)
            self.assertEqual(result.status, "complete")
