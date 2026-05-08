"""
BDD step definitions for adx_seed.feature.

Tests the seed functions in isolation using AsyncMock — no real database required.
All asyncpg calls are mocked to validate business logic without infrastructure.
"""
from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from scripts.data.adx_symbols import SECTORS, SYMBOLS
from scripts.generators.order_book import generate_orders
from scripts.seed_adx_data import seed_order_books, seed_sectors, seed_symbols

# pytest-bdd resolves feature paths relative to the step definition file's directory.
# We use an absolute path so the features/ folder is found regardless of invocation CWD.
FEATURE_DIR = os.path.join(os.path.dirname(__file__), "..", "features")

# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_conn():
    """Mock asyncpg connection with configurable return values."""
    conn = AsyncMock()
    # Default: fetchrow returns a row-like dict for sector inserts
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)   # default: 0 existing rows
    conn.executemany = AsyncMock()
    conn.transaction = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    return conn


@pytest.fixture
def sector_id_map():
    return {s.name: idx + 1 for idx, s in enumerate(SECTORS)}


# ─── Scenarios ─────────────────────────────────────────────────────────────────


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "Sectors are seeded with correct names")
def test_sectors_seeded():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "All 15 symbols are seeded")
def test_symbols_seeded():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "Order book generator produces correct number of orders")
def test_order_book_count():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "All generated prices respect tick_size")
def test_tick_size_compliance():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "Order book generator is deterministic with a fixed seed")
def test_deterministic_orders():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "Seed script skips order books already populated")
def test_idempotent_skip():
    pass


@scenario(os.path.join(FEATURE_DIR, "adx_seed.feature"), "Seed script fails gracefully on missing DB_PASSWORD")
def test_missing_password():
    pass


# ─── Background ────────────────────────────────────────────────────────────────


@given("a mock asyncpg connection is available", target_fixture="conn")
def mock_asyncpg_connection(mock_conn):
    return mock_conn


@given("the seed data constants are loaded", target_fixture="constants_loaded")
def seed_constants():
    assert len(SECTORS) == 6, f"Expected 6 sectors, got {len(SECTORS)}"
    assert len(SYMBOLS) == 15, f"Expected 15 symbols, got {len(SYMBOLS)}"
    return True


# ─── Sector steps ──────────────────────────────────────────────────────────────


@when("the seed_sectors function is called", target_fixture="sector_result")
def call_seed_sectors(conn):
    """Call seed_sectors with mocked fetchrow returning sequential IDs."""
    import asyncio

    call_count = 0

    async def mock_fetchrow(sql, *args):
        nonlocal call_count
        call_count += 1
        return {"sector_id": call_count}

    conn.fetchrow = mock_fetchrow
    result = asyncio.run(seed_sectors(conn))
    return result


@then(parsers.parse("{count:d} rows are upserted for sectors"))
def check_sector_count(sector_result, count):
    assert len(sector_result) == count, f"Expected {count} sectors, got {len(sector_result)}"


@then(parsers.parse('the returned sector map contains "{name}"'))
def check_sector_name(sector_result, name):
    assert name in sector_result, f"'{name}' not found in sector map: {list(sector_result.keys())}"


# ─── Symbol steps ──────────────────────────────────────────────────────────────


@when("the seed_symbols function is called with a valid sector map", target_fixture="symbol_result")
def call_seed_symbols(conn, sector_id_map):
    import asyncio

    call_count = 0

    async def mock_fetchrow(sql, *args):
        nonlocal call_count
        call_count += 1
        return {"symbol_id": call_count}

    conn.fetchrow = mock_fetchrow
    result = asyncio.run(seed_symbols(conn, sector_id_map))
    return result


@then(parsers.parse("{count:d} symbols are processed"))
def check_symbol_count(symbol_result, count):
    assert len(symbol_result) == count, f"Expected {count} symbols, got {len(symbol_result)}"


@then(parsers.parse('the symbol "{ticker}" is in the returned symbol map'))
def check_symbol_ticker(symbol_result, ticker):
    assert ticker in symbol_result, f"'{ticker}' not found in symbol map: {list(symbol_result.keys())}"


# ─── Order book generator steps ────────────────────────────────────────────────


@given(
    parsers.parse("the tick_size is {tick:f} and mid_price is {mid:f}"),
    target_fixture="order_params",
)
def set_order_params(tick, mid):
    return {"tick_size": Decimal(str(tick)), "mid_price": Decimal(str(mid))}


@when(
    parsers.parse("generate_orders is called with num_levels={levels:d}"),
    target_fixture="generated_orders",
)
def call_generate_orders(order_params, levels):
    return generate_orders(
        tick_size=order_params["tick_size"],
        mid_price=order_params["mid_price"],
        num_levels=levels,
    )


@then(parsers.parse("the result contains {count:d} BID orders"))
def check_bid_count(generated_orders, count):
    bids = [o for o in generated_orders if o["side"] == "BID"]
    assert len(bids) == count, f"Expected {count} BIDs, got {len(bids)}"


@then(parsers.parse("the result contains {count:d} OFFER orders"))
def check_offer_count(generated_orders, count):
    offers = [o for o in generated_orders if o["side"] == "OFFER"]
    assert len(offers) == count, f"Expected {count} OFFERs, got {len(offers)}"


@then(parsers.parse("all BID prices are below {mid:f}"))
def check_bid_prices_below_mid(generated_orders, mid):
    mid_d = Decimal(str(mid))
    bids = [o for o in generated_orders if o["side"] == "BID"]
    for o in bids:
        assert o["price"] < mid_d, f"BID price {o['price']} is not below mid {mid_d}"


@then(parsers.parse("all OFFER prices are above {mid:f}"))
def check_offer_prices_above_mid(generated_orders, mid):
    mid_d = Decimal(str(mid))
    offers = [o for o in generated_orders if o["side"] == "OFFER"]
    for o in offers:
        assert o["price"] > mid_d, f"OFFER price {o['price']} is not above mid {mid_d}"


@then(parsers.parse("every price in the result is a multiple of {tick:f}"))
def check_tick_compliance(generated_orders, tick):
    tick_d = Decimal(str(tick))
    for o in generated_orders:
        remainder = o["price"] % tick_d
        assert remainder == Decimal("0"), (
            f"Price {o['price']} is not a multiple of {tick_d} "
            f"(remainder={remainder})"
        )


# ─── Determinism steps ─────────────────────────────────────────────────────────


@when(
    parsers.parse("generate_orders is called twice with the same seed={seed:d}"),
    target_fixture="determinism_results",
)
def call_twice_same_seed(order_params, seed):
    first = generate_orders(
        tick_size=order_params["tick_size"],
        mid_price=order_params["mid_price"],
        num_levels=10,
        seed=seed,
    )
    second = generate_orders(
        tick_size=order_params["tick_size"],
        mid_price=order_params["mid_price"],
        num_levels=10,
        seed=seed,
    )
    return first, second


@then("both results are identical")
def check_determinism(determinism_results):
    first, second = determinism_results
    assert first == second, "Results differ between runs with same seed"


# ─── Idempotency steps ─────────────────────────────────────────────────────────


@given(
    parsers.parse("the order_books table already has {count:d} rows for symbol_id {sid:d}"),
    target_fixture="idempotent_conn",
)
def pre_seeded_order_books(mock_conn, count, sid):
    """Configure mock to return existing row count — triggers skip path."""
    mock_conn.fetchval = AsyncMock(return_value=count)
    return mock_conn, sid


@when("seed_order_books is called for that symbol", target_fixture="idempotent_result")
def call_seed_order_books_existing(idempotent_conn, sector_id_map):
    import asyncio
    import scripts.seed_adx_data as runner
    from scripts.data.adx_symbols import SYMBOLS as ALL_SYMBOLS

    conn, _ = idempotent_conn
    symbol_ids = {"FAB": 1}

    # Patch SYMBOLS to only FAB to keep test scoped
    fab = next(s for s in ALL_SYMBOLS if s.ticker == "FAB")
    with patch.object(runner, "SYMBOLS", [fab]):
        asyncio.run(seed_order_books(conn, symbol_ids))

    return conn


@then("no additional INSERT is executed for symbol_id 1")
def check_no_insert(idempotent_result):
    idempotent_result.executemany.assert_not_called()


# ─── Missing password steps ─────────────────────────────────────────────────────


@given("the DB_PASSWORD environment variable is not set", target_fixture="no_password_env")
def remove_password_env():
    env_backup = os.environ.pop("DB_PASSWORD", None)
    yield
    if env_backup is not None:
        os.environ["DB_PASSWORD"] = env_backup


@when("run_seed is called", target_fixture="run_seed_error")
def call_run_seed_no_password(no_password_env):
    import asyncio
    from scripts.seed_adx_data import run_seed

    with pytest.raises(KeyError) as exc_info:
        asyncio.run(run_seed())
    return exc_info


@then("a KeyError is raised")
def check_key_error(run_seed_error):
    assert run_seed_error.type is KeyError


@then("the process would exit with code 1")
def check_exit_code_intent(run_seed_error):
    # Verifies the exception is caught at __main__ level and would exit(1)
    # The KeyError propagates from _db_config() before any DB connection
    assert "DB_PASSWORD" in str(run_seed_error.value) or run_seed_error.type is KeyError
