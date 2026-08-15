"""Load and normalize CarMax/Apify result exports."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


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
    "url": ("url", "listingUrl", "vehicleUrl", "detailUrl", "carUrl"),
    "drivetrain": ("drivetrain", "driveTrain"),
    "engine": ("engine", "engineDescription", "engineType"),
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


class ApifyCollectionError(RuntimeError):
    """Raised when a live Actor run cannot be safely completed."""


def load_search_config(path: str | Path, search_name: str | None = None) -> dict[str, Any]:
    """Load one named search while keeping actor input separate from app metadata."""
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    searches = payload.get("searches", []) if isinstance(payload, dict) else []
    if not isinstance(searches, list) or not searches:
        raise ValueError("Search config must contain a non-empty 'searches' array")
    if search_name:
        search = next((item for item in searches if item.get("name") == search_name), None)
        if search is None:
            choices = ", ".join(str(item.get("name")) for item in searches)
            raise ValueError(f"Search '{search_name}' was not found. Available searches: {choices}")
    elif len(searches) == 1:
        search = searches[0]
    else:
        raise ValueError("More than one search is configured; pass --search-name")
    actor_input = search.get("actor_input")
    if not isinstance(actor_input, dict):
        raise ValueError("The selected search needs an 'actor_input' JSON object")
    serialized = json.dumps(actor_input)
    if "YOUR_ZIP_CODE" in serialized:
        raise ValueError("Replace YOUR_ZIP_CODE in config/searches.json before a live run")
    return search


def fetch_from_apify(
    search: dict[str, Any],
    *,
    token: str | None = None,
    actor_id: str | None = None,
    timeout_seconds: int = 300,
    max_items: int = 100,
) -> list[dict[str, Any]]:
    """Run one Apify Actor synchronously and normalize its dataset items.

    This intentionally does not retry: a timed-out request may still represent a paid
    Actor run, so an automatic retry could create duplicate charges.
    """
    api_token = token or os.getenv("APIFY_API_TOKEN", "").strip()
    selected_actor = actor_id or os.getenv("APIFY_ACTOR_ID", "").strip()
    if not api_token:
        raise ApifyCollectionError("APIFY_API_TOKEN is missing from your local .env file")
    if not selected_actor:
        raise ApifyCollectionError("APIFY_ACTOR_ID is missing from your local .env file")
    if not 1 <= max_items <= 1_000:
        raise ValueError("max_items must be between 1 and 1,000")
    if not 30 <= timeout_seconds <= 300:
        raise ValueError("timeout_seconds must be between 30 and 300")

    actor_path = quote(selected_actor.replace("/", "~"), safe="~")
    query = urlencode({"format": "json", "clean": "true", "timeout": timeout_seconds, "maxItems": max_items})
    endpoint = f"https://api.apify.com/v2/actors/{actor_path}/run-sync-get-dataset-items?{query}"
    body = json.dumps(search["actor_input"]).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "trexx-autoscout/0.2",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds + 30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ApifyCollectionError(f"Apify returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise ApifyCollectionError(f"Could not reach Apify: {error.reason}") from error
    except TimeoutError as error:
        raise ApifyCollectionError(
            "The request timed out. Check the run in Apify Console before trying again; "
            "the Actor may still have run and incurred usage."
        ) from error
    except json.JSONDecodeError as error:
        raise ApifyCollectionError("Apify returned a response that was not valid JSON") from error

    if not isinstance(payload, list):
        raise ApifyCollectionError("Apify returned JSON, but not a dataset-item array")
    normalized = [normalize_listing(item) for item in payload if isinstance(item, dict)]
    valid = [item for item in normalized if item["vin"] and item["price"] is not None]
    if payload and not valid:
        raise ApifyCollectionError(
            "The Actor returned items, but none contained a recognizable VIN and price. "
            "Its output mapping may need an update."
        )
    return valid
