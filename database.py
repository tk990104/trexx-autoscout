"""SQLite schema and snapshot persistence for T-Rexx AutoScout."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis.market_comps import market_price_for
from scoring.deal_score import calculate_deal_score


SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_file TEXT,
    search_name TEXT,
    collected_at TEXT NOT NULL,
    listing_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    vin TEXT NOT NULL,
    stock_number TEXT,
    year INTEGER,
    make TEXT,
    model TEXT,
    trim TEXT,
    price REAL NOT NULL,
    original_price REAL,
    mileage INTEGER,
    store_name TEXT,
    transfer_fee REAL,
    url TEXT,
    drivetrain TEXT,
    engine TEXT,
    mpg_city REAL,
    mpg_highway REAL,
    market_price REAL,
    deal_score INTEGER,
    raw_json TEXT NOT NULL,
    UNIQUE(scan_id, vin)
);

CREATE INDEX IF NOT EXISTS idx_observations_vin_scan ON observations(vin, scan_id);
CREATE INDEX IF NOT EXISTS idx_observations_scan_score ON observations(scan_id, deal_score DESC);
"""


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "data/autoscout.db"))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def save_snapshot(
    connection: sqlite3.Connection,
    listings: list[dict[str, Any]],
    *,
    source_file: str,
    search_name: str | None = None,
) -> int:
    """Persist one immutable scan and return its numeric ID."""
    collected_at = datetime.now(timezone.utc).isoformat()
    with connection:
        cursor = connection.execute(
            """INSERT INTO scans(source, source_file, search_name, collected_at, listing_count)
               VALUES (?, ?, ?, ?, ?)""",
            ("carmax", source_file, search_name, collected_at, len(listings)),
        )
        scan_id = int(cursor.lastrowid)
        columns = (
            "scan_id", "vin", "stock_number", "year", "make", "model", "trim", "price",
            "original_price", "mileage", "store_name", "transfer_fee", "url", "drivetrain",
            "engine", "mpg_city", "mpg_highway", "market_price", "deal_score", "raw_json",
        )
        placeholders = ", ".join("?" for _ in columns)
        for listing in listings:
            market_price = market_price_for(listing, listings)
            deal_score = calculate_deal_score(listing, market_price)
            values = [scan_id]
            values.extend(listing.get(column) for column in columns[1:17])
            values.extend((market_price, deal_score, listing.get("raw_json", json.dumps(listing))))
            connection.execute(
                f"INSERT OR REPLACE INTO observations ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
    return scan_id


def get_scan(connection: sqlite3.Connection, scan_id: int) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        raise ValueError(f"Scan {scan_id} does not exist")
    return dict(row)


def latest_scan_id(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(id) AS id FROM scans").fetchone()
    if row is None or row["id"] is None:
        raise ValueError("No scans have been imported yet")
    return int(row["id"])


def listings_for_scan(connection: sqlite3.Connection, scan_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM observations WHERE scan_id = ? ORDER BY deal_score DESC, price ASC",
        (scan_id,),
    ).fetchall()
    return [dict(row) for row in rows]

