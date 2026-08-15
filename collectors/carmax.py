"""Load and normalize CarMax/Apify result exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


ALIASES: dict[str, tuple[str, ...]] = {
    "vin": ("vin", "VIN"),
    "stock_number": ("stockNumber", "stock_number", "stockNo"),
    "year": ("year",),
    "make": ("make",),
    "model": ("model",),
    "trim": ("trim", "trimName"),
    "price": ("price", "currentPrice", "salePrice"),
    "original_price": ("originalPrice", "original_price", "previousPrice"),
    "mileage": ("mileage", "miles", "odometer"),
    "store_name": ("storeName", "store_name", "location", "store"),
    "transfer_fee": ("transferFee", "transfer_fee"),
    "url": ("url", "listingUrl", "vehicleUrl"),
    "drivetrain": ("drivetrain", "driveTrain"),
    "engine": ("engine", "engineDescription"),
    "mpg_city": ("mpgCity", "mpg_city", "cityMpg"),
    "mpg_highway": ("mpgHighway", "mpg_highway", "highwayMpg"),
}


def _first(record: dict[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _number(value: Any, *, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value) if integer else float(value)
    cleaned = str(value).replace("$", "").replace(",", "").replace(" miles", "").strip()
    try:
        parsed = float(cleaned)
        return int(parsed) if integer else parsed
    except ValueError:
        return None


def normalize_listing(record: dict[str, Any]) -> dict[str, Any]:
    """Map common CarMax/Apify field variants into the MVP schema."""
    normalized = {field: _first(record, aliases) for field, aliases in ALIASES.items()}
    normalized["vin"] = str(normalized["vin"] or "").strip().upper()
    normalized["stock_number"] = str(normalized["stock_number"] or "").strip()
    normalized["year"] = _number(normalized["year"], integer=True)
    normalized["price"] = _number(normalized["price"])
    normalized["original_price"] = _number(normalized["original_price"])
    normalized["mileage"] = _number(normalized["mileage"], integer=True)
    normalized["transfer_fee"] = _number(normalized["transfer_fee"])
    normalized["mpg_city"] = _number(normalized["mpg_city"])
    normalized["mpg_highway"] = _number(normalized["mpg_highway"])
    for field in ("make", "model", "trim", "store_name", "url", "drivetrain", "engine"):
        normalized[field] = str(normalized[field] or "").strip()
    normalized["raw_json"] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return normalized


def load_export(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSON array/object or CSV export and return normalized listings."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
    elif source.suffix.lower() == ".json":
        with source.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = next(
                (payload[key] for key in ("items", "results", "data") if isinstance(payload.get(key), list)),
                [payload],
            )
        else:
            raise ValueError("JSON input must contain an object or an array of objects")
    else:
        raise ValueError("Supported input formats are .json and .csv")

    normalized = [normalize_listing(item) for item in records if isinstance(item, dict)]
    return [item for item in normalized if item["vin"] and item["price"] is not None]


def fetch_from_apify(search: dict[str, Any]) -> list[dict[str, Any]]:
    """Placeholder for live collection; file imports work without network access."""
    # TODO: Read APIFY_API_TOKEN and APIFY_ACTOR_ID from the local environment.
    # TODO: Start the approved actor with values from config/searches.json.
    # TODO: Poll the run, download its dataset items, then normalize each item.
    # TODO: Add retry, timeout, rate-limit, and actor-output validation.
    raise NotImplementedError(
        "Live Apify collection is not wired yet. Export the actor dataset as JSON or CSV "
        "and run `python app.py ingest <export-file>`."
    )

