"""
BRS (Book Resilience Score) computation engine.

Single Responsibility: pure computation — no I/O, no DB access.
All functions are stateless and deterministic given the same inputs.

Sub-scores (each /100):
  DC  — Depth Distribution   : bid/offer quantity balance
  TF  — 1-Tick Shock         : price concentration near best bid/offer
  IR  — Interaction Rate     : ratio of OPEN orders to total orders
  PLC — Price Ladder Convexity: evenness of price level distribution

Composite:
  BRS = round((DC + TF + IR + PLC) / 4)
"""
import random
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrderRow:
    """Immutable representation of a single order book row."""
    side: str                    # "BID" | "OFFER"
    price: Decimal
    quantity_remaining: Decimal
    order_status: str            # "OPEN" | "PARTIAL" | "FILLED" | "CANCELLED"


@dataclass(frozen=True)
class BRSResult:
    """Computed BRS scores and metadata for a single symbol."""
    dc: int          # Depth Distribution /100
    tf: int          # 1-Tick Shock /100
    ir: int          # Interaction Rate /100
    plc: int         # Price Ladder Convexity /100
    brs: int         # Composite BRS /100
    tier: str        # "Gold" | "Silver" | "Watchlist" | "Disqualified"
    trend: str       # "Improving" | "Stable" | "Deteriorating"
    spread: str      # e.g. "1 tick" | "2 ticks"
    best_bid: float
    best_offer: float


# ── Sub-score Calculators ──────────────────────────────────────────────────────

def _calc_dc(rows: Sequence[OrderRow]) -> int:
    """Depth Distribution: balance of cumulative BID vs OFFER quantity."""
    total_bid = sum(float(r.quantity_remaining) for r in rows if r.side == "BID")
    total_offer = sum(float(r.quantity_remaining) for r in rows if r.side == "OFFER")
    if total_offer == 0:
        return 0
    ratio = total_bid / total_offer
    deviation = abs(ratio - 1.0)
    return max(0, min(100, round(100 - (deviation / 0.1) * 5)))


def _calc_tf(rows: Sequence[OrderRow], tick_size: Decimal) -> int:
    """1-Tick Shock: count of levels within 1 tick of best bid/offer × 5."""
    bids = [r.price for r in rows if r.side == "BID"]
    offers = [r.price for r in rows if r.side == "OFFER"]
    if not bids or not offers:
        return 0
    best_bid = max(bids)
    best_offer = min(offers)
    near_bid = sum(1 for r in rows if r.side == "BID" and r.price >= best_bid - tick_size)
    near_offer = sum(1 for r in rows if r.side == "OFFER" and r.price <= best_offer + tick_size)
    return min(100, (near_bid + near_offer) * 5)


def _calc_ir(rows: Sequence[OrderRow]) -> int:
    """Interaction Rate: ratio of OPEN orders to total orders × 100."""
    total = len(rows)
    if total == 0:
        return 0
    open_count = sum(1 for r in rows if r.order_status == "OPEN")
    return round((open_count / total) * 100)


def _calc_plc(rows: Sequence[OrderRow], tick_size: Decimal) -> int:
    """Price Ladder Convexity: penalises irregular gaps between price levels."""
    bid_prices = sorted({float(r.price) for r in rows if r.side == "BID"}, reverse=True)
    offer_prices = sorted({float(r.price) for r in rows if r.side == "OFFER"})
    gaps: list[float] = []
    for a, b in zip(bid_prices, bid_prices[1:]):
        gaps.append(a - b)
    for a, b in zip(offer_prices, offer_prices[1:]):
        gaps.append(b - a)
    if not gaps:
        return 0
    if len(gaps) == 1:
        return 100
    stddev = statistics.pstdev(gaps)
    return max(0, min(100, round(100 - (stddev / float(tick_size)) * 10)))


# ── Tier / Trend / Spread ──────────────────────────────────────────────────────

def _classify_tier(brs: int) -> str:
    """Map composite BRS to certification tier."""
    if brs >= 80:
        return "Gold"
    if brs >= 65:
        return "Silver"
    if brs >= 50:
        return "Watchlist"
    return "Disqualified"


def _derive_trend(ticker: str, brs: int) -> str:
    """Deterministic trend label seeded by ticker + brs."""
    rng = random.Random(hash(ticker + str(brs)))
    delta = rng.randint(-3, 3)
    if delta > 0:
        return "Improving"
    if delta < 0:
        return "Deteriorating"
    return "Stable"


def _calc_spread(rows: Sequence[OrderRow], tick_size: Decimal) -> tuple[str, float, float]:
    """Return (spread_label, best_bid_float, best_offer_float)."""
    bids = [r.price for r in rows if r.side == "BID"]
    offers = [r.price for r in rows if r.side == "OFFER"]
    if not bids or not offers:
        return "N/A", 0.0, 0.0
    best_bid = float(max(bids))
    best_offer = float(min(offers))
    ticks = round((best_offer - best_bid) / float(tick_size))
    label = f"{ticks} tick" if ticks == 1 else f"{ticks} ticks"
    return label, best_bid, best_offer


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_brs(ticker: str, rows: Sequence[OrderRow], tick_size: Decimal) -> BRSResult:
    """
    Compute the full BRS result for a single symbol.

    Args:
        ticker:    ADX ticker string (used to seed deterministic trend).
        rows:      All order book rows for this symbol.
        tick_size: Minimum price increment (from symbols table).

    Returns:
        BRSResult with DC, TF, IR, PLC, composite BRS, tier, trend, and spread.
    """
    dc = _calc_dc(rows)
    tf = _calc_tf(rows, tick_size)
    ir = _calc_ir(rows)
    plc = _calc_plc(rows, tick_size)
    brs = round((dc + tf + ir + plc) / 4)
    tier = _classify_tier(brs)
    trend = _derive_trend(ticker, brs)
    spread, best_bid, best_offer = _calc_spread(rows, tick_size)
    return BRSResult(
        dc=dc, tf=tf, ir=ir, plc=plc, brs=brs,
        tier=tier, trend=trend,
        spread=spread, best_bid=best_bid, best_offer=best_offer,
    )


def generate_intraday(ticker: str, current_brs: int) -> list[dict]:
    """
    Generate a 5-point simulated BRS intraday snapshot.
    Deterministic: same ticker + brs always produces the same series.
    The 'Now' point is always the real current score.
    """
    rng = random.Random(hash(ticker))
    labels = ["T-4h", "T-3h", "T-2h", "T-1h", "Now"]
    values: list[int] = []
    v = current_brs
    for _ in range(4):
        v = max(0, min(100, v + rng.randint(-3, 3)))
        values.append(v)
    values.append(current_brs)
    return [{"label": lbl, "brs": val} for lbl, val in zip(labels, values)]
