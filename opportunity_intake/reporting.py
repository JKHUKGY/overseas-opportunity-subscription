"""Read-only daily and period evidence, without historical opportunity details."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .collector import utc_now
from .storage import SQLiteStore


FIELDS = ("published_at", "budget", "pricing", "region", "title", "description", "currency")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Report times must include a timezone")
    return parsed.astimezone(timezone.utc)


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in FIELDS:
        counts = dict.fromkeys(("known", "partial", "unknown", "invalid"), 0)
        for row in rows:
            status = row.get("field_status", {}).get(name, "unknown")
            counts[status if status in counts else "unknown"] += 1
        result[name] = dict(counts, denominator=len(rows),
                            known_fraction=counts["known"] / len(rows) if rows else None)
    return result


def _summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    new: set[tuple[str, str]] = set()
    for run in runs:
        for row in run.get("candidate_results", []):
            key = (row["source"], row["id"])
            latest[key] = row
            if row["change"] == "new":
                new.add(key)
    statuses = dict.fromkeys(("success", "partial", "failed", "skipped", "running"), 0)
    for run in runs:
        status = run["status"]
        statuses[status] = statuses.get(status, 0) + 1
    redacted = sum(run.get("redacted_candidate_results", 0) for run in runs)
    # Older runs may predate candidate-level evidence; never fill in fake identities.
    unavailable = redacted + sum(max(0, max(run.get("unique_count", 0),
                                      run.get("new_count", 0) + run.get("changed_count", 0)
                                      + run.get("unchanged_count", 0)) - len(run.get("candidate_results", []))
                                      - run.get("redacted_candidate_results", 0)) for run in runs)
    errors = Counter((error["kind"], error.get("http_status")) for run in runs for error in run.get("errors", []))
    return {
        "runs": len(runs), "statuses": statuses,
        "unique_new_candidates": len(new) if not unavailable else None,
        "identifiable_unique_new_candidates": len(new),
        "new_observations": sum(run.get("new_count", 0) for run in runs),
        "redacted_candidate_observations": redacted,
        "unavailable_candidate_observations": unavailable,
        "unique_counts_complete": not unavailable,
        "unique_observed_candidates": len(latest),
        "candidate_observations": sum(len(run.get("candidate_results", [])) for run in runs) + unavailable,
        "requests": {key: sum(run.get("requests_" + key, 0) for run in runs)
                     for key in ("attempted", "succeeded", "failed")},
        "requests_without_saved_outcome": sum(max(0, run.get("requests_attempted", 0)
                                                 - run.get("requests_succeeded", 0)
                                                 - run.get("requests_failed", 0)) for run in runs),
        "request_errors": [dict(kind=key[0], http_status=key[1], count=value) for key, value in errors.items()],
        "truncated_runs": sum(bool(run.get("truncated")) for run in runs),
        "rechecks": {key: sum(run.get("rechecks_" + key, 0) for run in runs)
                     for key in ("attempted", "succeeded", "failed", "unresolved")},
        "confirmed_ended": sum(run.get("confirmed_ended_count", 0) for run in runs),
        "ended_record_hits": sum(run.get("ended_record_hits", 0) for run in runs),
        "invalid_records": sum(run.get("invalid_count", 0) for run in runs),
        "changed_observations": sum(run.get("changed_count", 0) for run in runs),
        "recent_candidates": sum(row["recency"] == "recent" for row in latest.values()),
        "recency": dict(Counter(row["recency"] for row in latest.values())),
        "field_coverage": _coverage(list(latest.values())),
    }


def _diagnostic(run: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "started_at", "finished_at", "status", "config", "truncated", "errors",
            "skip_reason", "next_allowed_at", "pending_recheck_count", "redacted_detail_requests")
    result = {key: run.get(key) for key in keys}
    result["search_requests"] = [row for row in run.get("requests", []) if row.get("kind") == "search"]
    result["requests"] = {key: run.get("requests_" + key, 0) for key in ("attempted", "succeeded", "failed")}
    return result


def _current_recency(row: dict[str, Any], current: datetime) -> str:
    if row.get("field_status", {}).get("published_at") != "known" or row.get("published_at") is None:
        return "unknown"
    published = _time(row["published_at"])
    if published > current:
        return "future"
    return "recent" if published >= current - timedelta(days=3) else "older"


def _period(runs: list[dict[str, Any]], schedules: list[dict[str, Any]],
            start: datetime, end: datetime) -> dict[str, Any]:
    selected = [run for run in runs if start <= _time(run["started_at"]) < end]
    result = _summary(selected)
    interrupted = {event["run_id"] for plan in schedules for event in plan["events"]
                   if event["kind"] == "interrupted_run"}
    result["known_interrupted_runs"] = sum(run["id"] in interrupted for run in selected)
    gaps = []
    events: Counter[str] = Counter()
    for plan in schedules:
        for event in plan["events"]:
            if event["kind"] == "observation_gap":
                left, right = max(start, _time(event["from"])), min(end, _time(event["to"]))
                if left < right:
                    gaps.append((left, right))
            elif "at" in event and start <= _time(event["at"]) < end:
                events[event["kind"]] += 1
    merged: list[tuple[datetime, datetime]] = []
    for left, right in sorted(gaps):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    result.update(observation_gaps=[{"from": left.isoformat(), "to": right.isoformat()} for left, right in merged],
                  observation_gap_seconds=sum((right - left).total_seconds() for left, right in merged),
                  schedule_events=dict(events))
    return result


def observation_report(store: SQLiteStore, *, start: datetime, end: datetime,
                       now: Callable[[], datetime] = utc_now) -> dict[str, Any]:
    """Select runs by start in [start, end); daily buckets and timestamps are UTC."""
    start, end, generated = _time(start.isoformat()), _time(end.isoformat()), _time(now().isoformat())
    if end <= start:
        raise ValueError("Observation end must be after start")
    snapshot = store.observation_snapshot()
    runs = sorted((run for run in snapshot["runs"] if start <= _time(run["started_at"]) < end),
                  key=lambda run: _time(run["started_at"]))
    schedules = snapshot["schedules"]
    daily = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        following = day + timedelta(days=1)
        daily.append(dict(_period(runs, schedules, max(day, start), min(following, end)),
                          date=day.date().isoformat(), start=max(day, start).isoformat(),
                          end=min(following, end).isoformat()))
        day = following
    candidates = snapshot["candidates"]
    return {
        "generated_at": generated.isoformat(),
        "scope": {"start": start.isoformat(), "end": end.isoformat(), "timezone": "UTC",
                  "requested_end_in_future": end > generated,
                  "queries": sorted({query for run in runs for query in run["config"]["queries"]})},
        "total": _period(runs, schedules, start, end), "daily": daily,
        "run_diagnostics": [_diagnostic(run) for run in runs],
        "schedules": [plan for plan in schedules if _time(plan["started_at"]) < end],
        "methodology": {
            "run_selection": "Run started_at in [start, end); running means no saved finish, not proof of a live process.",
            "deduplication": "source + id across runs/queries; daily unique counts need not sum to period unique counts.",
            "new": "new observations are insertion events; unique_new_candidates is null when identity evidence is missing after deletion or legacy runs.",
            "coverage": "Latest retained observation per source + id within each bucket. Fractions use that bucket's unique_observed_candidates denominator; redacted observations excluded.",
            "recency": "Latest observation per identity: source publication in the inclusive three days ending at that run's start. Not recency at export time.",
            "current_candidates": "Current retained database state at export; not a historical snapshot or restricted to observation dates. Use list for live details.",
            "gaps": "Recorded scheduler gaps clipped to range, union seconds; no inferred missed projects. Zero recorded gaps is not evidence of continuous operation.",
            "skips": "Persisted skipped runs only; scheduling overlap/defer events reported separately. Unpersisted manual lock conflicts cannot be reconstructed.",
            "meaning": "Unreviewed collection candidates, not verified drawing commissions or platform totals. Manual relevance assessment is separate and not measured here.",
        },
        "current_candidates": {"count": len(candidates), "as_of": generated.isoformat(),
                               "recency": dict(Counter(_current_recency(row, generated) for row in candidates)),
                               "field_coverage": _coverage(candidates),
                               "status_counts": dict(Counter(row.get("status", "未核实") for row in candidates)),
                               "ever_verified": sum(row.get("last_status_verified_at") is not None for row in candidates),
                               "pending_processing": sum(row.get("processing_status") == "pending" for row in candidates)},
    }
