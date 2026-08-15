"""Queries for new listings and price movements between scans."""

from __future__ import annotations

import sqlite3
from typing import Any


def new_listings(connection: sqlite3.Connection, scan_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT o.*
        FROM observations o
        WHERE o.scan_id = ?
          AND NOT EXISTS (
            SELECT 1 FROM observations prior
            WHERE prior.vin = o.vin AND prior.scan_id < o.scan_id
          )
        ORDER BY o.deal_score DESC, o.price ASC
        """,
        (scan_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def price_changes(connection: sqlite3.Connection, scan_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT current.vin, current.year, current.make, current.model, current.trim,
               previous.price AS previous_price, current.price AS current_price,
               current.price - previous.price AS change_amount, current.url
        FROM observations current
        JOIN observations previous ON previous.id = (
            SELECT p.id FROM observations p
            WHERE p.vin = current.vin AND p.scan_id < current.scan_id
            ORDER BY p.scan_id DESC LIMIT 1
        )
        WHERE current.scan_id = ? AND current.price != previous.price
        ORDER BY change_amount ASC
        """,
        (scan_id,),
    ).fetchall()
    return [dict(row) for row in rows]

