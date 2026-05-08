"""
Order book data generator.

Pure function module — no I/O, no DB access, fully unit-testable.
Generates synthetic BID/ASK price levels for a given symbol,
ensuring all prices are exact multiples of tick_size.
"""
import random
from decimal import ROUND_DOWN, Decimal


def _round_to_tick(price: Decimal, tick_size: Decimal) -> Decimal:
    """Round price DOWN to the nearest tick_size multiple.

    Uses ROUND_DOWN (floor) to ensure BID prices never exceed mid_price
    and to avoid floating-point precision issues.

    Args:
        price:     Raw price value.
        tick_size: Minimum price increment (e.g., Decimal("0.01")).

    Returns:
        Price quantized to tick_size, rounded down.
    """
    return (price / tick_size).to_integral_value(rounding=ROUND_DOWN) * tick_size


def generate_orders(
    tick_size: Decimal,
    mid_price: Decimal,
    num_levels: int = 10,
    seed: int | None = None,
) -> list[dict]:
    """Generate num_levels BID and num_levels ASK orders around mid_price.

    BID prices step *down* from mid_price in tick_size increments.
    ASK prices step *up* from mid_price in tick_size increments.
    Quantities are random integers in [100, 10_000], seeded for reproducibility.

    Args:
        tick_size:  Minimum price increment for the symbol.
        mid_price:  Synthetic mid-market reference price.
        num_levels: Number of price levels on each side (BID + ASK).
        seed:       Optional integer seed for reproducible output.

    Returns:
        List of order dicts with keys:
            side              (str):     "BID" or "OFFER"
            price             (Decimal): tick_size-aligned price
            quantity_original (int):     order size in units
    """
    rng = random.Random(seed)
    orders: list[dict] = []

    for level in range(1, num_levels + 1):
        spread = tick_size * level
        bid_price = _round_to_tick(mid_price - spread, tick_size)
        ask_price = _round_to_tick(mid_price + spread, tick_size)
        qty = rng.randint(100, 10_000)

        orders.append({
            "side":              "BID",
            "price":             bid_price,
            "quantity_original": qty,
        })
        orders.append({
            "side":              "OFFER",
            "price":             ask_price,
            "quantity_original": qty,
        })

    return orders
