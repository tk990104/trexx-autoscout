"""Transparent starter deal score for normalized listings."""

from __future__ import annotations

from typing import Any


def calculate_deal_score(listing: dict[str, Any], market_price: float | None = None) -> int:
    """Return a basic 0-100 score; higher means more attractive, not safer."""
    price = float(listing.get("price") or 0)
    mileage = int(listing.get("mileage") or 0)
    transfer_fee = float(listing.get("transfer_fee") or 0)
    original_price = float(listing.get("original_price") or 0)

    if market_price and market_price > 0 and price > 0:
        price_ratio = price / market_price
        price_points = max(0.0, min(55.0, 27.5 + (1.0 - price_ratio) * 137.5))
    else:
        price_points = 27.5

    mileage_points = max(0.0, min(25.0, 25.0 - (mileage / 100_000) * 25.0))
    fee_points = max(0.0, min(10.0, 10.0 - (transfer_fee / 2_000) * 10.0))
    drop_points = 0.0
    if original_price > price > 0:
        drop_points = min(10.0, ((original_price - price) / original_price) * 100.0)

    return int(round(max(0.0, min(100.0, price_points + mileage_points + fee_points + drop_points))))


def score_explanation(listing: dict[str, Any], market_price: float | None) -> str:
    if market_price:
        difference = float(listing["price"]) - market_price
        relation = "below" if difference < 0 else "above"
        return f"Price is ${abs(difference):,.0f} {relation} the local same-model benchmark."
    return "Not enough same-model observations for a price benchmark; neutral price points were used."

