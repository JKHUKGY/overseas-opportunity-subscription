"""Explicit one-shot collection, bounded foreground scheduling and local controls."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import Config, SQLiteStore, StorageError, collect
from .source import FreelancerSource
from .scheduling import Scheduler
from .reporting import observation_report


def _add_collection_arguments(action: argparse.ArgumentParser, *, require_budgets: bool = False) -> None:
    action.add_argument("--query", action="append", help="可重复指定；默认 illustration 和 portrait")
    action.add_argument("--limit", type=int, default=5)
    action.add_argument("--pages", type=int, default=1)
    action.add_argument("--max-requests", type=int, default=2, required=require_budgets)
    action.add_argument("--request-timeout", type=float, default=20)
    action.add_argument("--max-seconds", type=float, default=40, required=require_budgets)
    action.add_argument("--recheck-limit", type=int, default=1)


def _collection_config(args: argparse.Namespace) -> Config:
    return Config(tuple(args.query or ("illustration", "portrait")), args.limit,
                  args.pages, args.max_requests, args.request_timeout, args.max_seconds, args.recheck_limit)


def _schedule_command(args: argparse.Namespace) -> int:
    config = _collection_config(args) if args.action == "start" else None
    if args.action != "start" and not args.state.is_file():
        raise StorageError("State does not exist; create a schedule first")
    with SQLiteStore(args.state) as store:
        scheduler = Scheduler(store)
        if args.action == "start":
            assert config is not None
            result = asdict(scheduler.start(config, interval_seconds=args.interval_seconds,
                                             max_runs=args.max_runs, until=args.until))
        elif args.action == "status":
            result = asdict(scheduler.status())
        elif args.action in ("pause", "resume", "stop"):
            result = asdict(scheduler.control(args.action))
        else:
            source = FreelancerSource(os.environ.get("FLN_OAUTH_TOKEN", ""))
            result = asdict(scheduler.tick(source) if args.action == "tick" else scheduler.work(source))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Freelancer 候选采集实验与本地状态管理")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "list", "runs", "ended", "delete-source", "report"):
        action = commands.add_parser(command)
        action.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "freelancer.sqlite3")
        if command == "delete-source":
            action.add_argument("--source", required=True)
            selector = action.add_mutually_exclusive_group(required=True)
            selector.add_argument("--project-id")
            selector.add_argument("--url")
        if command == "run":
            _add_collection_arguments(action)
        if command == "report":
            action.add_argument("--start", type=datetime.fromisoformat, required=True, help="含时区，包含起点")
            action.add_argument("--end", type=datetime.fromisoformat, required=True, help="含时区，不含终点")
    schedule = commands.add_parser("schedule", help="持久计划与显式前台执行器")
    controls = schedule.add_subparsers(dest="action", required=True)
    for name in ("start", "status", "pause", "resume", "stop", "tick", "work"):
        control = controls.add_parser(name)
        control.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "freelancer.sqlite3")
        if name == "start":
            _add_collection_arguments(control, require_budgets=True)
            control.add_argument("--interval-seconds", type=float, required=True)
            control.add_argument("--max-runs", type=int)
            control.add_argument("--until", type=datetime.fromisoformat, help="带时区的 ISO 日期时间")
    args = parser.parse_args()
    if args.command == "schedule" and args.action == "start" and args.max_runs is None and args.until is None:
        parser.error("schedule start requires --max-runs or --until")
    try:
        if args.command == "schedule":
            return _schedule_command(args)
        if args.command == "run":
            config = _collection_config(args)
            source = FreelancerSource(os.environ.get("FLN_OAUTH_TOKEN", ""))
            with SQLiteStore(args.state) as store:
                report = collect(config, store, source)
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if report.status == "failed" else 0
        if not args.state.is_file():
            raise StorageError("State does not exist; run collection first")
        with SQLiteStore(args.state) as store:
            if args.command == "report":
                observation = observation_report(store, start=args.start, end=args.end)
                print(json.dumps(observation, ensure_ascii=False, indent=2, allow_nan=False))
                return 0
            if args.command == "delete-source":
                result = store.delete_source_data(args.source, project_id=args.project_id, url=args.url)
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
                return 0
            rows = store.candidates() if args.command == "list" else store.ended_records() if args.command == "ended" else store.runs()
        print(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"error": "Worker interrupted; saved schedule and progress retained"}), file=sys.stderr)
        return 130
    except (ValueError, StorageError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
