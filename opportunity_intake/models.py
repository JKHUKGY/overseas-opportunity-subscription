from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal, Optional, TypedDict


ChangeKind = Literal["new", "changed", "unchanged"]
Recency = Literal["recent", "older", "future", "unknown"]
FieldStatus = Literal["known", "partial", "unknown", "invalid"]


class CandidateResult(TypedDict):
    source: str
    id: str
    change: ChangeKind
    recency: Recency
    field_status: dict[str, FieldStatus]


@dataclass(frozen=True)
class Config:
    queries: tuple[str, ...] = ("illustration", "portrait")
    limit: int = 5
    pages: int = 1
    max_requests: int = 2
    request_timeout: float = 20.0
    max_seconds: float = 40.0
    recheck_limit: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.queries, tuple) or not self.queries or any(
            not isinstance(query, str) or not query.strip() for query in self.queries
        ):
            raise ValueError("queries must be a nonempty tuple of nonempty strings")
        for name in ("limit", "pages", "max_requests"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name + " must be a positive integer")
        if type(self.recheck_limit) is not int or self.recheck_limit < 0:
            raise ValueError("recheck_limit must be a nonnegative integer")
        for name in ("request_timeout", "max_seconds"):
            value = getattr(self, name)
            try:
                valid = type(value) in (int, float) and isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(name + " must be finite and positive")


@dataclass
class SourceLimit:
    next_allowed_at: Optional[str] = None
    rate_limit_streak: int = 0


@dataclass(frozen=True)
class SourceDeletionResult:
    candidates_deleted: int
    ended_records_deleted: int = 0
    history_entries_redacted: int = 0
    recheck_cursors_deleted: int = 0
    status: Literal["complete"] = "complete"


@dataclass
class RunReport:
    id: str
    started_at: str
    finished_at: Optional[str]
    config: dict[str, Any]
    status: str = "success"
    requests_attempted: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    received_count: int = 0
    unique_count: int = 0
    new_count: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    truncated: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    next_allowed_at: Optional[str] = None
    skip_reason: Optional[str] = None
    unfinished_run_ids: list[str] = field(default_factory=list)
    unchanged_count: int = 0
    changed_count: int = 0
    candidate_results: list[CandidateResult] = field(default_factory=list)
    recent_count: int = 0
    recent_window_start: Optional[str] = None
    recent_window_end: Optional[str] = None
    statistics_timezone: str = "UTC"
    field_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    rechecks_attempted: int = 0
    rechecks_succeeded: int = 0
    rechecks_failed: int = 0
    rechecks_unresolved: int = 0
    pending_recheck_count: int = 0
    confirmed_ended_count: int = 0
    ended_record_hits: int = 0
    recovered_deletions: int = 0


@dataclass
class ScheduleState:
    id: str
    config: Config
    interval_seconds: float
    started_at: str
    next_run_at: str
    max_runs: Optional[int] = None
    until: Optional[str] = None
    status: Literal["active", "paused", "stopped", "completed"] = "active"
    runs_started: int = 0
    completed_runs: int = 0
    inflight_run_id: Optional[str] = None
    last_run_id: Optional[str] = None
    last_result: Optional[str] = None
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TickResult:
    status: str
    schedule: ScheduleState
