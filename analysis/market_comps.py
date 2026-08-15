"""Simple same-make/model market comparisons."""

from __future__ import annotations

from statistics import median
from typing import Any, Iterable


def comparable_prices(target: dict[str, Any], listings: Iterable[dict[str, Any]]) -> list[float]:
    year = target.get("year")
    values: list[float] = []
    for candidate in listings:
        if candidate.get("vin") == target.get("vin"):
            continue
        same_name = (
            str(candidate.get("make", "")).casefold() == str(target.get("make", "")).casefold()
            and str(candidate.get("model", "")).casefold() == str(target.get("model", "")).casefold()
        )
        candidate_year = candidate.get("year")
        close_year = year is None or candidate_year is None or abs(int(candidate_year) - int(year)) <= 2
        price = candidate.get("price")
        if same_name and close_year and price:
            values.append(float(price))
    return values


def market_price_for(target: dict[str, Any], listings: Iterable[dict[str, Any]]) -> float | None:
    prices = comparable_prices(target, listings)
    return float(median(prices)) if len(prices) >= 2 else None

