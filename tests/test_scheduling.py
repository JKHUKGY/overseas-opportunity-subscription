"""Scheduling through public controls, real storage and a controllable clock."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from opportunity_intake import Config, SQLiteStore
from opportunity_intake.scheduling import Scheduler
from tests.test_collection import NOW, Source, project


class SchedulingTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "state.sqlite3"
        self.time = NOW
        self.config = Config(queries=("portrait",), recheck_limit=0, max_requests=1, max_seconds=5)

    def test_due_runs_reuse_collection_and_preserve_limit_across_restart(self) -> None:
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            state = scheduler.start(self.config, interval_seconds=60, max_runs=2)
            self.assertEqual(state.status, "active")
            self.assertEqual(store.runs(), [])
            result = scheduler.tick(Source([project()]))
            self.assertEqual(result.status, "ran")
            self.assertEqual(result.schedule.runs_started, 1)
            self.assertEqual(len(store.candidates()), 1)
            self.assertEqual(scheduler.tick(Source([])).status, "not_due")
        self.time += timedelta(seconds=60)
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            result = scheduler.tick(Source([project()]))
            self.assertEqual(result.schedule.status, "completed")
            self.assertEqual(result.schedule.completed_runs, 2)
            self.assertEqual(len(store.candidates()), 1)
            self.assertEqual(store.runs()[-1]["new_count"], 0)
            self.assertEqual(scheduler.tick(Source([])).status, "completed")
            self.assertEqual(len(store.runs()), 2)

    def test_schedule_requires_valid_bounds_and_rejects_replacing_active_progress(self) -> None:
        from typing import Any
        invalid: list[dict[str, Any]] = [
            {"interval_seconds": 60}, {"interval_seconds": 0, "max_runs": 1},
            {"interval_seconds": float("nan"), "max_runs": 1},
            {"interval_seconds": 60, "max_runs": True}, {"interval_seconds": 60, "max_runs": -1},
            {"interval_seconds": 60, "until": NOW},
            {"interval_seconds": 60, "until": NOW.replace(tzinfo=None)},
        ]
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            for options in invalid:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    scheduler.start(self.config, **options)
                self.assertIsNone(store.schedule())
            original = scheduler.start(self.config, interval_seconds=60, max_runs=1)
            with self.assertRaises(ValueError):
                scheduler.start(self.config, interval_seconds=10, max_runs=10)
            self.assertEqual(scheduler.status(), original)

    def test_pause_resume_and_stop_preserve_counts_and_expose_observation_gap(self) -> None:
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=3)
            scheduler.tick(Source([]))
            scheduler.control("pause")
        self.time += timedelta(seconds=180)
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            self.assertEqual(scheduler.tick(Source([])).status, "paused")
            self.assertEqual(scheduler.status().runs_started, 1)
            scheduler.control("resume")
            result = scheduler.tick(Source([]))
            self.assertEqual(result.schedule.runs_started, 2)
            gaps = [event for event in result.schedule.events if event["kind"] == "observation_gap"]
            self.assertEqual(gaps[0]["from"], "2026-10-20T12:01:00+00:00")
            self.assertEqual(gaps[0]["to"], "2026-10-20T12:03:00+00:00")
            self.assertEqual(gaps[0]["overdue_intervals"], 2)
            self.assertEqual(len(store.runs()), 2)
            scheduler.control("stop")
            self.time += timedelta(days=1)
            self.assertEqual(scheduler.tick(Source([])).status, "stopped")
            with self.assertRaises(ValueError):
                scheduler.control("resume")

    def test_end_time_bounds_source_window_and_expired_pause_cannot_resume_work(self) -> None:
        from typing import Any
        owner = self

        class Slow(Source):
            timeouts: list[float] = []

            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                self.timeouts.append(timeout)
                owner.time += timedelta(seconds=4)
                return []

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time, clock=lambda: (self.time - NOW).total_seconds())
            scheduler.start(Config(recheck_limit=0, max_seconds=20), interval_seconds=60, until=NOW + timedelta(seconds=3))
            source = Slow([])
            result = scheduler.tick(source)
            self.assertEqual(source.timeouts, [3])
            self.assertEqual(result.schedule.status, "completed")
            self.assertEqual(store.runs()[0]["requests_attempted"], 1)
            self.assertEqual(scheduler.tick(source).status, "completed")
            scheduler.start(self.config, interval_seconds=60, until=self.time + timedelta(seconds=10))
            scheduler.control("pause")
            self.time += timedelta(seconds=10)
            self.assertEqual(scheduler.control("resume").status, "completed")
            self.assertEqual(scheduler.tick(source).status, "completed")
            self.assertEqual(len(store.runs()), 1)

    def test_rate_limit_defers_future_dispatch_without_spending_run_budget(self) -> None:
        from opportunity_intake.source import SourceError
        from typing import Any

        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="120")

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=30, max_runs=2)
            first = scheduler.tick(Limited([]))
            self.assertEqual(first.schedule.last_result, "failed")
            self.assertEqual(first.schedule.next_run_at, "2026-10-20T12:02:00+00:00")
        self.time += timedelta(seconds=60)
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            self.assertEqual(scheduler.tick(Source([])).status, "not_due")
            self.assertEqual(scheduler.status().runs_started, 1)
            self.assertEqual(len(store.runs()), 1)
            self.assertTrue(any(event["kind"] == "source_cooldown" for event in scheduler.status().events))
            self.time += timedelta(seconds=60)
            self.assertEqual(scheduler.tick(Source([])).schedule.status, "completed")
            self.assertEqual(len(store.runs()), 2)

    def test_overlapping_schedule_manual_run_and_deletion_cannot_modify_active_run(self) -> None:
        from typing import Any
        from opportunity_intake import StorageError, collect
        owner = self

        class Overlap(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                with SQLiteStore(owner.database) as other:
                    nested = Scheduler(other, now=lambda: owner.time).tick(Source([]))
                    owner.assertEqual(nested.status, "overlap")
                    manual = collect(owner.config, other, Source([]), now=lambda: owner.time)
                    owner.assertEqual(manual.skip_reason, "state_busy")
                    with owner.assertRaises(StorageError):
                        other.delete_source_data("Freelancer", project_id="42")
                return [project()]

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=2)
            result = scheduler.tick(Overlap([]))
            self.assertEqual(result.schedule.runs_started, 1)
            self.assertEqual(len(store.runs()), 1)
            self.assertEqual(len(store.candidates()), 1)
            self.assertTrue(any(event["kind"] == "overlap" for event in result.schedule.events))

    def test_crashed_run_keeps_saved_batch_consumes_attempt_and_releases_process_lock(self) -> None:
        import subprocess
        import sys
        script = '''
import os, sys
from pathlib import Path
from opportunity_intake import Config, SQLiteStore
from opportunity_intake.scheduling import Scheduler
from tests.test_collection import NOW, Source, project
class Interrupted(Source):
    def search(self, query, limit, offset, timeout):
        if query == "second":
            os._exit(77)
        return [project()]
with SQLiteStore(Path(sys.argv[1])) as store:
    scheduler = Scheduler(store, now=lambda: NOW)
    scheduler.start(Config(queries=("first", "second"), recheck_limit=0), interval_seconds=60, max_runs=2)
    scheduler.tick(Interrupted([]))
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.database)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.time += timedelta(seconds=120)
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            self.assertEqual(scheduler.status().runs_started, 1)
            self.assertEqual(len(store.candidates()), 1)
            self.assertEqual(store.runs()[0]["status"], "running")
            result2 = scheduler.tick(Source([project()]))
            self.assertEqual(result2.schedule.runs_started, 2)
            self.assertEqual(result2.schedule.completed_runs, 1)
            self.assertEqual(result2.schedule.status, "completed")
            self.assertIsNone(result2.schedule.inflight_run_id)
            self.assertTrue(any(event["kind"] == "interrupted_run" for event in result2.schedule.events))
            self.assertEqual(len(store.candidates()), 1)
            self.assertEqual(len(store.runs()), 2)

    def test_control_during_collection_survives_completion_and_manual_overlap_costs_no_attempt(self) -> None:
        from opportunity_intake import collect
        from typing import Any
        owner = self

        class PauseDuringRead(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                with SQLiteStore(owner.database) as other:
                    Scheduler(other, now=lambda: owner.time).control("pause")
                return []

        class ManualRead(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                with SQLiteStore(owner.database) as other:
                    result = Scheduler(other, now=lambda: owner.time).tick(Source([]))
                    owner.assertEqual(result.status, "overlap")
                    owner.assertEqual(result.schedule.runs_started, 0)
                    owner.assertIsNone(result.schedule.last_run_id)
                return []

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=2)
            collect(self.config, store, ManualRead([]), now=lambda: self.time)
            result = scheduler.tick(PauseDuringRead([]))
            self.assertEqual(result.schedule.status, "paused")
            self.assertEqual(result.schedule.completed_runs, 1)
            self.assertEqual(len(store.runs()), 2)

    def test_saved_run_completion_is_reconciled_without_replaying_after_schedule_write_failure(self) -> None:
        import sqlite3
        from opportunity_intake import StorageError

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=1)
            with sqlite3.connect(str(self.database)) as fault:
                fault.execute('''CREATE TRIGGER fail_schedule_finish BEFORE UPDATE ON schedules
                    WHEN instr(NEW.payload, '"completed_runs": 1') > 0
                    BEGIN SELECT RAISE(ABORT, 'injected'); END''')
            with self.assertRaises(StorageError):
                scheduler.tick(Source([project()]))
            self.assertEqual(len(store.runs()), 1)
            self.assertEqual(store.runs()[0]["status"], "success")
            self.assertIsNotNone(scheduler.status().inflight_run_id)
        with sqlite3.connect(str(self.database)) as fault:
            fault.execute("DROP TRIGGER fail_schedule_finish")
        with SQLiteStore(self.database) as store:
            result = Scheduler(store, now=lambda: self.time).tick(Source([]))
            self.assertEqual(result.schedule.status, "completed")
            self.assertEqual(result.schedule.runs_started, 1)
            self.assertEqual(result.schedule.completed_runs, 1)
            self.assertEqual(len(store.runs()), 1)
            self.assertTrue(any(event["kind"] == "recovered_completion" for event in result.schedule.events))

    def test_foreground_worker_uses_controlled_wait_and_stops_at_limit(self) -> None:
        waited: list[float] = []

        def wait(seconds: float) -> None:
            waited.append(seconds)
            self.time += timedelta(seconds=seconds)

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=3)
            result = scheduler.work(Source([]), wait=wait)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.schedule.completed_runs, 3)
            self.assertEqual(sum(waited), 120)
            self.assertEqual([run["started_at"] for run in store.runs()], [
                "2026-10-20T12:00:00+00:00", "2026-10-20T12:01:00+00:00", "2026-10-20T12:02:00+00:00"])

    def test_cli_start_requires_budgets_and_controls_do_not_launch_collection(self) -> None:
        import json
        import subprocess
        import sys

        command = [sys.executable, "-m", "opportunity_intake", "schedule"]
        invalid = subprocess.run(command + ["start", "--state", str(self.database), "--interval-seconds", "60", "--max-runs", "2"], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertFalse(self.database.exists())
        started = subprocess.run(command + ["start", "--state", str(self.database), "--interval-seconds", "60", "--max-runs", "2", "--max-requests", "1", "--max-seconds", "5"], capture_output=True, text=True)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(json.loads(started.stdout)["status"], "active")
        for action, status in (("pause", "paused"), ("status", "paused"), ("resume", "active"), ("stop", "stopped")):
            result = subprocess.run(command + [action, "--state", str(self.database)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], status)
        with SQLiteStore(self.database) as store:
            self.assertEqual(store.runs(), [])
            self.assertEqual(store.candidates(), [])
        result = subprocess.run(command + ["work", "--state", str(self.database)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "stopped")

    def test_preexisting_cooldown_can_reach_observation_end_without_any_dispatch(self) -> None:
        from opportunity_intake import collect
        from opportunity_intake.source import SourceError
        from typing import Any

        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="120")

        def wait(seconds: float) -> None:
            self.time += timedelta(seconds=seconds)

        with SQLiteStore(self.database) as store:
            collect(self.config, store, Limited([]), now=lambda: self.time)
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=30, until=NOW + timedelta(seconds=60))
            self.assertEqual(scheduler.tick(Source([])).status, "deferred")
            result = scheduler.work(Source([]), wait=wait)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.schedule.runs_started, 0)
            self.assertEqual(self.time, NOW + timedelta(seconds=60))
            self.assertEqual(len(store.runs()), 1)

    def test_another_process_observes_schedule_lock_and_does_not_collect(self) -> None:
        import subprocess
        import sys
        from typing import Any
        owner = self
        script = '''
import sys
from pathlib import Path
from opportunity_intake import SQLiteStore
from opportunity_intake.scheduling import Scheduler
from tests.test_collection import NOW, Source
with SQLiteStore(Path(sys.argv[1])) as store:
    result = Scheduler(store, now=lambda: NOW).tick(Source([]))
    print(result.status)
'''

        class Checking(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                result = subprocess.run([sys.executable, "-c", script, str(owner.database)], capture_output=True, text=True, timeout=10)
                owner.assertEqual(result.returncode, 0, result.stderr)
                owner.assertEqual(result.stdout.strip(), "overlap")
                return []

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=1)
            result = scheduler.tick(Checking([]))
            self.assertEqual(result.schedule.runs_started, 1)
            self.assertEqual(len(store.runs()), 1)

    def test_restarting_after_observation_end_records_gap_without_late_collection(self) -> None:
        with SQLiteStore(self.database) as store:
            Scheduler(store, now=lambda: self.time).start(self.config, interval_seconds=60, until=NOW + timedelta(seconds=180))
        self.time += timedelta(seconds=300)
        with SQLiteStore(self.database) as store:
            result = Scheduler(store, now=lambda: self.time).tick(Source([]))
            self.assertEqual(result.status, "completed")
            self.assertEqual(store.runs(), [])
            gaps = [event for event in result.schedule.events if event["kind"] == "observation_gap"]
            self.assertEqual(gaps[0]["from"], NOW.isoformat())
            self.assertEqual(gaps[0]["to"], "2026-10-20T12:03:00+00:00")

    def test_worker_does_not_adopt_a_new_plan_created_while_waiting(self) -> None:
        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            original = scheduler.start(self.config, interval_seconds=60, max_runs=2)

            def replace_plan(seconds: float) -> None:
                scheduler.control("stop")
                scheduler.start(self.config, interval_seconds=60, max_runs=1)
                self.time += timedelta(seconds=seconds)

            result = scheduler.work(Source([]), wait=replace_plan)
            self.assertEqual(result.status, "schedule_changed")
            self.assertNotEqual(result.schedule.id, original.id)
            self.assertEqual(result.schedule.status, "active")
            self.assertEqual(result.schedule.runs_started, 0)
            self.assertEqual(len(store.runs()), 1)

    def test_cooldown_deferral_preserves_the_gap_before_the_late_trigger(self) -> None:
        from opportunity_intake import collect
        from opportunity_intake.source import SourceError
        from typing import Any

        class Limited(Source):
            def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
                raise SourceError("http_error", 429, retry_after="120")

        with SQLiteStore(self.database) as store:
            scheduler = Scheduler(store, now=lambda: self.time)
            scheduler.start(self.config, interval_seconds=60, max_runs=1)
            self.time += timedelta(seconds=120)
            collect(self.config, store, Limited([]), now=lambda: self.time)
            self.time += timedelta(seconds=60)
            result = scheduler.tick(Source([]))
            self.assertEqual(result.status, "deferred")
            self.assertEqual(result.schedule.runs_started, 0)
            gaps = [event for event in result.schedule.events if event["kind"] == "observation_gap"]
            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0]["from"], NOW.isoformat())
            self.assertEqual(gaps[0]["to"], "2026-10-20T12:03:00+00:00")
            self.time += timedelta(seconds=60)
            result = scheduler.tick(Source([]))
            self.assertEqual(result.schedule.status, "completed")
            self.assertEqual(sum(event["kind"] == "observation_gap" for event in result.schedule.events), 1)
