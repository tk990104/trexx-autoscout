"""Produce source-grounded Markdown summaries suitable for NotebookLM."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis.price_history import new_listings, price_changes
from database import get_scan, listings_for_scan


def _vehicle_name(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key) or "").strip() for key in ("year", "make", "model", "trim")).strip()


def build_markdown(connection: sqlite3.Connection, scan_id: int, *, top_n: int = 10) -> str:
    scan = get_scan(connection, scan_id)
    listings = listings_for_scan(connection, scan_id)
    additions = new_listings(connection, scan_id)
    changes = price_changes(connection, scan_id)
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# T-Rexx AutoScout — CarMax Scan {scan_id}",
        "",
        f"- Collected: {scan['collected_at']}",
        f"- Report generated: {generated_at}",
        f"- Imported source: `{scan.get('source_file') or 'unknown'}`",
        f"- Listings: {len(listings)}",
        f"- First-seen listings: {len(additions)}",
        f"- Price changes: {len(changes)}",
        "",
        "## Top deals",
        "",
        "| Score | Vehicle | Price | Miles | Market benchmark | Store |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for item in listings[:top_n]:
        benchmark = f"${item['market_price']:,.0f}" if item.get("market_price") else "Insufficient comps"
        lines.append(
            f"| {item['deal_score']} | {_vehicle_name(item)} | ${item['price']:,.0f} | "
            f"{(item.get('mileage') or 0):,} | {benchmark} | {item.get('store_name') or 'Unknown'} |"
        )

    lines.extend(["", "## Price changes", ""])
    if changes:
        for item in changes:
            direction = "down" if item["change_amount"] < 0 else "up"
            lines.append(
                f"- **{_vehicle_name(item)}** ({item['vin']}): ${item['previous_price']:,.0f} → "
                f"${item['current_price']:,.0f} ({direction} ${abs(item['change_amount']):,.0f})"
            )
    else:
        lines.append("- No price changes were detected against the prior observation for each VIN.")

    lines.extend(["", "## First-seen listings", ""])
    if additions:
        for item in additions[:top_n]:
            link = f" — {item['url']}" if item.get("url") else ""
            lines.append(f"- **{_vehicle_name(item)}** — ${item['price']:,.0f}, {(item.get('mileage') or 0):,} miles{link}")
    else:
        lines.append("- No first-seen listings in this scan.")

    lines.extend(
        [
            "",
            "## Method and cautions",
            "",
            "The starter Deal Score is a 0–100 research-ranking heuristic. It weighs price against the "
            "median of at least two same-make/model listings within two model years, then considers "
            "mileage, transfer fee, and any advertised price reduction. A high score is not a vehicle "
            "inspection, history report, financing recommendation, or guarantee of value.",
            "",
            "Listings with too few comparable vehicles receive neutral price points. Confirm availability, "
            "options, taxes, fees, accident history, recalls, and mechanical condition before acting.",
            "",
            "## Suggested NotebookLM questions",
            "",
            "- Which listings combine a strong score with low mileage?",
            "- Which vehicles had the largest price drops?",
            "- Which models repeatedly appear below their market benchmark?",
            "- What should I verify before visiting the store?",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown(connection: sqlite3.Connection, scan_id: int, output: str | Path) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_markdown(connection, scan_id), encoding="utf-8")
    return destination

