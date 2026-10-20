from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Optional


@dataclass(frozen=True)
class Config:
    queries: tuple[str, ...] = ("illustration", "portrait")
    limit: int = 5
    pages: int = 1
    max_requests: int = 2
    request_timeout: float = 20.0
    max_seconds: float = 40.0

    def __post_init__(self) -> None:
        if not isinstance(self.queries, tuple) or not self.queries or any(
            not isinstance(query, str) or not query.strip() for query in self.queries
        ):
            raise ValueError("queries must be a nonempty tuple of nonempty strings")
        for name in ("limit", "pages", "max_requests"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name + " must be a positive integer")
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
