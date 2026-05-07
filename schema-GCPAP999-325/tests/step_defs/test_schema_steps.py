"""
test_schema_steps.py
--------------------
BDD step definitions for the adx_exchange schema feature tests.

Design principles applied:
 - SRP: each step function does exactly one thing.
 - DRY: insert helpers (_insert_sector, _insert_symbol, _insert_order) are
   module-level so they are never duplicated.
 - Error handling: all DB errors are caught and stored on request.node so
   that 'Then' steps can assert on them cleanly.
 - Modular: steps are grouped by scenario concern with clear section headers.
"""

import uuid
import pg8000
import pytest
from pytest_bdd import given, when, then, scenarios, parsers

# Register all scenarios from the feature file
scenarios("../features/schema.feature")


# ══════════════════════════════════════════════════════════════════════════════
# Helper functions (DRY)
# ══════════════════════════════════════════════════════════════════════════════

def _insert_sector(cursor, name: str) -> int:
    """Insert a sector (or ignore if already exists) and return its sector_id."""
    cursor.execute(
        "INSERT INTO sectors (sector_name) VALUES (%s) "
        "ON CONFLICT (sector_name) DO UPDATE SET sector_name = EXCLUDED.sector_name "
        "RETURNING sector_id",
        (name,),
    )
    return cursor.fetchone()[0]


def _insert_symbol(cursor, ticker: str, tick_size: float, sector_id: int) -> int:
    """Insert a symbol and return its symbol_id."""
    cursor.execute(
        "INSERT INTO symbols (ticker_symbol, full_name, sector_id, tick_size, lot_size, currency) "
        "VALUES (%s, %s, %s, %s, 1, 'USD') "
        "ON CONFLICT (ticker_symbol) DO UPDATE SET tick_size = EXCLUDED.tick_size "
        "RETURNING symbol_id",
        (ticker, f"{ticker} Asset", sector_id, tick_size),
    )
    return cursor.fetchone()[0]


def _insert_order(cursor, symbol_id: int, side: str, price: float) -> int:
    """Insert an order book entry and return its order_id."""
    cursor.execute(
        "INSERT INTO order_books (symbol_id, side, price, quantity_original, quantity_remaining) "
        "VALUES (%s, %s, %s, 100, 100) RETURNING order_id",
        (symbol_id, side, price),
    )
    return cursor.fetchone()[0]


def _store_error(request, exc: Exception) -> None:
    """Store a caught DB exception on the pytest node for assertion by Then steps."""
    request.node._db_error = str(exc)


def _clear_error(request) -> None:
    request.node._db_error = None


def _get_error(request):
    return getattr(request.node, "_db_error", None)


# ══════════════════════════════════════════════════════════════════════════════
# Background
# ══════════════════════════════════════════════════════════════════════════════

@given('the "adx_exchange" database is reachable')
def db_is_reachable(db_cursor):
    """Verify connectivity by running a trivial query."""
    db_cursor.execute("SELECT 1")
    result = db_cursor.fetchone()
    assert result == (1,), f"Database ping failed: got {result}"


@given("all migration scripts have been applied")
def migrations_are_applied(db_cursor):
    """Confirm at least 5 tables exist — migrations must have run."""
    db_cursor.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    )
    count = db_cursor.fetchone()[0]
    assert count >= 5, f"Expected ≥5 tables, found {count}. Run apply_migrations.py first."


# ══════════════════════════════════════════════════════════════════════════════
# Table existence
# ══════════════════════════════════════════════════════════════════════════════

@when("I query the information_schema for public table names")
def query_public_tables(db_cursor):
    db_cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )


@then(parsers.parse("the following tables should exist:\n{table_data}"))
def check_tables_exist(db_cursor, table_data):
    expected = {
        line.strip().strip("|").strip()
        for line in table_data.splitlines()
        if line.strip() and "table_name" not in line
    }
    rows = {row[0] for row in db_cursor.fetchall()}
    missing = expected - rows
    assert not missing, f"Missing tables: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# ENUM types
# ══════════════════════════════════════════════════════════════════════════════

@when(parsers.parse('I query pg_type for enum "{enum_name}"'))
def query_enum(db_cursor, enum_name):
    db_cursor.execute(
        "SELECT enumlabel FROM pg_enum "
        "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
        "WHERE typname = %s ORDER BY enumsortorder",
        (enum_name,),
    )


@then(parsers.parse('the enum values should include "{v1}" and "{v2}"'))
def check_two_enum_values(db_cursor, v1, v2):
    values = {row[0] for row in db_cursor.fetchall()}
    assert v1 in values, f"'{v1}' missing from enum values: {values}"
    assert v2 in values, f"'{v2}' missing from enum values: {values}"


@then(parsers.parse('the enum values should include "{v1}", "{v2}", "{v3}", and "{v4}"'))
def check_four_enum_values(db_cursor, v1, v2, v3, v4):
    values = {row[0] for row in db_cursor.fetchall()}
    for v in (v1, v2, v3, v4):
        assert v in values, f"'{v}' missing from enum values: {values}"


# ══════════════════════════════════════════════════════════════════════════════
# Symbol–Sector FK
# ══════════════════════════════════════════════════════════════════════════════

@given(parsers.parse('a sector "{sector_name}" is inserted'))
def sector_inserted(db_cursor, sector_name, request):
    sid = _insert_sector(db_cursor, sector_name)
    # Store on request node so subsequent steps can access it
    request.node._sector_id = sid
    request.node._sector_name = sector_name


@when(parsers.parse('I insert symbol "{ticker}" with tick_size {tick_size:f} linked to that sector'))
def insert_linked_symbol(db_cursor, ticker, tick_size, request):
    _clear_error(request)
    try:
        sid = _insert_symbol(db_cursor, ticker, tick_size, request.node._sector_id)
        request.node._symbol_id = sid
        request.node._symbol_ticker = ticker
    except pg8000.Error as e:
        db_cursor.connection.rollback()
        _store_error(request, e)


@then("the symbol insert should succeed")
def symbol_insert_succeeded(request):
    assert _get_error(request) is None, f"Expected success but got: {_get_error(request)}"


@then(parsers.parse('a join of symbols and sectors should return sector_name "{expected_sector}" for "{ticker}"'))
def check_sector_join(db_cursor, expected_sector, ticker):
    db_cursor.execute(
        "SELECT sec.sector_name FROM symbols sym "
        "JOIN sectors sec ON sym.sector_id = sec.sector_id "
        "WHERE sym.ticker_symbol = %s",
        (ticker,),
    )
    row = db_cursor.fetchone()
    assert row is not None, f"Symbol '{ticker}' not found"
    assert row[0] == expected_sector, f"Expected '{expected_sector}', got '{row[0]}'"


@when("I insert a symbol with a sector_id of 99999 that does not exist")
def insert_symbol_bad_sector(db_cursor, request):
    _clear_error(request)
    try:
        db_cursor.execute(
            "INSERT INTO symbols (ticker_symbol, full_name, sector_id, tick_size, lot_size, currency) "
            "VALUES ('INVALID', 'Invalid Corp', 99999, 0.01, 1, 'USD')"
        )
    except pg8000.Error as e:
        db_cursor.connection.rollback()
        _store_error(request, e)


@then("the insert should fail with a constraint error")
def check_constraint_error(request):
    err = _get_error(request)
    assert err is not None, "Expected a constraint error but none was raised"


# ══════════════════════════════════════════════════════════════════════════════
# Tick size validation
# ══════════════════════════════════════════════════════════════════════════════

@given(parsers.parse('symbol "{ticker}" exists with tick_size {tick_size:f}'))
def symbol_exists_with_tick(db_cursor, ticker, tick_size, request):
    sector_id = getattr(request.node, "_sector_id", None)
    if sector_id is None:
        sector_id = _insert_sector(db_cursor, "Default")
        request.node._sector_id = sector_id
    sid = _insert_symbol(db_cursor, ticker, tick_size, sector_id)
    request.node._symbol_id = sid
    request.node._symbol_ticker = ticker


@when(parsers.parse('I insert an order for "{ticker}" with price {price:f}'))
def insert_order_with_price(db_cursor, ticker, price, request):
    _clear_error(request)
    db_cursor.execute(
        "SELECT symbol_id FROM symbols WHERE ticker_symbol = %s", (ticker,)
    )
    row = db_cursor.fetchone()
    assert row is not None, f"Symbol '{ticker}' not found"
    symbol_id = row[0]
    try:
        _insert_order(db_cursor, symbol_id, "BID", price)
        request.node._order_error = None
    except pg8000.Error as e:
        db_cursor.connection.rollback()
        request.node._order_error = str(e)


@then("the order insert should fail with a tick validation error")
def check_tick_error(request):
    err = getattr(request.node, "_order_error", None)
    assert err is not None, "Expected tick validation error but insert succeeded"
    assert any(
        kw in err.lower() for kw in ("multiple", "tick", "check", "violation")
    ), f"Unexpected error message: {err}"


@then("the order insert should succeed")
def check_order_succeeded(request):
    err = getattr(request.node, "_order_error", None)
    assert err is None, f"Expected order insert success but got: {err}"


# ══════════════════════════════════════════════════════════════════════════════
# Trade integrity
# ══════════════════════════════════════════════════════════════════════════════

@given(parsers.parse('a BUY order and a SELL order exist for "{ticker}" at price {price:f}'))
def buy_and_sell_orders(db_cursor, ticker, price, request):
    db_cursor.execute(
        "SELECT symbol_id FROM symbols WHERE ticker_symbol = %s", (ticker,)
    )
    symbol_id = db_cursor.fetchone()[0]
    buy_id  = _insert_order(db_cursor, symbol_id, "BID",   price)
    sell_id = _insert_order(db_cursor, symbol_id, "OFFER", price)
    request.node._buy_order_id  = buy_id
    request.node._sell_order_id = sell_id
    request.node._symbol_id     = symbol_id


@when(parsers.parse(
    "I insert a trade with execution_price {price:f}, quantity {qty:f}, total_value {total:f}"
))
def insert_trade(db_cursor, price, qty, total, request):
    _clear_error(request)
    try:
        db_cursor.execute(
            "INSERT INTO trades "
            "(symbol_id, buy_order_id, sell_order_id, execution_price, execution_quantity, total_value) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                request.node._symbol_id,
                request.node._buy_order_id,
                request.node._sell_order_id,
                price, qty, total,
            ),
        )
    except pg8000.Error as e:
        db_cursor.connection.rollback()
        _store_error(request, e)


@then("the trade insert should fail with a check constraint error")
def check_trade_constraint_error(request):
    err = _get_error(request)
    assert err is not None, "Expected a check constraint error but insert succeeded"


@then("the trade insert should succeed")
def check_trade_succeeded(request):
    assert _get_error(request) is None, f"Expected trade success but got: {_get_error(request)}"


# ══════════════════════════════════════════════════════════════════════════════
# Watchlist UUID + uniqueness
# ══════════════════════════════════════════════════════════════════════════════

@when(parsers.parse('I insert a watchlist entry for user_id {user_id:d} watching "{ticker}"'))
def insert_watchlist(db_cursor, user_id, ticker, request):
    _clear_error(request)
    db_cursor.execute(
        "SELECT symbol_id FROM symbols WHERE ticker_symbol = %s", (ticker,)
    )
    symbol_id = db_cursor.fetchone()[0]
    try:
        db_cursor.execute(
            "INSERT INTO watchlists (user_id, symbol_id) VALUES (%s, %s) RETURNING watchlist_id",
            (user_id, symbol_id),
        )
        request.node._watchlist_id = db_cursor.fetchone()[0]
    except pg8000.Error as e:
        db_cursor.connection.rollback()
        _store_error(request, e)


@given(parsers.parse('a watchlist entry for user_id {user_id:d} watching "{ticker}" already exists'))
def watchlist_entry_exists(db_cursor, user_id, ticker, request):
    db_cursor.execute(
        "SELECT symbol_id FROM symbols WHERE ticker_symbol = %s", (ticker,)
    )
    symbol_id = db_cursor.fetchone()[0]
    db_cursor.execute(
        "INSERT INTO watchlists (user_id, symbol_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id, symbol_id) DO NOTHING",
        (user_id, symbol_id),
    )


@then("the watchlist insert should succeed")
def check_watchlist_succeeded(request):
    assert _get_error(request) is None, f"Expected success but got: {_get_error(request)}"


@then("the watchlist_id returned should be a valid UUID")
def check_uuid(request):
    wid = getattr(request.node, "_watchlist_id", None)
    assert wid is not None, "No watchlist_id returned"
    parsed = uuid.UUID(str(wid))
    assert parsed.version in (1, 4), f"Expected UUID v1 or v4, got version {parsed.version}"


@then("the watchlist insert should fail with a unique constraint error")
def check_unique_error(request):
    err = _get_error(request)
    assert err is not None, "Expected unique constraint error but insert succeeded"
    assert "unique" in err.lower() or "duplicate" in err.lower(), (
        f"Expected unique violation, got: {err}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Indexes
# ══════════════════════════════════════════════════════════════════════════════

@when(parsers.parse('I query pg_indexes for schema "{schema}"'))
def query_indexes(db_cursor, schema, request):
    db_cursor.execute(
        "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = %s ORDER BY tablename, indexname",
        (schema,),
    )
    request.node._index_result = db_cursor.fetchall()


@then(parsers.parse("the following indexes should be present:\n{index_data}"))
def check_indexes(request, index_data):
    existing = {(row[0], row[1]) for row in request.node._index_result}
    for line in index_data.splitlines():
        if "|" not in line or "tablename" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) == 2:
            table, index = parts
            assert (table, index) in existing, (
                f"❌ Missing index: '{index}' on table '{table}'. "
                f"Found: {sorted(existing)}"
            )
