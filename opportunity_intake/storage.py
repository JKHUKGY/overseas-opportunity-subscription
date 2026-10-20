"""Atomic candidate and run persistence, with public readback operations."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from .models import ChangeKind, RunReport, SourceLimit


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
            if not existed:
                path.chmod(0o600)
                with db:
                    db.execute("CREATE TABLE candidates (source TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY (source, id))")
                    db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                    db.execute("PRAGMA user_version = 1")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise StorageError("State integrity check failed")
            version = db.execute("PRAGMA user_version").fetchone()
            if version not in ((1,), (2,)):
                raise StorageError("Unrecognized state schema; refusing to reset it")
            db.execute("SELECT source, id, payload FROM candidates LIMIT 0")
            db.execute("SELECT id, payload FROM runs LIMIT 0")
            if version == (1,):
                db.execute("BEGIN IMMEDIATE")
                with db:
                    db.execute("CREATE TABLE source_limits (source TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                    db.execute("PRAGMA user_version = 2")
            db.execute("SELECT source, payload FROM source_limits LIMIT 0")
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

    def commit_run(self, candidates: list[dict[str, Any]], report: RunReport,
                   source_limit: Optional[SourceLimit] = None) -> RunReport:
        db = self._connection()
        checkpoint = asdict(report)
        results = {(row["source"], row["id"]): row for row in report.candidate_results}
        try:
            with db:
                for candidate in candidates:
                    previous = db.execute(
                        "SELECT payload FROM candidates WHERE source = ? AND id = ?",
                        (candidate["source"], candidate["id"]),
                    ).fetchone()
                    change: ChangeKind = "new"
                    if previous:
                        saved = json.loads(previous[0])
                        for field in ("first_seen_at", "status", "processing_status", "last_status_verified_at"):
                            candidate[field] = saved[field]
                        if candidate["published_at"] is None:
                            candidate["published_at"] = saved.get("published_at")
                            candidate["published_at_read_at"] = saved.get("published_at_read_at")
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

    def candidates(self) -> list[dict[str, Any]]:
        return self._read("SELECT payload FROM candidates ORDER BY source, id")

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
