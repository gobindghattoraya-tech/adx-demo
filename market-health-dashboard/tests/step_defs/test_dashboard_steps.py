"""
BDD Step Definitions — Good Book Certified™ Dashboard
Feature: tests/features/brs_dashboard.feature

Strategy:
  - BRS engine tests: pure unit tests, no DB or HTTP needed
  - API tests: FastAPI TestClient with dependency_overrides to inject
               a mocked AsyncSession (AsyncMock) — no live Cloud SQL required
"""
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from app.brs_engine import BRSResult, OrderRow, compute_brs, generate_intraday

FEATURE = str(Path(__file__).parent.parent / "features" / "brs_dashboard.feature")


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def balanced_rows():
    """10 BID + 10 OFFER rows, perfectly balanced, all OPEN, even price ladder."""
    tick = Decimal("0.01")
    rows = []
    for i in range(10):
        rows.append(OrderRow("BID",   Decimal(f"{10.00 - i*0.01:.2f}"), Decimal("100"), "OPEN"))
        rows.append(OrderRow("OFFER", Decimal(f"{10.01 + i*0.01:.2f}"), Decimal("100"), "OPEN"))
    return rows


@pytest.fixture
def high_brs_rows():
    """Rows designed to produce BRS >= 80."""
    return (
        [OrderRow("BID",   Decimal(f"{10.00 - i*0.01:.2f}"), Decimal("200"), "OPEN") for i in range(10)] +
        [OrderRow("OFFER", Decimal(f"{10.01 + i*0.01:.2f}"), Decimal("200"), "OPEN") for i in range(10)]
    )


@pytest.fixture
def low_brs_rows():
    """Rows designed to produce BRS < 50: imbalanced, mostly FILLED, wide spread."""
    return [
        OrderRow("BID",   Decimal("9.00"), Decimal("10000"), "FILLED"),
        OrderRow("BID",   Decimal("8.00"), Decimal("10000"), "CANCELLED"),
        OrderRow("OFFER", Decimal("15.00"), Decimal("1"),    "FILLED"),
        OrderRow("OFFER", Decimal("20.00"), Decimal("1"),    "CANCELLED"),
    ]


@pytest.fixture
def test_client():
    """TestClient with DB dependency replaced by an empty AsyncMock session."""
    from app.db import get_db
    from app.main import app

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_result.fetchone.return_value = None
    session.execute.return_value = mock_result

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_client_with_data():
    """TestClient whose DB session returns two symbols (FAB + ADCB) with order books."""
    from app.db import get_db
    from app.main import app

    def _row(ticker, name, sector, tick, side, price, qty, status):
        r = MagicMock()
        r.ticker_symbol = ticker; r.full_name = name; r.sector_name = sector
        r.tick_size = tick; r.side = side; r.price = price
        r.quantity_remaining = qty; r.order_status = status
        return r

    fab_ob = (
        [_row("FAB","First Abu Dhabi Bank P.J.S.C.","Banking", 0.01,"BID",  round(9.95-i*0.01,2),200,"OPEN") for i in range(10)] +
        [_row("FAB","First Abu Dhabi Bank P.J.S.C.","Banking", 0.01,"OFFER",round(9.96+i*0.01,2),200,"OPEN") for i in range(10)]
    )
    adcb_ob = (
        [_row("ADCB","Abu Dhabi Commercial Bank PJSC","Banking",0.01,"BID",  round(8.50-i*0.01,2),300,"OPEN")   for i in range(5)] +
        [_row("ADCB","Abu Dhabi Commercial Bank PJSC","Banking",0.01,"OFFER",round(8.60+i*0.05,2),50, "FILLED") for i in range(5)]
    )

    depth_rows = (
        [MagicMock(side="BID",   price=round(9.95-i*0.01,2), quantity_remaining=200.0) for i in range(10)] +
        [MagicMock(side="OFFER", price=round(9.96+i*0.01,2), quantity_remaining=200.0) for i in range(10)]
    )

    trade_row = MagicMock(trades_count=10, volume_aed=5000.0, value_aed=50000.0)

    ob_result    = MagicMock(); ob_result.fetchall.return_value = fab_ob + adcb_ob
    depth_result = MagicMock(); depth_result.fetchall.return_value = depth_rows
    trade_result = MagicMock(); trade_result.fetchone.return_value = trade_row

    session = AsyncMock()

    async def _exec(sql, *args, **kwargs):
        s = str(sql)
        if "LIMIT 20" in s:
            return depth_result
        if "trades" in s.lower():
            return trade_result
        return ob_result

    session.execute.side_effect = _exec

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


# ── Shared state ────────────────────────────────────────────────────────────────
class _Ctx:
    rows = []
    ticker = "FAB"
    tick_size = Decimal("0.01")
    result: BRSResult | None = None
    intraday: list | None = None
    response = None
    brs_value: int = 75
    client = None

ctx = _Ctx()


# ═══════════════════════════════════════════════════════════════════════════════
# Shared Given steps
# ═══════════════════════════════════════════════════════════════════════════════

@given("the BRS engine is available")
def given_brs_engine(): pass

@given('sample order book rows exist for ticker "FAB" with tick size 0.01')
def given_sample_rows(): pass

@given("the FastAPI test client is configured")
def given_test_client(test_client):
    ctx.client = test_client

@given("the database contains mocked symbol and order book data")
def given_mocked_data(test_client_with_data):
    ctx.client = test_client_with_data

@given('balanced order book rows for ticker "FAB"')
def given_balanced(balanced_rows):
    ctx.rows = balanced_rows
    ctx.ticker = "FAB"
    ctx.tick_size = Decimal("0.01")

@given('order book rows that produce a high BRS for ticker "FAB"')
def given_high(high_brs_rows):
    ctx.rows = high_brs_rows
    ctx.ticker = "FAB"
    ctx.tick_size = Decimal("0.01")

@given('order book rows that produce a very low BRS for ticker "FAB"')
def given_low(low_brs_rows):
    ctx.rows = low_brs_rows
    ctx.ticker = "FAB"
    ctx.tick_size = Decimal("0.01")

@given('a current BRS of 75 for ticker "FAB"')
def given_brs_75():
    ctx.brs_value = 75; ctx.ticker = "FAB"

@given('a current BRS of 80 for ticker "FAB"')
def given_brs_80():
    ctx.brs_value = 80; ctx.ticker = "FAB"


# ── When steps ──────────────────────────────────────────────────────────────────

@when("I compute the BRS result")
def when_compute():
    ctx.result = compute_brs(ctx.ticker, ctx.rows, ctx.tick_size)

@when("I generate the intraday snapshot")
def when_intraday():
    ctx.intraday = generate_intraday(ctx.ticker, ctx.brs_value)

@when('I request GET "/dashboard"')
def when_dashboard(): ctx.response = ctx.client.get("/dashboard")

@when('I request GET "/api/v1/market/summary"')
def when_summary(): ctx.response = ctx.client.get("/api/v1/market/summary")

@when('I request GET "/api/v1/symbols"')
def when_symbols(): ctx.response = ctx.client.get("/api/v1/symbols")

@when('I request GET "/api/v1/symbols/FAB/depth"')
def when_depth(): ctx.response = ctx.client.get("/api/v1/symbols/FAB/depth")


# ── Then steps ──────────────────────────────────────────────────────────────────

@then("the response status code should be 200")
def then_200(): assert ctx.response.status_code == 200, f"got {ctx.response.status_code}"

@then('the response content type should contain "text/html"')
def then_html(): assert "text/html" in ctx.response.headers.get("content-type","")

@then('the response body should contain "Good Book Certified"')
def then_gbc(): assert "Good Book Certified" in ctx.response.text

@then("the DC score should be between 0 and 100")
def then_dc(): assert 0 <= ctx.result.dc <= 100

@then("the TF score should be between 0 and 100")
def then_tf(): assert 0 <= ctx.result.tf <= 100

@then("the IR score should be between 0 and 100")
def then_ir(): assert 0 <= ctx.result.ir <= 100

@then("the PLC score should be between 0 and 100")
def then_plc(): assert 0 <= ctx.result.plc <= 100

@then("the BRS composite should be between 0 and 100")
def then_brs_range(): assert 0 <= ctx.result.brs <= 100

@then("the BRS composite should equal round of DC plus TF plus IR plus PLC divided by 4")
def then_brs_formula():
    r = ctx.result
    assert r.brs == round((r.dc + r.tf + r.ir + r.plc) / 4)

@then('the tier should be "Gold"')
def then_gold(): assert ctx.result.tier == "Gold", f"tier={ctx.result.tier} brs={ctx.result.brs}"

@then('the tier should be "Disqualified"')
def then_disq(): assert ctx.result.tier == "Disqualified", f"tier={ctx.result.tier} brs={ctx.result.brs}"

@then("the result should contain exactly 5 data points")
def then_5(): assert len(ctx.intraday) == 5

@then("the last point BRS should equal 75")
def then_last_75(): assert ctx.intraday[-1]["brs"] == 75

@then("every intraday BRS value should be between 0 and 100")
def then_intraday_range():
    for pt in ctx.intraday: assert 0 <= pt["brs"] <= 100

@then("the labels should be T-4h T-3h T-2h T-1h Now")
def then_labels():
    assert [p["label"] for p in ctx.intraday] == ["T-4h","T-3h","T-2h","T-1h","Now"]

@then('the JSON body should contain key "total_symbols"')
def then_key_total(): assert "total_symbols" in ctx.response.json()

@then('the JSON body should contain key "certified_count"')
def then_key_cert(): assert "certified_count" in ctx.response.json()

@then('the JSON body should contain key "watchlist_count"')
def then_key_watch(): assert "watchlist_count" in ctx.response.json()

@then('the JSON body should contain key "market_avg_brs"')
def then_key_avg(): assert "market_avg_brs" in ctx.response.json()

@then("the JSON body should be a list")
def then_is_list(): assert isinstance(ctx.response.json(), list)

@then("the symbols should be ordered by BRS descending")
def then_sorted():
    brs = [s["brs"] for s in ctx.response.json()]
    assert brs == sorted(brs, reverse=True)

@then("the depth rows should include both BID and OFFER sides")
def then_both_sides():
    sides = {r["side"] for r in ctx.response.json()}
    assert "BID" in sides and "OFFER" in sides


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario registrations
# ═══════════════════════════════════════════════════════════════════════════════

@scenario(FEATURE, "Dashboard route returns HTTP 200")
def test_dashboard_http_200(): pass

@scenario(FEATURE, "BRS sub-scores are each between 0 and 100")
def test_brs_subscores_range(): pass

@scenario(FEATURE, "BRS composite equals rounded average of DC TF IR PLC")
def test_brs_formula(): pass

@scenario(FEATURE, "A symbol with high BRS receives the Gold tier")
def test_gold_tier(): pass

@scenario(FEATURE, "A symbol with very low BRS is Disqualified")
def test_disqualified_tier(): pass

@scenario(FEATURE, "Intraday simulation returns exactly 5 labelled BRS points")
def test_intraday_5(): pass

@scenario(FEATURE, "Intraday labels follow the expected time series")
def test_intraday_labels(): pass

@scenario(FEATURE, "Market summary endpoint returns valid JSON structure")
def test_market_summary(): pass

@scenario(FEATURE, "Symbols list is ordered by BRS descending")
def test_symbols_sorted(): pass

@scenario(FEATURE, "Depth endpoint returns BID and OFFER price levels")
def test_depth_sides(): pass
