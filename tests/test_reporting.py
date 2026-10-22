"""Observation acceptance through reporting, complete runs and public scheduling."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from opportunity_intake import Config, SQLiteStore, collect
from opportunity_intake.reporting import observation_report
from tests.test_collection import NOW, Source, project


class ReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"

    def test_daily_and_period_deduplicate_overlap_and_latest_observed_fields(self) -> None:
        unknown = {"id": 99}
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Source([project(), unknown]), now=lambda: NOW)
        changed = project()
        changed["description"] = "A different paid drawing brief"
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Source([changed]), now=lambda: NOW + timedelta(days=1))
            result = observation_report(store, start=NOW, end=NOW + timedelta(days=2), now=lambda: NOW + timedelta(days=2))
        total = result["total"]
        self.assertEqual(total["runs"], 2)
        self.assertEqual(total["statuses"]["success"], 2)
        self.assertEqual(total["unique_new_candidates"], 2)
        self.assertEqual(total["candidate_observations"], 3)
        self.assertEqual(total["unique_observed_candidates"], 2)
        self.assertEqual(total["recent_candidates"], 1)
        self.assertEqual(total["field_coverage"]["budget"], {"known": 1, "partial": 0, "unknown": 1, "invalid": 0, "denominator": 2, "known_fraction": 0.5})
        self.assertEqual(total["changed_observations"], 1)
        self.assertEqual([day["runs"] for day in result["daily"]], [1, 1, 0])
        self.assertEqual([day["unique_new_candidates"] for day in result["daily"]], [2, 0, 0])
        self.assertEqual(result["scope"]["queries"], ["illustration", "portrait"])
        self.assertEqual(result["current_candidates"]["count"], 2)

    def test_cross_run_failure_end_deletion_and_stopped_schedule_are_auditable(self) -> None:
        import json
        from typing import Any
        from opportunity_intake.scheduling import Scheduler
        from opportunity_intake.source import SourceError
        from tests.test_rechecks import RecheckSource, listing

        class Partial(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                if query == "portrait":
                    raise SourceError("http_error", 503)
                return self.projects

        time = NOW
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: time)
            scheduler.start(Config(recheck_limit=0), interval_seconds=3600, max_runs=3)
            scheduler.tick(Source([listing(1), {"id": 2}]))
            scheduler.control("pause")
        time += timedelta(days=1)
        changed = listing(1)
        changed["description"] = "CHANGED PRIVATE DESCRIPTION"
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: time)
            scheduler.control("resume")
            scheduler.tick(Partial([changed, listing(3)]))
            scheduler.control("stop")
            collect(Config(queries=("portrait",), max_requests=1, recheck_limit=1), store,
                    RecheckSource([], {"1": listing(1, "closed")}), now=lambda: time + timedelta(hours=1))
            store.delete_source_data("Freelancer", project_id="2")
        with SQLiteStore(self.database) as store:
            report = observation_report(store, start=NOW, end=NOW + timedelta(days=2), now=lambda: NOW + timedelta(days=2))
            self.assertEqual([row["id"] for row in store.candidates()], ["3"])
            self.assertEqual(len(store.ended_records()), 1)
        total = report["total"]
        self.assertEqual(total["statuses"], {"success": 1, "partial": 2, "failed": 0, "skipped": 0, "running": 0})
        self.assertEqual(total["requests"], {"attempted": 5, "succeeded": 4, "failed": 1})
        self.assertEqual(total["request_errors"], [{"kind": "http_error", "http_status": 503, "count": 1}])
        self.assertEqual(total["new_observations"], 3)
        self.assertIsNone(total["unique_new_candidates"])
        self.assertEqual(total["identifiable_unique_new_candidates"], 2)
        self.assertEqual(total["redacted_candidate_observations"], 1)
        self.assertEqual(total["confirmed_ended"], 1)
        self.assertEqual(total["rechecks"]["succeeded"], 1)
        self.assertEqual(total["observation_gap_seconds"], 23 * 3600)
        self.assertEqual([day["observation_gap_seconds"] for day in report["daily"]], [11 * 3600, 12 * 3600, 0])
        self.assertEqual(report["current_candidates"]["count"], 1)
        self.assertEqual(report["current_candidates"]["status_counts"], {"未核实": 1})
        self.assertEqual(len(report["run_diagnostics"]), 3)
        self.assertEqual(report["run_diagnostics"][1]["search_requests"][1]["status"], "failed")
        self.assertEqual(report["schedules"][0]["status"], "stopped")
        self.assertNotIn("CHANGED PRIVATE DESCRIPTION", json.dumps(report))
        self.assertNotIn("character-portrait", json.dumps(report))
        self.assertNotIn('"candidate_results"', json.dumps(report))

    def test_utc_half_open_range_empty_days_and_current_recency_are_explicit(self) -> None:
        from datetime import timezone
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Source([project(), {"id": 99}]), now=lambda: NOW)
            collect(Config(recheck_limit=0), store, Source([]), now=lambda: NOW + timedelta(days=1))
            result = observation_report(store, start=NOW.astimezone(timezone(timedelta(hours=-7))),
                                        end=NOW + timedelta(days=1), now=lambda: NOW + timedelta(days=10))
            self.assertEqual(result["total"]["runs"], 1)
            self.assertEqual(result["scope"]["start"], NOW.isoformat())
            self.assertEqual(result["current_candidates"]["recency"], {"older": 1, "unknown": 1})
            self.assertEqual(result["total"]["recent_candidates"], 1)
            empty = observation_report(store, start=NOW - timedelta(days=2), end=NOW, now=lambda: NOW)
            self.assertEqual(empty["total"]["unique_new_candidates"], 0)
            self.assertIsNone(empty["total"]["field_coverage"]["budget"]["known_fraction"])
            self.assertEqual(len(empty["daily"]), 3)
            for start, end in [(NOW, NOW), (NOW, NOW - timedelta(seconds=1)), (NOW.replace(tzinfo=None), NOW)]:
                with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                    observation_report(store, start=start, end=end)

    def test_report_cli_exports_json_and_rejects_invalid_or_missing_state(self) -> None:
        import json
        import subprocess
        import sys
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Source([project()]), now=lambda: NOW)
        command = [sys.executable, "-m", "opportunity_intake", "report", "--state", str(self.database),
                   "--start", NOW.isoformat(), "--end", (NOW + timedelta(days=1)).isoformat()]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["total"]["unique_new_candidates"], 1)
        self.assertNotIn("Paid portrait commission", result.stdout)
        self.assertEqual(subprocess.run(command[:-1] + [NOW.isoformat()], capture_output=True).returncode, 2)
        missing = self.database.with_name("absent.sqlite3")
        command[5] = str(missing)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertFalse(missing.exists())

    def test_interrupted_run_and_prior_plan_remain_visible_after_new_plan(self) -> None:
        from typing import Any
        from opportunity_intake.scheduling import Scheduler

        class Interrupted(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise KeyboardInterrupt()

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: NOW)
            old = scheduler.start(Config(recheck_limit=0), interval_seconds=60, max_runs=1)
            with self.assertRaises(KeyboardInterrupt):
                scheduler.tick(Interrupted([]))
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: NOW + timedelta(days=1))
            scheduler.tick(Source([]))
            scheduler.start(Config(recheck_limit=0), interval_seconds=60, max_runs=1)
            scheduler.tick(Source([]))
            result = observation_report(store, start=NOW, end=NOW + timedelta(days=2), now=lambda: NOW + timedelta(days=2))
        self.assertEqual(len(result["schedules"]), 2)
        self.assertEqual(result["schedules"][0]["id"], old.id)
        self.assertEqual(result["total"]["statuses"]["running"], 1)
        self.assertEqual(result["total"]["known_interrupted_runs"], 1)
        self.assertEqual(result["daily"][0]["known_interrupted_runs"], 1)
        self.assertEqual(result["daily"][1]["schedule_events"]["interrupted_run"], 1)
        self.assertEqual(result["total"]["requests"], {"attempted": 3, "succeeded": 2, "failed": 0})
        self.assertEqual(result["total"]["requests_without_saved_outcome"], 1)

    def test_rate_limit_failure_and_cooldown_skip_do_not_look_like_empty_success(self) -> None:
        from typing import Any
        from opportunity_intake.source import SourceError

        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="60")

        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Limited([]), now=lambda: NOW)
            collect(Config(recheck_limit=0), store, Source([]), now=lambda: NOW + timedelta(seconds=1))
            result = observation_report(store, start=NOW, end=NOW + timedelta(minutes=1), now=lambda: NOW + timedelta(minutes=1))
        total = result["total"]
        self.assertEqual(total["statuses"], {"success": 0, "partial": 0, "failed": 1, "skipped": 1, "running": 0})
        self.assertEqual(total["requests"], {"attempted": 1, "succeeded": 0, "failed": 1})
        self.assertEqual(total["unique_new_candidates"], 0)
        self.assertEqual(result["run_diagnostics"][1]["skip_reason"], "source_cooldown")

    def test_deleted_identity_reentry_does_not_claim_two_unique_new_candidates(self) -> None:
        with SQLiteStore(self.database) as store:
            collect(Config(recheck_limit=0), store, Source([project()]), now=lambda: NOW)
            store.delete_source_data("Freelancer", project_id="42")
            collect(Config(recheck_limit=0), store, Source([project()]), now=lambda: NOW + timedelta(hours=1))
            result = observation_report(store, start=NOW, end=NOW + timedelta(days=1), now=lambda: NOW + timedelta(days=1))
        total = result["total"]
        self.assertEqual(total["new_observations"], 2)
        self.assertEqual(total["identifiable_unique_new_candidates"], 1)
        self.assertIsNone(total["unique_new_candidates"])
        self.assertFalse(total["unique_counts_complete"])
        self.assertEqual(total["candidate_observations"], 2)
        self.assertEqual(total["field_coverage"]["budget"]["denominator"], 1)
        self.assertEqual(result["current_candidates"]["count"], 1)
