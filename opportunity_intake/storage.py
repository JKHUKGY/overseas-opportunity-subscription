"""Atomic candidate and run persistence, with public readback operations."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from .identity import canonical_url
from .models import ChangeKind, RunReport, SourceDeletionResult, SourceLimit


class StorageError(Exception):
    """State could not be read or committed; existing data was not reset."""


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existed = path.exists()
        self._db: Optional[sqlite3.Connection] = None
        try:
            db = sqlite3.connect(str(path), timeout=5)
            self._db = db
            db.execute("PRAGMA secure_delete = ON")
            if not existed:
                path.chmod(0o600)
                with db:
                    db.execute("CREATE TABLE candidates (source TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY (source, id))")
                    db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                    db.execute("PRAGMA user_version = 1")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise StorageError("State integrity check failed")
            version = db.execute("PRAGMA user_version").fetchone()
            if version not in ((1,), (2,), (3,)):
                raise StorageError("Unrecognized state schema; refusing to reset it")
            db.execute("SELECT source, id, payload FROM candidates LIMIT 0")
            db.execute("SELECT id, payload FROM runs LIMIT 0")
            if version == (1,):
                db.execute("BEGIN IMMEDIATE")
                with db:
                    db.execute("CREATE TABLE source_limits (source TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                    db.execute("PRAGMA user_version = 2")
            if version in ((1,), (2,)):
                with db:
                    db.execute("CREATE TABLE IF NOT EXISTS recheck_state (source TEXT PRIMARY KEY, cursor TEXT NOT NULL)")
                    db.execute("CREATE TABLE IF NOT EXISTS ended_records (source TEXT, id TEXT, canonical_url TEXT, payload TEXT NOT NULL, PRIMARY KEY(source, id))")
                    db.execute("CREATE INDEX IF NOT EXISTS ended_by_url ON ended_records(source, canonical_url)")
                    db.execute("PRAGMA user_version = 3")
            db.execute("SELECT source, payload FROM source_limits LIMIT 0")
            db.execute("SELECT source, cursor FROM recheck_state LIMIT 0")
            db.execute("SELECT source, id, canonical_url, payload FROM ended_records LIMIT 0")
        except (sqlite3.Error, OSError):
            self.close()
            raise StorageError("Unable to open collection state; existing data was not reset") from None
        except StorageError:
            self.close()
            raise

    def _connection(self) -> sqlite3.Connection:
        if self._db is None:
            raise StorageError("Collection state is closed")
        return self._db

    def source_limit(self) -> SourceLimit:
        rows = self._read("SELECT payload FROM source_limits WHERE source = 'Freelancer'")
        return SourceLimit(**rows[0]) if rows else SourceLimit()

    def recheck_candidates(self, limit: int) -> list[dict[str, Any]]:
        rows = self.candidates()
        try:
            saved = self._connection().execute("SELECT cursor FROM recheck_state WHERE source='Freelancer'").fetchone()
        except sqlite3.Error:
            raise StorageError("Unable to read recheck progress") from None
        cursor = saved[0] if saved else ""
        return ([row for row in rows if row["id"] > cursor] + [row for row in rows if row["id"] <= cursor])[:limit]

    def commit_run(self, candidates: list[dict[str, Any]], report: RunReport,
                   source_limit: Optional[SourceLimit] = None, *, status_checked: bool = False,
                   recheck_cursor: Optional[str] = None, failed_recheck_at: Optional[str] = None) -> RunReport:
        db = self._connection()
        checkpoint = asdict(report)
        results = {(row["source"], row["id"]): row for row in report.candidate_results}
        try:
            with db:
                if recheck_cursor is not None:
                    db.execute("INSERT INTO recheck_state VALUES ('Freelancer', ?) ON CONFLICT(source) DO UPDATE SET cursor=excluded.cursor", (recheck_cursor,))
                    if failed_recheck_at is not None:
                        previous = db.execute("SELECT payload FROM candidates WHERE source='Freelancer' AND id=?", (recheck_cursor,)).fetchone()
                        if previous:
                            failed = json.loads(previous[0])
                            failed.update(status="无法核实", last_status_attempt_at=failed_recheck_at)
                            db.execute("UPDATE candidates SET payload=? WHERE source='Freelancer' AND id=?", (json.dumps(failed, ensure_ascii=False), recheck_cursor))
                for candidate in candidates:
                    previous = db.execute(
                        "SELECT payload FROM candidates WHERE source = ? AND id = ?",
                        (candidate["source"], candidate["id"]),
                    ).fetchone()
                    change: ChangeKind = "new"
                    if previous:
                        saved = json.loads(previous[0])
                        for field in ("first_seen_at", "processing_status"):
                            candidate[field] = saved[field]
                        if not status_checked:
                            candidate["status"] = saved["status"]
                            candidate["last_status_attempt_at"] = saved.get("last_status_attempt_at")
                        if candidate["last_status_verified_at"] is None:
                            candidate["last_status_verified_at"] = saved["last_status_verified_at"]
                        if candidate["published_at"] is None:
                            candidate["published_at"] = saved.get("published_at")
                            candidate["published_at_read_at"] = saved.get("published_at_read_at")
                        if candidate["url"] is None:
                            candidate["url"] = saved.get("url")
                            candidate["canonical_url"] = canonical_url(candidate["url"])
                        candidate["content_version"] = saved.get("content_version", 1)
                        for field in ("classification", "summary"):
                            candidate[field] = saved.get(field)
                        change = "unchanged"
                        if any(candidate[field] != saved.get(field) for field in
                               ("title", "description", "budget_min", "budget_max", "currency", "pricing", "region")):
                            candidate["content_version"] += 1
                            candidate.update(processing_status="pending", classification=None, summary=None)
                            change = "changed"
                        report.duplicate_count += 1
                    else:
                        candidate.update(content_version=1, classification=None, summary=None)
                        change = "new"
                    key = (candidate["source"], candidate["id"])
                    if key in results and results[key]["change"] in ("new", "changed"):
                        change = results[key]["change"]
                    candidate["last_change"] = change
                    results[key] = {"source": candidate["source"], "id": candidate["id"], "change": change,
                                    "recency": candidate["recency"], "field_status": candidate["field_status"]}
                    db.execute(
                        "INSERT INTO candidates VALUES (?, ?, ?) ON CONFLICT(source, id) DO UPDATE SET payload=excluded.payload",
                        (candidate["source"], candidate["id"], json.dumps(candidate, ensure_ascii=False, allow_nan=False)),
                    )
                report.candidate_results = list(results.values())
                report.new_count = sum(row["change"] == "new" for row in report.candidate_results)
                report.unchanged_count = sum(row["change"] == "unchanged" for row in report.candidate_results)
                report.changed_count = sum(row["change"] == "changed" for row in report.candidate_results)
                report.recent_count = sum(row["recency"] == "recent" for row in report.candidate_results)
                report.field_counts = {}
                for row in report.candidate_results:
                    for name, status in row["field_status"].items():
                        counts = report.field_counts.setdefault(name, {})
                        counts[status] = counts.get(status, 0) + 1
                db.execute("INSERT INTO runs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (report.id, json.dumps(asdict(report), ensure_ascii=False, allow_nan=False)))
                if source_limit is not None:
                    db.execute("INSERT INTO source_limits VALUES ('Freelancer', ?) ON CONFLICT(source) DO UPDATE SET payload=excluded.payload",
                               (json.dumps(asdict(source_limit), allow_nan=False),))
            return report
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            for name, value in checkpoint.items():
                setattr(report, name, value)
            raise StorageError("Unable to commit collection; transaction rolled back") from None

    def is_ended(self, source: str, project_id: str, url: Optional[str]) -> bool:
        try:
            return self._connection().execute(
                "SELECT 1 FROM ended_records WHERE source=? AND (id=? OR canonical_url=?) LIMIT 1",
                (source, project_id, canonical_url(url)),
            ).fetchone() is not None
        except (sqlite3.Error, ValueError):
            raise StorageError("Unable to check ended records") from None

    def record_ended(self, candidate: dict[str, Any], deleted_at: str, reason: str, report: RunReport) -> None:
        record = {"source": candidate["source"], "id": candidate["id"], "url": candidate["url"],
                  "deleted_at": deleted_at, "reason": reason}
        db = self._connection()
        old_count = report.confirmed_ended_count
        try:
            with db:
                inserted = db.execute("INSERT OR IGNORE INTO ended_records VALUES (?, ?, ?, ?)",
                                      (record["source"], record["id"], canonical_url(record["url"]), json.dumps(record, ensure_ascii=False))).rowcount
                report.confirmed_ended_count += inserted
                db.execute("INSERT INTO recheck_state VALUES ('Freelancer', ?) ON CONFLICT(source) DO UPDATE SET cursor=excluded.cursor", (record["id"],))
                db.execute("INSERT INTO runs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                           (report.id, json.dumps(asdict(report), ensure_ascii=False)))
        except (sqlite3.Error, ValueError, TypeError):
            report.confirmed_ended_count = old_count
            raise StorageError("Unable to save ended record; candidate preserved") from None

    def cleanup_ended(self) -> int:
        db = self._connection()
        removed = 0
        try:
            with db:
                for row in self._read("SELECT payload FROM candidates"):
                    if self.is_ended(row["source"], row["id"], row.get("url")):
                        removed += db.execute("DELETE FROM candidates WHERE source=? AND id=?", (row["source"], row["id"])).rowcount
            return removed
        except sqlite3.Error:
            raise StorageError("Ended details cleanup incomplete; retry collection") from None

    def ended_records(self) -> list[dict[str, Any]]:
        return self._read("SELECT payload FROM ended_records ORDER BY source, id")

    def delete_source_data(self, source: str, *, project_id: Optional[str] = None,
                           url: Optional[str] = None) -> SourceDeletionResult:
        if (project_id is None) == (url is None):
            raise ValueError("Specify exactly one project ID or URL")
        for value in (source, project_id if project_id is not None else url):
            if not isinstance(value, str) or not value or value != value.strip() or any(ord(char) < 32 for char in value):
                raise ValueError("Source and selector must be nonempty text without surrounding whitespace or controls")
        if url is not None:
            try:
                parts = urlsplit(url)
                if parts.scheme not in ("http", "https") or not parts.hostname:
                    raise ValueError
            except ValueError:
                raise ValueError("Project URL must be an absolute HTTP or HTTPS URL") from None
        db = self._connection()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                rows = [(table, row) for table in ("candidates", "ended_records")
                        for row in self._read("SELECT payload FROM " + table) if row["source"] == source]
                ids = {project_id} if project_id is not None else set()
                urls = {canonical_url(url)} if url is not None else set()
                # A known ID can have a saved and an ended URL; follow both and their aliases.
                changed = True
                while changed:
                    before = (len(ids), len(urls))
                    for _, row in rows:
                        normalized = canonical_url(row.get("url"))
                        if row["id"] in ids or (normalized is not None and normalized in urls):
                            ids.add(row["id"])
                            if normalized is not None:
                                urls.add(normalized)
                    changed = before != (len(ids), len(urls))
                counts = {"candidates": 0, "ended_records": 0}
                for table, row in rows:
                    if row["id"] in ids:
                        counts[table] += db.execute("DELETE FROM " + table + " WHERE source=? AND id=?",
                                                    (source, row["id"])).rowcount
                cursors = 0
                for identifier in ids:
                    cursors += db.execute("DELETE FROM recheck_state WHERE source=? AND cursor=?", (source, identifier)).rowcount
                redacted = 0
                for run in self.runs():
                    run_redacted = 0
                    for field, count_field in (("candidate_results", "redacted_candidate_results"),
                                               ("requests", "redacted_detail_requests")):
                        entries = run.get(field, [])
                        kept = [entry for entry in entries
                                if not (entry.get("source") == source and entry.get("id") in ids)]
                        removed = len(entries) - len(kept)
                        if removed:
                            run[field] = kept
                            run[count_field] = run.get(count_field, 0) + removed
                            run_redacted += removed
                    if run_redacted:
                        db.execute("UPDATE runs SET payload=? WHERE id=?", (json.dumps(run, ensure_ascii=False, allow_nan=False), run["id"]))
                        redacted += run_redacted
            return SourceDeletionResult(counts["candidates"], counts["ended_records"], redacted, cursors)
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            raise StorageError("Source deletion failed; transaction rolled back; retry deletion") from None

    def candidates(self) -> list[dict[str, Any]]:
        return [row for row in self._read("SELECT payload FROM candidates ORDER BY source, id")
                if not self.is_ended(row["source"], row["id"], row.get("url"))]

    def runs(self) -> list[dict[str, Any]]:
        return self._read("SELECT payload FROM runs ORDER BY rowid")

    def _read(self, query: str) -> list[dict[str, Any]]:
        try:
            return [json.loads(row[0]) for row in self._connection().execute(query)]
        except (sqlite3.Error, ValueError):
            raise StorageError("Unable to read collection state") from None

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
