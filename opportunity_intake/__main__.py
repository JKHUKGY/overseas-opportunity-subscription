"""Manual CLI; each run is bounded and exits after one collection cycle."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from . import Config, SQLiteStore, StorageError, collect
from .source import FreelancerSource


def main() -> int:
    parser = argparse.ArgumentParser(description="Freelancer 候选采集实验与本地状态管理")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "list", "runs", "ended", "delete-source"):
        action = commands.add_parser(command)
        action.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "freelancer.sqlite3")
        if command == "delete-source":
            action.add_argument("--source", required=True)
            selector = action.add_mutually_exclusive_group(required=True)
            selector.add_argument("--project-id")
            selector.add_argument("--url")
        if command == "run":
            action.add_argument("--query", action="append", help="可重复指定；默认 illustration 和 portrait")
            action.add_argument("--limit", type=int, default=5)
            action.add_argument("--pages", type=int, default=1)
            action.add_argument("--max-requests", type=int, default=2)
            action.add_argument("--request-timeout", type=float, default=20)
            action.add_argument("--max-seconds", type=float, default=40)
            action.add_argument("--recheck-limit", type=int, default=1, help="maximum stored candidates to recheck; 0 disables rechecks")
    args = parser.parse_args()
    try:
        if args.command == "run":
            config = Config(tuple(args.query or ("illustration", "portrait")), args.limit,
                            args.pages, args.max_requests, args.request_timeout, args.max_seconds, args.recheck_limit)
            source = FreelancerSource(os.environ.get("FLN_OAUTH_TOKEN", ""))
            with SQLiteStore(args.state) as store:
                report = collect(config, store, source)
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if report.status == "failed" else 0
        if not args.state.is_file():
            raise StorageError("State does not exist; run collection first")
        with SQLiteStore(args.state) as store:
            if args.command == "delete-source":
                result = store.delete_source_data(args.source, project_id=args.project_id, url=args.url)
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
                return 0
            rows = store.candidates() if args.command == "list" else store.ended_records() if args.command == "ended" else store.runs()
        print(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, StorageError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
