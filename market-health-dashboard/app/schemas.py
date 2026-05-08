"""
Pydantic response schemas — type safety and auto-docs.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class HelloResponse(BaseModel):
    message: str


# ── Dashboard BRS response models ──────────────────────────────────────────────

class SymbolBRS(BaseModel):
    """BRS scores and metadata for a single symbol (used in symbol list)."""
    ticker: str
    full_name: str
    sector: str
    brs: int
    dc: int
    tf: int
    ir: int
    plc: int
    tier: str        # "Gold" | "Silver" | "Watchlist" | "Disqualified"
    trend: str       # "Improving" | "Stable" | "Deteriorating"
    spread: str      # e.g. "1 tick"
    best_bid: float
    best_offer: float


class SymbolDetail(SymbolBRS):
    """Extended symbol view with trade statistics (used in detail panel)."""
    trades_count: int
    volume_aed: float
    value_aed: float


class MarketSummary(BaseModel):
    """Market-level KPI aggregates (used in the KPI row)."""
    total_symbols: int
    certified_count: int    # Gold + Silver
    watchlist_count: int
    disqualified_count: int
    market_avg_brs: int


class OrderBookRow(BaseModel):
    """Single order book price level (used in depth chart)."""
    side: str     # "BID" | "OFFER"
    price: float
    quantity: float


class BRSSnapshot(BaseModel):
    """Single point in the BRS intraday simulation series."""
    label: str   # "T-4h" … "Now"
    brs: int
