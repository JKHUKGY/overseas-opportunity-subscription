"""One complete manual run: search, normalize, persist, report."""

from dataclasses import asdict
from datetime import datetime, timezone
from math import isfinite
from time import monotonic
from typing import Any, Callable, Optional, Protocol, Union
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from .models import Config, RunReport
from .storage import SQLiteStore
from .source import SourceError


class ProjectSource(Protocol):
    def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> Optional[Union[int, float]]:
    if type(value) in (int, float):
        try:
            if isfinite(value):
                return value  # type: ignore[no-any-return]
        except OverflowError:
            pass
    return None


def _candidate(project: dict[str, Any], checked_at: str) -> dict[str, Any]:
    project_id = project.get("id")
    if type(project_id) is not int or project_id <= 0:
        raise ValueError("Missing or invalid source project ID")
    timestamp = _number(project.get("time_submitted") if project.get("time_submitted") is not None else project.get("submitdate"))
    published = None
    if timestamp is not None:
        try:
            published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        except (OverflowError, ValueError, OSError):
            pass
    slug = _text(project.get("seo_url"))
    url = "https://www.freelancer.com/projects/" + slug.lstrip("/") if slug else None
    canonical = url
    if url:
        parts = urlsplit(url)
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")])
        canonical = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    budget = project.get("budget")
    budget = budget if isinstance(budget, dict) else {}
    currency = project.get("currency")
    currency = currency if isinstance(currency, dict) else {}
    return {
        "source": "Freelancer", "id": str(project["id"]),
        "url": url, "canonical_url": canonical, "title": _text(project.get("title")),
        "description": _text(project.get("description")) or _text(project.get("preview_description")),
        "published_at": published, "first_seen_at": checked_at,
        "last_read_at": checked_at, "last_status_verified_at": None,
        "budget_min": _number(budget.get("minimum")), "budget_max": _number(budget.get("maximum")),
        "currency": _text(currency.get("code")), "pricing": _text(project.get("type")),
        "source_status": _text(project.get("status")),
        "frontend_status": _text(project.get("frontend_project_status")),
        "status": "未核实", "region": "地域未说明", "processing_status": "pending",
    }


def collect(config: Config, store: SQLiteStore, source: ProjectSource,
            *, now: Callable[[], datetime] = utc_now,
            clock: Callable[[], float] = monotonic) -> RunReport:
    started = now().isoformat()
    report = RunReport(str(uuid4()), started, started, asdict(config))
    deadline = clock() + config.max_seconds
    candidates = []
    stop = False
    for query in config.queries:
        if stop:
            break
        for page in range(config.pages):
            remaining = deadline - clock()
            if report.requests_attempted >= config.max_requests or remaining <= 0:
                report.truncated = True
                stop = True
                break
            report.requests_attempted += 1
            try:
                projects = source.search(query, config.limit, page * config.limit, min(config.request_timeout, remaining))
            except SourceError as error:
                report.requests_failed += 1
                report.errors.append({"kind": error.kind, "http_status": error.http_status})
                stop = True
                break
            report.requests_succeeded += 1
            report.received_count += len(projects)
            for project in projects[:config.limit]:
                try:
                    if not isinstance(project, dict):
                        raise ValueError("Invalid project record")
                    candidates.append(_candidate(project, now().isoformat()))
                except ValueError:
                    report.invalid_count += 1
            if len(projects) < config.limit:
                break
            if page == config.pages - 1 or len(projects) > config.limit:
                report.truncated = True
    report.unique_count = len({(p["source"], p["id"]) for p in candidates})
    report.finished_at = now().isoformat()
    if report.requests_failed:
        report.status = "partial" if report.requests_succeeded else "failed"
    elif report.truncated or report.invalid_count:
        report.status = "partial"
    return store.commit_run(candidates, report)
