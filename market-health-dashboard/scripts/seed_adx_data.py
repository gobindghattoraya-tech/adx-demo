"""
GCPAP999-326 — ADX Primary Symbol & Order Book Seed Script.

Populates the Cloud SQL PostgreSQL `adx_exchange` database with:
  - 6 market sectors
  - 15 ADX primary listed symbols
  - 300 order book rows (10 BID + 10 ASK per symbol)

Connects via Cloud SQL Auth Proxy running as a sidecar process on
127.0.0.1:5432 within the Cloud Build private pool step.

All operations are idempotent — safe to re-run without duplicating data.

Usage:
    python3 -m scripts.seed_adx_data

Environment variables:
    DB_PASSWORD  (required) — DB password from Secret Manager
    DB_USER      (optional, default: postgres)
    DB_HOST      (optional, default: 127.0.0.1)
    DB_PORT      (optional, default: 5432)
    DB_NAME      (optional, default: adx_exchange)
"""
import asyncio
import logging
import os
import sys
from decimal import Decimal

import asyncpg

from scripts.data.adx_symbols import SECTORS, SYMBOLS
from scripts.generators.order_book import generate_orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Synthetic mid-market prices per ticker (representative AED values) ─────────
MID_PRICES: dict[str, Decimal] = {
    "FAB":        Decimal("15.20"),
    "ADCB":       Decimal("9.80"),
    "ADIB":       Decimal("11.50"),
    "IHC":        Decimal("320.50"),
    "ALPHADHABI": Decimal("22.80"),
    "TAQA":       Decimal("2.85"),
    "ADNOCGAS":   Decimal("4.12"),
    "ADNOCDRILL": Decimal("4.45"),
    "ADNOCDIST":  Decimal("3.80"),
    "ADNOCLS":    Decimal("5.10"),
    "EAND":       Decimal("17.60"),
    "ETISALAT":   Decimal("9.25"),
    "ALDAR":      Decimal("6.30"),
    "MODON":      Decimal("8.75"),
    "BOROUGE":    Decimal("2.60"),
}

# ── Number of price levels per side of the order book ─────────────────────────
ORDER_BOOK_LEVELS = 10


def _db_config() -> dict:
    """Build asyncpg connection config from environment variables."""
    return {
        "host":     os.getenv("DB_HOST", "127.0.0.1"),
        "port":     int(os.getenv("DB_PORT", "5432")),
        "user":     os.getenv("DB_USER", "postgres"),
        "password": os.environ["DB_PASSWORD"],          # Required — raises KeyError if missing
        "database": os.getenv("DB_NAME", "adx_exchange"),
    }


async def seed_sectors(conn: asyncpg.Connection) -> dict[str, int]:
    """Insert all sectors with upsert, return {sector_name: sector_id} map.

    Uses ON CONFLICT DO UPDATE to refresh descriptions on re-runs.
    """
    sector_ids: dict[str, int] = {}
    for sector in SECTORS:
        row = await conn.fetchrow(
            """
            INSERT INTO sectors (sector_name, description)
            VALUES ($1, $2)
            ON CONFLICT (sector_name)
            DO UPDATE SET description = EXCLUDED.description
            RETURNING sector_id
            """,
            sector.name,
            sector.description,
        )
        sector_ids[sector.name] = row["sector_id"]
        log.info("  ✓ sector %-15s → id=%s", sector.name, row["sector_id"])
    return sector_ids


async def seed_symbols(
    conn: asyncpg.Connection,
    sector_ids: dict[str, int],
) -> dict[str, int]:
    """Insert all symbols with ON CONFLICT DO NOTHING, return {ticker: symbol_id} map.

    Fetches existing symbol_id for already-present tickers so that
    order book seeding can proceed correctly on re-runs.
    """
    symbol_ids: dict[str, int] = {}
    for sym in SYMBOLS:
        row = await conn.fetchrow(
            """
            INSERT INTO symbols
              (ticker_symbol, full_name, sector_id, tick_size, lot_size, currency, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            ON CONFLICT (ticker_symbol) DO NOTHING
            RETURNING symbol_id
            """,
            sym.ticker,
            sym.full_name,
            sector_ids[sym.sector_name],
            sym.tick_size,
            sym.lot_size,
            sym.currency,
        )
        if row:
            symbol_ids[sym.ticker] = row["symbol_id"]
            log.info("  ✓ symbol %-12s → id=%s", sym.ticker, row["symbol_id"])
        else:
            # Symbol exists — fetch id for order book seeding
            existing = await conn.fetchrow(
                "SELECT symbol_id FROM symbols WHERE ticker_symbol = $1",
                sym.ticker,
            )
            symbol_ids[sym.ticker] = existing["symbol_id"]
            log.info("  ↩ symbol %-12s already exists (id=%s)", sym.ticker, existing["symbol_id"])
    return symbol_ids


async def seed_order_books(
    conn: asyncpg.Connection,
    symbol_ids: dict[str, int],
) -> int:
    """Insert ORDER_BOOK_LEVELS BID + ORDER_BOOK_LEVELS OFFER orders per symbol.

    Skips symbols that already have >= (ORDER_BOOK_LEVELS * 2) orders.
    Uses ON CONFLICT DO NOTHING for extra safety on partial re-runs.

    Returns:
        Total number of order rows inserted in this run.
    """
    total_inserted = 0
    for sym in SYMBOLS:
        symbol_id = symbol_ids[sym.ticker]
        mid_price = MID_PRICES[sym.ticker]
        min_rows = ORDER_BOOK_LEVELS * 2

        # Idempotency guard: skip if already fully seeded
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM order_books WHERE symbol_id = $1",
            symbol_id,
        )
        if count >= min_rows:
            log.info("  ↩ order_book %-12s already seeded (%s rows)", sym.ticker, count)
            continue

        orders = generate_orders(
            tick_size=sym.tick_size,
            mid_price=mid_price,
            num_levels=ORDER_BOOK_LEVELS,
            seed=hash(sym.ticker) % (2**31),  # deterministic per ticker
        )

        records = [
            (
                symbol_id,
                o["side"],
                o["price"],
                o["quantity_original"],
                o["quantity_original"],   # quantity_remaining = quantity_original
                "OPEN",
            )
            for o in orders
        ]

        await conn.executemany(
            """
            INSERT INTO order_books
              (symbol_id, side, price, quantity_original, quantity_remaining, order_status)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            """,
            records,
        )
        total_inserted += len(records)
        log.info(
            "  ✓ order_book %-12s → %s orders inserted (BID×%s / OFFER×%s)",
            sym.ticker,
            len(records),
            ORDER_BOOK_LEVELS,
            ORDER_BOOK_LEVELS,
        )
    return total_inserted


async def run_seed() -> None:
    """Main seed orchestrator — runs all seed steps within a single transaction."""
    cfg = _db_config()
    log.info(
        "Connecting to %s@%s:%s/%s",
        cfg["user"], cfg["host"], cfg["port"], cfg["database"],
    )

    conn = await asyncpg.connect(**cfg)
    try:
        async with conn.transaction():
            log.info("── Seeding sectors (%s) ────────────────────────────", len(SECTORS))
            sector_ids = await seed_sectors(conn)

            log.info("── Seeding symbols (%s) ────────────────────────────", len(SYMBOLS))
            symbol_ids = await seed_symbols(conn, sector_ids)

            log.info("── Seeding order books ─────────────────────────────")
            total = await seed_order_books(conn, symbol_ids)
            log.info("   Total order rows inserted this run: %s", total)
    finally:
        await conn.close()

    log.info("✓ Seed complete — sectors=%s  symbols=%s  orders_this_run=%s",
             len(SECTORS), len(SYMBOLS), total)


if __name__ == "__main__":
    try:
        asyncio.run(run_seed())
    except KeyError as exc:
        log.error("Missing required environment variable: %s", exc)
        sys.exit(1)
    except (asyncpg.PostgresConnectionError, OSError) as exc:
        log.error("Connection refused or could not connect: %s", exc)
        sys.exit(1)
