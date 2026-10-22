"""Persistent bounded schedules calling the existing complete collection entry."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from math import isfinite
from time import monotonic, sleep
from typing import Any, Callable, Optional
from uuid import uuid4

from .collector import ProjectSource, collect, utc_now
from .models import Config, ScheduleState, TickResult
from .storage import SQLiteStore


class Scheduler:
    def __init__(self, store: SQLiteStore, *, now: Callable[[], datetime] = utc_now,
                 clock: Callable[[], float] = monotonic) -> None:
        self.store = store
        self._now = now
        self.clock = clock

    def now(self) -> datetime:
        value = self._now()
        if value.utcoffset() is None:
            raise ValueError("Schedule time must include a timezone")
        return value.astimezone(timezone.utc)

    def status(self) -> ScheduleState:
        state = self.store.schedule()
        if state is None:
            raise ValueError("No schedule exists")
        return state

    def start(self, config: Config, *, interval_seconds: float, max_runs: Optional[int] = None,
              until: Optional[datetime] = None) -> ScheduleState:
        current = self.now()
        try:
            valid_interval = type(interval_seconds) in (int, float) and isfinite(interval_seconds) and interval_seconds >= 1
            current + timedelta(seconds=interval_seconds)
        except (OverflowError, TypeError, ValueError):
            valid_interval = False
        if not valid_interval:
            raise ValueError("interval_seconds must be finite and at least one second within the datetime range")
        if max_runs is None and until is None:
            raise ValueError("Provide max_runs or an observation end time")
        if max_runs is not None and (type(max_runs) is not int or max_runs <= 0):
            raise ValueError("max_runs must be a positive integer")
        if until is not None and (until.utcoffset() is None or until <= current):
            raise ValueError("Observation end must be a future timezone-aware datetime")
        started = current.isoformat()
        state = ScheduleState(str(uuid4()), config, interval_seconds, started, started, max_runs,
                              until.astimezone(timezone.utc).isoformat() if until is not None else None)

        def create(previous: Optional[ScheduleState]) -> ScheduleState:
            if previous is not None and (previous.status in ("active", "paused") or previous.inflight_run_id is not None):
                raise ValueError("Finish or stop the existing schedule before starting another")
            return state
        return self.store.update_schedule(create)

    def control(self, action: str) -> ScheduleState:
        if action not in ("pause", "resume", "stop"):
            raise ValueError("Unknown schedule control")

        def change(state: Optional[ScheduleState]) -> ScheduleState:
            if state is None:
                raise ValueError("No schedule exists")
            if action == "stop":
                if state.status not in ("completed", "stopped"):
                    state.status = "stopped"
            elif state.status in ("completed", "stopped"):
                raise ValueError("A finished schedule cannot be paused or resumed")
            else:
                state.status = "paused" if action == "pause" else "active"
            self._complete_if_limit(state)
            state.events.append({"kind": action, "at": self.now().isoformat()})
            return state
        return self.store.update_schedule(change)

    def _limit_reached(self, state: ScheduleState) -> bool:
        return ((state.max_runs is not None and state.runs_started >= state.max_runs)
                or (state.until is not None and self.now() >= datetime.fromisoformat(state.until)))

    def _complete_if_limit(self, state: ScheduleState) -> None:
        if state.status != "active" or not self._limit_reached(state):
            return
        exhausted = state.max_runs is not None and state.runs_started >= state.max_runs
        if not exhausted and state.until is not None:
            end = datetime.fromisoformat(state.until)
            due = datetime.fromisoformat(state.next_run_at)
            if self.now() >= end and due < end:
                state.events.append({"kind": "observation_gap", "from": due.isoformat(), "to": end.isoformat(),
                                     "overdue_intervals": int((end - due).total_seconds() // state.interval_seconds)})
        state.status = "completed"

    def _change(self, change: Callable[[ScheduleState], None]) -> ScheduleState:
        def update(state: Optional[ScheduleState]) -> ScheduleState:
            if state is None:
                raise ValueError("No schedule exists")
            change(state)
            return state
        return self.store.update_schedule(update)

    def tick(self, source: ProjectSource, *, expected_schedule_id: Optional[str] = None) -> TickResult:
        with self.store.operation_lock("schedule") as acquired:
            if not acquired:
                state = self._change(lambda current: current.events.append({"kind": "overlap", "at": self.now().isoformat()}))
                return TickResult("overlap", state)
            state = self.status()
            if expected_schedule_id is not None and state.id != expected_schedule_id:
                return TickResult("schedule_changed", state)
            return self._tick(source, expected_schedule_id)

    def work(self, source: ProjectSource, *, wait: Callable[[float], None] = sleep) -> TickResult:
        schedule_id = self.status().id
        while True:
            result = self.tick(source, expected_schedule_id=schedule_id)
            state = result.schedule
            if state.status != "active":
                return TickResult(state.status, state)
            if result.status in ("overlap", "schedule_changed"):
                return result
            next_check = datetime.fromisoformat(state.next_run_at)
            if state.until is not None:
                next_check = min(next_check, datetime.fromisoformat(state.until))
            wait(max(0.001, min(1.0, (next_check - self.now()).total_seconds())))

    def _finish(self, state: ScheduleState, report: dict[str, Any]) -> None:
        state.inflight_run_id = None
        if report.get("skip_reason") in ("state_busy", "source_cooldown"):
            state.runs_started -= 1
            kind = "overlap" if report["skip_reason"] == "state_busy" else "source_cooldown"
            state.events.append({"kind": kind, "at": self.now().isoformat()})
            if kind == "overlap":
                return
        else:
            state.completed_runs += 1
        state.last_run_id, state.last_result = report["id"], report["status"]
        finished = datetime.fromisoformat(report["finished_at"])
        state.next_run_at = (finished + timedelta(seconds=state.interval_seconds)).isoformat()
        not_before = report.get("next_allowed_at")
        if not_before is not None and datetime.fromisoformat(not_before) > datetime.fromisoformat(state.next_run_at):
            state.next_run_at = not_before
            state.events.append({"kind": "source_cooldown", "at": self.now().isoformat(), "until": not_before})
        self._complete_if_limit(state)

    def _recover(self) -> None:
        state = self.status()
        if state.inflight_run_id is None:
            return
        report = next((run for run in self.store.runs() if run["id"] == state.inflight_run_id), None)

        def recover(current: ScheduleState) -> None:
            if report is not None and report.get("finished_at") is not None:
                self._finish(current, report)
                current.events.append({"kind": "recovered_completion", "at": self.now().isoformat(), "run_id": report["id"]})
            else:
                current.events.append({"kind": "interrupted_run", "at": self.now().isoformat(), "run_id": current.inflight_run_id})
                current.last_run_id, current.last_result = current.inflight_run_id, "interrupted"
                current.inflight_run_id = None
        self._change(recover)

    def _tick(self, source: ProjectSource, expected_schedule_id: Optional[str]) -> TickResult:
        self._recover()
        outcome = "not_due"

        def prepare(state: ScheduleState) -> None:
            nonlocal outcome
            if expected_schedule_id is not None and state.id != expected_schedule_id:
                outcome = "schedule_changed"
                return
            self._complete_if_limit(state)
            if state.status != "active":
                outcome = state.status
                return
            current = self.now()
            due = datetime.fromisoformat(state.next_run_at)
            if current < due:
                return
            late = (current - due).total_seconds()
            if late >= state.interval_seconds:
                state.events.append({"kind": "observation_gap", "from": due.isoformat(), "to": current.isoformat(),
                                     "overdue_intervals": int(late // state.interval_seconds)})
            not_before = self.store.source_limit().next_allowed_at
            if not_before is not None and datetime.fromisoformat(not_before) > current:
                state.next_run_at = not_before
                state.events.append({"kind": "source_cooldown", "at": current.isoformat(), "until": not_before})
                outcome = "deferred"
                return
            state.runs_started += 1
            state.inflight_run_id = str(uuid4())
            state.events.append({"kind": "dispatch", "at": current.isoformat(), "run_id": state.inflight_run_id})
            outcome = "dispatch"

        state = self._change(prepare)
        if outcome != "dispatch":
            return TickResult(outcome, state)
        config = state.config
        if state.until is not None:
            remaining = (datetime.fromisoformat(state.until) - self.now()).total_seconds()
            if remaining <= 0:
                def expire(current: ScheduleState) -> None:
                    current.inflight_run_id = None
                    current.runs_started -= 1
                    current.status = "completed"
                    current.events.append({"kind": "window_closed_before_read", "at": self.now().isoformat()})
                return TickResult("completed", self._change(expire))
            config = replace(config, max_seconds=min(config.max_seconds, remaining))
        report = collect(config, self.store, source, now=self.now, clock=self.clock, run_id=state.inflight_run_id)
        state = self._change(lambda current: self._finish(current, asdict(report)))
        return TickResult("overlap" if report.skip_reason == "state_busy" else "ran", state)
