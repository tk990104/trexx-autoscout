"""Windows-friendly command-line entrypoint for T-Rexx AutoScout."""

from __future__ import annotations

import argparse
import os
from contextlib import closing
from pathlib import Path

from analysis.price_history import new_listings, price_changes
from collectors.carmax import load_export
from database import connect, latest_scan_id, save_snapshot
from reports.notebooklm import write_markdown


def load_local_env(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE settings without adding a package dependency."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def ingest(args: argparse.Namespace) -> None:
    listings = load_export(args.input)
    if not listings:
        raise SystemExit("No valid listings found. Each row needs at least a VIN and price.")
    with closing(connect(args.database)) as connection:
        scan_id = save_snapshot(
            connection,
            listings,
            source_file=str(Path(args.input)),
            search_name=args.search_name,
        )
        additions = new_listings(connection, scan_id)
        changes = price_changes(connection, scan_id)
        print(f"Saved scan {scan_id}: {len(listings)} listings, {len(additions)} first-seen, {len(changes)} price changes")
        if args.report:
            output = write_markdown(connection, scan_id, args.report)
            print(f"NotebookLM-ready report: {output}")


def report(args: argparse.Namespace) -> None:
    with closing(connect(args.database)) as connection:
        scan_id = args.scan_id or latest_scan_id(connection)
        output = write_markdown(connection, scan_id, args.output)
        print(f"NotebookLM-ready report: {output}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Local CarMax listing research and change tracking")
    root.add_argument("--database", help="SQLite path (default: DATABASE_PATH or data/autoscout.db)")
    commands = root.add_subparsers(dest="command", required=True)

    ingest_parser = commands.add_parser("ingest", help="Import a CarMax/Apify JSON or CSV export")
    ingest_parser.add_argument("input", help="Path to a JSON or CSV export")
    ingest_parser.add_argument("--search-name", default="manual-import")
    ingest_parser.add_argument("--report", help="Also write a NotebookLM-ready Markdown report")
    ingest_parser.set_defaults(func=ingest)

    report_parser = commands.add_parser("report", help="Create a report from a stored scan")
    report_parser.add_argument("--scan-id", type=int, help="Default: most recent scan")
    report_parser.add_argument("--output", default="reports/output/latest.md")
    report_parser.set_defaults(func=report)
    return root


if __name__ == "__main__":
    load_local_env()
    arguments = parser().parse_args()
    arguments.func(arguments)
