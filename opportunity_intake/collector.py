"""One complete manual run: recheck, search, normalize, persist, report."""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from time import monotonic
from typing import Any, Callable, Optional, Protocol, TypeVar, Union
from uuid import uuid4

from .identity import canonical_url, project_url
from .models import Config, RunReport, SourceLimit
from .storage import SQLiteStore
from .source import SourceError


T = TypeVar("T")


class ProjectSource(Protocol):
    def detail(self, project_id: str, timeout: float) -> dict[str, Any]: ...

    def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_time(value: Optional[str], failed_at: datetime, streak: int) -> str:
    if value is not None:
        value = value.strip()
        try:
            if value.isascii() and value.isdigit():
                return (failed_at + timedelta(seconds=int(value))).isoformat()
            date = parsedate_to_datetime(value)
            if date.tzinfo is not None:
                return max(failed_at, date.astimezone(timezone.utc)).isoformat()
        except (ValueError, TypeError, OverflowError):
            pass
    return (failed_at + timedelta(seconds=min(60 * 2 ** (streak - 1), 3600))).isoformat()


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


def _candidate(project: dict[str, Any], checked_at: str, run_started: datetime) -> dict[str, Any]:
    project_id = project.get("id")
    if type(project_id) is not int or project_id <= 0:
        raise ValueError("Missing or invalid source project ID")
    source_time = project.get("time_submitted") if project.get("time_submitted") is not None else project.get("submitdate")
    timestamp = _number(source_time)
    published = None
    publication_status = "unknown" if source_time is None else "invalid"
    recency = "unknown"
    if timestamp is not None:
        try:
            published_time = datetime.fromtimestamp(timestamp, timezone.utc)
            published = published_time.isoformat()
            publication_status = "known"
            recency = "recent" if run_started - timedelta(days=3) <= published_time <= run_started else (
                "future" if published_time > run_started else "older")
        except (OverflowError, ValueError, OSError):
            pass
    url = project_url(project)
    canonical = canonical_url(url)
    budget = project.get("budget")
    budget = budget if isinstance(budget, dict) else {}
    budget_min, budget_max = _number(budget.get("minimum")), _number(budget.get("maximum"))
    invalid_budget = any(budget.get(name) is not None and _number(budget[name]) is None
                         for name in ("minimum", "maximum"))
    if budget_min is not None and budget_min < 0:
        budget_min, invalid_budget = None, True
    if budget_max is not None and budget_max < 0:
        budget_max, invalid_budget = None, True
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        budget_min, budget_max, invalid_budget = None, None, True
    budget_status = "invalid" if invalid_budget else (
        "known" if budget_min is not None and budget_max is not None else
        "unknown" if budget_min is None and budget_max is None else "partial")
    currency = project.get("currency")
    currency = currency if isinstance(currency, dict) else {}
    pricing = project.get("type")
    pricing_status = "known" if pricing in ("fixed", "hourly") else "unknown" if pricing is None else "invalid"
    candidate: dict[str, Any] = {
        "source": "Freelancer", "id": str(project["id"]),
        "url": url, "canonical_url": canonical, "title": _text(project.get("title")),
        "description": _text(project.get("description")) or _text(project.get("preview_description")),
        "published_at": published, "published_at_read_at": checked_at if published is not None else None,
        "first_seen_at": checked_at,
        "last_read_at": checked_at, "last_status_verified_at": None,
        "budget_min": budget_min, "budget_max": budget_max,
        "currency": _text(currency.get("code")), "pricing": pricing if pricing_status == "known" else None,
        "source_status": _text(project.get("status")),
        "frontend_status": _text(project.get("frontend_project_status")),
        "status": "未核实", "region": "地域未说明", "processing_status": "pending",
        "recency": recency, "recency_as_of": run_started.isoformat(),
        "field_status": {"published_at": publication_status, "budget": budget_status,
                         "pricing": pricing_status, "region": "unknown"},
    }
    for name in ("title", "description", "currency"):
        candidate["field_status"][name] = "known" if candidate[name] is not None else "unknown"
    for value in candidate.values():
        if isinstance(value, str):
            value.encode("utf-8")
    return candidate


def collect(config: Config, store: SQLiteStore, source: ProjectSource,
            *, now: Callable[[], datetime] = utc_now,
            clock: Callable[[], float] = monotonic) -> RunReport:
    run_started = now()
    if run_started.utcoffset() is None:
        raise ValueError("Run time must include a timezone")
    run_started = run_started.astimezone(timezone.utc)
    started = run_started.isoformat()
    report = RunReport(str(uuid4()), started, None, asdict(config), status="running")
    report.recent_window_start = (run_started - timedelta(days=3)).isoformat()
    report.recent_window_end = started
    report.unfinished_run_ids = [run["id"] for run in store.runs() if run.get("status") == "running"]
    deadline = clock() + config.max_seconds
    report.recovered_deletions = store.cleanup_ended()
    report.pending_recheck_count = len(store.candidates())
    source_limit = store.source_limit()
    not_before = source_limit.next_allowed_at
    if not_before is not None and datetime.fromisoformat(not_before) > now():
        report.finished_at = now().isoformat()
        report.status = "skipped"
        report.skip_reason = "source_cooldown"
        report.next_allowed_at = not_before
        return store.commit_run([], report)
    store.commit_run([], report)
    seen: set[tuple[str, str]] = set()
    stop = False
    attempted_ids: set[str] = set()

    def read(kind: str, metadata: dict[str, Any], fetch: Callable[[float], T]) -> Optional[T]:
        nonlocal stop, source_limit
        remaining = deadline - clock()
        if stop or report.requests_attempted >= config.max_requests or remaining <= 0:
            report.truncated = True
            stop = True
            return None
        request = dict(metadata, kind=kind, status="running", received_count=0)
        report.requests.append(request)
        report.requests_attempted += 1
        if kind == "detail":
            report.rechecks_attempted += 1
        store.commit_run([], report)
        remaining = deadline - clock()
        if remaining <= 0:
            report.requests_attempted -= 1
            if kind == "detail":
                report.rechecks_attempted -= 1
            report.requests.pop()
            report.truncated = True
            stop = True
            return None
        try:
            result = fetch(min(config.request_timeout, remaining))
        except SourceError as error:
            report.requests_failed += 1
            if kind == "detail":
                report.rechecks_failed += 1
            report.errors.append({"kind": error.kind, "http_status": error.http_status})
            request.update(status="failed", error_kind=error.kind, http_status=error.http_status)
            if error.http_status == 429:
                streak = min(source_limit.rate_limit_streak + 1, 7)
                report.next_allowed_at = _retry_time(error.retry_after, now(), streak)
                source_limit = SourceLimit(report.next_allowed_at, streak)
            stop = True
            return None
        count = len(result) if isinstance(result, list) else 1
        report.requests_succeeded += 1
        report.received_count += count
        if kind == "detail":
            report.rechecks_succeeded += 1
        request.update(status="success", received_count=count)
        return result

    for saved in store.recheck_candidates(config.recheck_limit):
        if store.is_ended(saved["source"], saved["id"], saved["url"]):
            report.ended_record_hits += 1
            continue
        def fetch_detail(timeout: float) -> dict[str, Any]:
            raw = source.detail(saved["id"], timeout)
            if not isinstance(raw, dict) or type(raw.get("id")) is not int or str(raw["id"]) != saved["id"]:
                raise SourceError("invalid_response")
            try:
                return _candidate(raw, now().astimezone(timezone.utc).isoformat(), run_started)
            except ValueError:
                raise SourceError("invalid_record") from None

        before = report.rechecks_attempted
        candidate = read("detail", {"source": saved["source"], "id": saved["id"]}, fetch_detail)
        if candidate is None:
            if report.rechecks_attempted > before:
                attempted_ids.add(saved["id"])
                report.rechecks_unresolved += 1
                store.commit_run([], report, source_limit, recheck_cursor=saved["id"], failed_recheck_at=now().isoformat())
            break
        attempted_ids.add(saved["id"])
        candidate["last_status_attempt_at"] = candidate["last_read_at"]
        reason = {"closed": "source_closed", "complete": "source_complete"}.get(candidate["frontend_status"])
        if reason is not None:
            ending = dict(saved, url=saved["url"] or candidate["url"])
            store.record_ended(ending, candidate["last_read_at"], reason, report)
            store.cleanup_ended()
            continue
        if candidate["frontend_status"] == "open":
            candidate["status"] = "来源显示开放，未确认可承接"
            candidate["last_status_verified_at"] = candidate["last_read_at"]
        else:
            candidate["status"] = "无法核实"
            report.rechecks_unresolved += 1
        seen.add((candidate["source"], candidate["id"]))
        report.unique_count = len(seen)
        store.commit_run([candidate], report, status_checked=True, recheck_cursor=saved["id"])

    for query in config.queries:
        if stop:
            break
        for page in range(config.pages):
            projects = read("search", {"query": query, "offset": page * config.limit, "limit": config.limit},
                            lambda timeout: source.search(query, config.limit, page * config.limit, timeout))
            if projects is None:
                break
            candidates = []
            for project in projects[:config.limit]:
                try:
                    if not isinstance(project, dict):
                        raise ValueError("Invalid project record")
                    if type(project.get("id")) is int and store.is_ended("Freelancer", str(project["id"]), project_url(project)):
                        report.ended_record_hits += 1
                        continue
                    candidates.append(_candidate(project, now().astimezone(timezone.utc).isoformat(), run_started))
                except ValueError:
                    report.invalid_count += 1
            seen.update((p["source"], p["id"]) for p in candidates)
            report.unique_count = len(seen)
            store.commit_run(candidates, report)
            if len(projects) < config.limit:
                break
            if page == config.pages - 1 or len(projects) > config.limit:
                report.truncated = True
    report.pending_recheck_count = sum(row["id"] not in attempted_ids for row in store.candidates())
    if config.recheck_limit and report.pending_recheck_count:
        report.truncated = True
    if clock() >= deadline:
        report.truncated = True
    report.finished_at = now().isoformat()
    report.status = "success"
    if report.requests_failed:
        report.status = "partial" if report.requests_succeeded else "failed"
    elif report.truncated or report.invalid_count or report.rechecks_unresolved:
        report.status = "partial"
    if report.requests_succeeded and not report.requests_failed:
        source_limit = SourceLimit()
    return store.commit_run([], report, source_limit)
