"""
Market API v1 — FastAPI router for BRS dashboard endpoints.

Single Responsibility: HTTP layer only.
  - DB queries via SQLAlchemy async session (app.db.get_db dependency)
  - BRS computation delegated to app.brs_engine
  - Response serialisation via app.schemas Pydantic models
"""
import logging
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.brs_engine import OrderRow, compute_brs, generate_intraday
from app.db import get_db
from app.schemas import (
    BRSSnapshot,
    MarketSummary,
    OrderBookRow,
    SymbolBRS,
    SymbolDetail,
)

log = logging.getLogger(__name__)
router = APIRouter()

# ── SQL ────────────────────────────────────────────────────────────────────────

_SYMBOLS_OB_SQL = text("""
    SELECT
        s.ticker_symbol,
        s.full_name,
        sec.sector_name,
        CAST(s.tick_size AS FLOAT)          AS tick_size,
        ob.side,
        CAST(ob.price AS FLOAT)             AS price,
        CAST(ob.quantity_remaining AS FLOAT) AS quantity_remaining,
        ob.order_status
    FROM symbols s
    JOIN sectors sec ON s.sector_id = sec.sector_id
    JOIN order_books ob ON ob.symbol_id = s.symbol_id
    WHERE s.is_active = true
    ORDER BY s.ticker_symbol, ob.side, ob.price
""")

_SYMBOL_TRADES_SQL = text("""
    SELECT
        COALESCE(COUNT(t.trade_id), 0)               AS trades_count,
        COALESCE(SUM(CAST(t.execution_quantity AS FLOAT)), 0) AS volume_aed,
        COALESCE(SUM(CAST(t.total_value AS FLOAT)), 0)        AS value_aed
    FROM symbols s
    LEFT JOIN trades t ON t.symbol_id = s.symbol_id
    WHERE s.ticker_symbol = :ticker
      AND s.is_active = true
    GROUP BY s.symbol_id
""")

_DEPTH_SQL = text("""
    SELECT
        ob.side,
        CAST(ob.price AS FLOAT)              AS price,
        CAST(ob.quantity_remaining AS FLOAT) AS quantity_remaining
    FROM order_books ob
    JOIN symbols s ON s.symbol_id = ob.symbol_id
    WHERE s.ticker_symbol = :ticker
      AND ob.order_status IN ('OPEN', 'PARTIAL')
    ORDER BY
        CASE WHEN ob.side = 'BID'   THEN ob.price END DESC,
        CASE WHEN ob.side = 'OFFER' THEN ob.price END ASC
    LIMIT 20
""")


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _load_all_grouped(db: AsyncSession) -> dict[str, dict]:
    """Fetch all active symbols + order books, grouped by ticker."""
    result = await db.execute(_SYMBOLS_OB_SQL)
    rows = result.fetchall()
    grouped: dict[str, dict] = defaultdict(
        lambda: {"full_name": "", "sector": "", "tick_size": 0.01, "rows": []}
    )
    for r in rows:
        g = grouped[r.ticker_symbol]
        g["full_name"] = r.full_name
        g["sector"] = r.sector_name
        g["tick_size"] = r.tick_size
        g["rows"].append(
            OrderRow(
                side=r.side,
                price=Decimal(str(r.price)),
                quantity_remaining=Decimal(str(r.quantity_remaining)),
                order_status=r.order_status,
            )
        )
    return grouped


def _build_symbol_brs(ticker: str, meta: dict) -> SymbolBRS:
    """Compute BRS and return a SymbolBRS schema instance."""
    tick = Decimal(str(meta["tick_size"]))
    res = compute_brs(ticker, meta["rows"], tick)
    return SymbolBRS(
        ticker=ticker,
        full_name=meta["full_name"],
        sector=meta["sector"],
        brs=res.brs, dc=res.dc, tf=res.tf, ir=res.ir, plc=res.plc,
        tier=res.tier, trend=res.trend,
        spread=res.spread,
        best_bid=res.best_bid,
        best_offer=res.best_offer,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/market/summary", response_model=MarketSummary, summary="Market KPI summary")
async def market_summary(db: AsyncSession = Depends(get_db)) -> MarketSummary:
    """Return aggregate KPI counts: total symbols, certified, watchlist, avg BRS."""
    grouped = await _load_all_grouped(db)
    scores = [_build_symbol_brs(t, m) for t, m in grouped.items()]
    if not scores:
        return MarketSummary(
            total_symbols=0, certified_count=0,
            watchlist_count=0, disqualified_count=0, market_avg_brs=0,
        )
    certified = sum(1 for s in scores if s.tier in ("Gold", "Silver"))
    watchlist = sum(1 for s in scores if s.tier == "Watchlist")
    disqualified = sum(1 for s in scores if s.tier == "Disqualified")
    avg_brs = round(sum(s.brs for s in scores) / len(scores))
    return MarketSummary(
        total_symbols=len(scores),
        certified_count=certified,
        watchlist_count=watchlist,
        disqualified_count=disqualified,
        market_avg_brs=avg_brs,
    )


@router.get("/symbols", response_model=list[SymbolBRS], summary="All symbols ranked by BRS")
async def list_symbols(
    sector: str | None = None,
    tier: str | None = None,
    min_brs: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[SymbolBRS]:
    """
    Return all active symbols with BRS scores, sorted by BRS descending.
    Optional filters: sector, tier, min_brs.
    """
    grouped = await _load_all_grouped(db)
    scores = [_build_symbol_brs(t, m) for t, m in grouped.items()]
    if sector:
        scores = [s for s in scores if s.sector.lower() == sector.lower()]
    if tier:
        scores = [s for s in scores if s.tier.lower() == tier.lower()]
    scores = [s for s in scores if s.brs >= min_brs]
    return sorted(scores, key=lambda s: s.brs, reverse=True)


@router.get("/symbols/{ticker}", response_model=SymbolDetail, summary="Symbol BRS detail")
async def symbol_detail(ticker: str, db: AsyncSession = Depends(get_db)) -> SymbolDetail:
    """Return full BRS detail + trade statistics for a single ticker."""
    ticker = ticker.upper()
    grouped = await _load_all_grouped(db)
    if ticker not in grouped:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")
    meta = grouped[ticker]
    base = _build_symbol_brs(ticker, meta)

    result = await db.execute(_SYMBOL_TRADES_SQL, {"ticker": ticker})
    trade_row = result.fetchone()
    trades_count = int(trade_row.trades_count) if trade_row else 0
    volume_aed = float(trade_row.volume_aed) if trade_row else 0.0
    value_aed = float(trade_row.value_aed) if trade_row else 0.0

    return SymbolDetail(
        **base.model_dump(),
        trades_count=trades_count,
        volume_aed=volume_aed,
        value_aed=value_aed,
    )


@router.get(
    "/symbols/{ticker}/depth",
    response_model=list[OrderBookRow],
    summary="Order book depth (top 10 BID + 10 OFFER)",
)
async def symbol_depth(ticker: str, db: AsyncSession = Depends(get_db)) -> list[OrderBookRow]:
    """Return top 10 BID and 10 OFFER price levels for the depth chart."""
    ticker = ticker.upper()
    result = await db.execute(_DEPTH_SQL, {"ticker": ticker})
    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No depth data for '{ticker}'")
    return [
        OrderBookRow(side=r.side, price=r.price, quantity=r.quantity_remaining)
        for r in rows
    ]


@router.get(
    "/symbols/{ticker}/intraday",
    response_model=list[BRSSnapshot],
    summary="BRS 5-point intraday simulation",
)
async def symbol_intraday(ticker: str, db: AsyncSession = Depends(get_db)) -> list[BRSSnapshot]:
    """Return a deterministic 5-point BRS intraday snapshot for the trend chart."""
    ticker = ticker.upper()
    grouped = await _load_all_grouped(db)
    if ticker not in grouped:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")
    meta = grouped[ticker]
    base = _build_symbol_brs(ticker, meta)
    points = generate_intraday(ticker, base.brs)
    return [BRSSnapshot(label=p["label"], brs=p["brs"]) for p in points]
