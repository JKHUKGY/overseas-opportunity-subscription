"""Incremental collection acceptance tests through complete runs and public reads."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from opportunity_intake import Config, SQLiteStore, collect
from tests.test_collection import NOW, Source, project


class IncrementalTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = Path(__file__).resolve().parents[1] / "temp"
        scratch.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_same_content_preserves_version_and_existing_processing_across_restart(self) -> None:
        with SQLiteStore(self.database) as store:
            first = collect(Config(), store, Source([project()]), now=lambda: NOW)
            saved = store.candidates()[0]
            self.assertEqual(saved["content_version"], 1)
            self.assertEqual(saved["last_change"], "new")
            self.assertEqual((first.new_count, first.unchanged_count, first.changed_count), (1, 0, 0))
            # A pre-existing processing result is a fixture, not a new product workflow.
            saved.update(processing_status="reviewed", classification="drawing", summary="Known summary")
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("UPDATE candidates SET payload = ?", (json.dumps(saved),))
        with SQLiteStore(self.database) as store:
            repeated = collect(Config(), store, Source([project()]), now=lambda: NOW + timedelta(hours=1))
            saved = store.candidates()[0]
            self.assertEqual(saved["content_version"], 1)
            self.assertEqual(saved["last_change"], "unchanged")
            self.assertEqual(saved["first_seen_at"], NOW.isoformat())
            self.assertEqual(saved["summary"], "Known summary")
            self.assertEqual(saved["classification"], "drawing")
            self.assertEqual(saved["processing_status"], "reviewed")
            self.assertEqual((repeated.new_count, repeated.unchanged_count, repeated.changed_count), (0, 1, 0))

    def test_changed_description_invalidates_processing_once_per_unique_candidate(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            saved = store.candidates()[0]
            saved.update(processing_status="reviewed", classification="drawing", summary="Old summary",
                         last_status_verified_at=NOW.isoformat())
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("UPDATE candidates SET payload = ?", (json.dumps(saved),))
            changed = project()
            changed["description"] = "Paid commission for a full character sheet."
            report = collect(Config(), store, Source([changed]), now=lambda: NOW + timedelta(hours=1))
            candidate = store.candidates()[0]
            self.assertEqual(candidate["content_version"], 2)
            self.assertEqual(candidate["last_change"], "changed")
            self.assertEqual(candidate["description"], changed["description"])
            self.assertIsNone(candidate["summary"])
            self.assertIsNone(candidate["classification"])
            self.assertEqual(candidate["processing_status"], "pending")
            self.assertEqual(candidate["first_seen_at"], NOW.isoformat())
            self.assertEqual(candidate["last_status_verified_at"], NOW.isoformat())
            self.assertEqual((report.new_count, report.unchanged_count, report.changed_count), (0, 0, 1))
            self.assertEqual(len(store.candidates()), 1)
            self.assertNotIn("full character sheet", json.dumps(store.runs()))
            self.assertNotIn("Old summary", json.dumps(store.runs()))

    def test_other_processing_inputs_also_advance_content_version(self) -> None:
        changes: list[dict[str, Any]] = [
            {"title": "Draw a landscape"},
            {"budget": {"minimum": 75, "maximum": 150}},
            {"currency": {"code": "EUR"}},
            {"type": "hourly"},
        ]
        for index, fields in enumerate(changes):
            with self.subTest(fields=fields), SQLiteStore(self.database.with_name(f"fields-{index}.sqlite3")) as store:
                collect(Config(), store, Source([project()]), now=lambda: NOW)
                changed = project()
                changed.update(fields)
                report = collect(Config(), store, Source([changed]), now=lambda: NOW)
                self.assertEqual(store.candidates()[0]["content_version"], 2)
                self.assertEqual(report.changed_count, 1)

    def test_recent_window_uses_source_time_inclusive_boundaries_and_unique_ids(self) -> None:
        timestamps = [NOW - timedelta(days=3), NOW - timedelta(days=3, seconds=1),
                      NOW, NOW + timedelta(seconds=1), None, "invalid"]
        projects = []
        for index, value in enumerate(timestamps):
            item = project(index + 1)
            item["time_submitted"] = value.timestamp() if isinstance(value, datetime) else value
            projects.append(item)
        with SQLiteStore(self.database) as store:
            report = collect(Config(limit=10), store, Source(projects), now=lambda: NOW)
            saved = {row["id"]: row for row in store.candidates()}
            self.assertEqual([saved[str(i)]["recency"] for i in range(1, 7)],
                             ["recent", "older", "recent", "future", "unknown", "unknown"])
            self.assertEqual(report.recent_count, 2)
            self.assertEqual(report.unique_count, 6)
            self.assertEqual(report.recent_window_start, "2026-10-17T12:00:00+00:00")
            self.assertEqual(report.recent_window_end, "2026-10-20T12:00:00+00:00")
            self.assertEqual(report.statistics_timezone, "UTC")
            self.assertIsNone(saved["5"]["published_at"])
            self.assertIsNone(saved["6"]["published_at"])
            self.assertEqual(saved["5"]["field_status"]["published_at"], "unknown")
            self.assertEqual(saved["6"]["field_status"]["published_at"], "invalid")
            self.assertEqual(report.field_counts["published_at"], {"known": 4, "unknown": 1, "invalid": 1})

    def test_budget_units_missing_fields_and_region_are_not_inferred(self) -> None:
        fixed = project(1)
        hourly = project(2)
        hourly.update(type="hourly", budget={"minimum": 20, "maximum": 40})
        unknown = {"id": 3, "bid_stats": {"bid_avg": 999}, "international": True}
        partial = project(4)
        partial["budget"] = {"minimum": 50}
        invalid = project(5)
        invalid.update(budget={"minimum": 200, "maximum": 100}, type="unrecognized")
        with SQLiteStore(self.database) as store:
            report = collect(Config(limit=10), store, Source([fixed, hourly, unknown, partial, invalid]), now=lambda: NOW)
            saved = {row["id"]: row for row in store.candidates()}
            self.assertEqual((saved["1"]["budget_min"], saved["1"]["budget_max"], saved["1"]["currency"], saved["1"]["pricing"]),
                             (50, 100, "USD", "fixed"))
            self.assertEqual((saved["2"]["budget_min"], saved["2"]["budget_max"], saved["2"]["pricing"]), (20, 40, "hourly"))
            for name in ("budget_min", "budget_max", "currency", "pricing"):
                self.assertIsNone(saved["3"][name])
            self.assertIsNone(saved["4"]["budget_max"])
            self.assertIsNone(saved["5"]["budget_min"])
            self.assertIsNone(saved["5"]["budget_max"])
            self.assertIsNone(saved["5"]["pricing"])
            self.assertEqual(report.field_counts["budget"], {"known": 2, "unknown": 1, "partial": 1, "invalid": 1})
            self.assertEqual(report.field_counts["region"], {"unknown": 5})
            for candidate in saved.values():
                self.assertEqual(candidate["region"], "地域未说明")
                self.assertEqual(candidate["processing_status"], "pending")
                self.assertIsNone(candidate["summary"])
                self.assertIsNone(candidate["classification"])
                self.assertNotIn("budget_cny", candidate)

    def test_cross_query_changes_have_disjoint_counts_and_latest_field_state(self) -> None:
        changed = project()
        changed["description"] = "Updated paid portrait commission."
        newly_changed = project(43)
        newly_changed["description"] = "Second description in the same run."

        class Overlapping:
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                return [project(), project(43)] if query == "illustration" else [changed, newly_changed, {"id": 44}]

        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            report = collect(Config(), store, Overlapping(), now=lambda: NOW)
            self.assertEqual((report.new_count, report.unchanged_count, report.changed_count, report.unique_count), (2, 0, 1, 3))
            self.assertEqual(report.duplicate_count, 3)
            self.assertEqual(report.field_counts["description"], {"known": 2, "unknown": 1})
            saved = {row["id"]: row for row in store.candidates()}
            self.assertEqual((saved["42"]["content_version"], saved["43"]["content_version"]), (2, 2))
            self.assertEqual((saved["42"]["last_change"], saved["43"]["last_change"]), ("changed", "new"))
            repeated = collect(Config(), store, Source([changed, newly_changed, {"id": 44}]), now=lambda: NOW)
            self.assertEqual((repeated.new_count, repeated.unchanged_count, repeated.changed_count), (0, 3, 0))

    def test_source_publication_correction_does_not_reset_discovery_or_verification_time(self) -> None:
        original = project()
        original["time_submitted"] = (NOW - timedelta(days=10)).timestamp()
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([original]), now=lambda: NOW)
            corrected = project()
            corrected["time_submitted"] = (NOW - timedelta(hours=1)).timestamp()
            report = collect(Config(), store, Source([corrected]), now=lambda: NOW + timedelta(hours=2))
            saved = store.candidates()[0]
            self.assertEqual(saved["published_at"], "2026-10-20T11:00:00+00:00")
            self.assertEqual(saved["first_seen_at"], "2026-10-20T12:00:00+00:00")
            self.assertEqual(saved["last_read_at"], "2026-10-20T14:00:00+00:00")
            self.assertIsNone(saved["last_status_verified_at"])
            self.assertEqual(report.recent_count, 1)
            self.assertEqual(saved["content_version"], 1)

    def test_timezone_and_recency_use_one_run_start_instant(self) -> None:
        local = NOW.astimezone(timezone(timedelta(hours=-7)))
        item = project()
        item["time_submitted"] = (NOW - timedelta(days=3)).timestamp()
        moments = iter([local, local + timedelta(minutes=1), local + timedelta(minutes=2)])
        with SQLiteStore(self.database) as store:
            report = collect(Config(queries=("portrait",)), store, Source([item]), now=lambda: next(moments))
            self.assertEqual(report.started_at, NOW.isoformat())
            self.assertEqual(report.recent_count, 1)
            self.assertEqual(store.candidates()[0]["recency_as_of"], NOW.isoformat())
            self.assertEqual(store.candidates()[0]["last_read_at"], "2026-10-20T12:01:00+00:00")

    def test_invalid_source_timestamps_remain_unknown_in_saved_results(self) -> None:
        invalid_values = [None, "not a date", True, float("inf"), float("nan"), 1e100]
        projects = []
        for index, value in enumerate(invalid_values):
            item = project(index + 1)
            item["time_submitted"] = value
            projects.append(item)
        with SQLiteStore(self.database) as store:
            report = collect(Config(limit=10), store, Source(projects), now=lambda: NOW)
            self.assertEqual(report.recent_count, 0)
            self.assertEqual(report.field_counts["published_at"], {"unknown": 1, "invalid": 5})
            self.assertTrue(all(row["published_at"] is None for row in store.candidates()))
            self.assertEqual(report.invalid_count, 0)

    def test_legacy_candidate_adopts_version_without_losing_processing_and_cli_shows_it(self) -> None:
        import subprocess
        import sys

        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([project()]), now=lambda: NOW)
            legacy = store.candidates()[0]
            for name in ("content_version", "last_change", "field_status", "recency", "recency_as_of"):
                legacy.pop(name)
            legacy.update(processing_status="reviewed", summary="Legacy summary", classification="drawing")
            with sqlite3.connect(str(self.database)) as setup:
                setup.execute("UPDATE candidates SET payload = ?", (json.dumps(legacy),))
        with SQLiteStore(self.database) as store:
            report = collect(Config(), store, Source([project()]), now=lambda: NOW + timedelta(days=1))
            self.assertEqual(report.unchanged_count, 1)
            self.assertEqual(report.changed_count, 0)
        result = subprocess.run([sys.executable, "-m", "opportunity_intake", "list", "--state", str(self.database)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        candidate = json.loads(result.stdout)[0]
        self.assertEqual(candidate["content_version"], 1)
        self.assertEqual(candidate["summary"], "Legacy summary")
        self.assertEqual(candidate["last_change"], "unchanged")
        self.assertEqual(candidate["recency_as_of"], "2026-10-21T12:00:00+00:00")
        self.assertEqual(candidate["field_status"]["budget"], "known")

    def test_missing_or_invalid_later_time_preserves_last_verified_publication(self) -> None:
        original = project()
        original["time_submitted"] = (NOW - timedelta(hours=1)).timestamp()
        with SQLiteStore(self.database) as store:
            collect(Config(), store, Source([original]), now=lambda: NOW)
            for offset, missing_time in enumerate((None, "invalid", float("inf")), 1):
                with self.subTest(missing_time=missing_time):
                    later = project()
                    later["time_submitted"] = missing_time
                    report = collect(Config(), store, Source([later]), now=lambda: NOW + timedelta(hours=offset))
                    saved = store.candidates()[0]
                    self.assertEqual(saved["published_at"], "2026-10-20T11:00:00+00:00")
                    self.assertEqual(saved["published_at_read_at"], NOW.isoformat())
                    self.assertEqual(saved["field_status"]["published_at"], "unknown" if missing_time is None else "invalid")
                    self.assertEqual(saved["recency"], "unknown")
                    self.assertEqual(report.recent_count, 0)
                    self.assertEqual(saved["first_seen_at"], NOW.isoformat())
                    self.assertEqual(saved["content_version"], 1)
