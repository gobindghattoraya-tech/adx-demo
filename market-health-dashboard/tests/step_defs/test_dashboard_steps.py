"""
Step definitions for dashboard.feature — all 7 BDD scenarios.
Fixtures client_with_db / client_db_unavailable are now callable sync functions
(see conftest.py — each call uses asyncio.run internally).
"""
import os as _os

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = _os.path.join(_os.path.dirname(__file__), "..", "features", "dashboard.feature")


# ── Scenario bindings ─────────────────────────────────────────────────────

@scenario(FEATURE, "Frontend page loads successfully")
def test_frontend_loads(): ...

@scenario(FEATURE, "Hello World is retrieved from the database and displayed")
def test_hello_world_displayed(): ...

@scenario(FEATURE, "Health endpoint responds correctly")
def test_health_endpoint(): ...

@scenario(FEATURE, "Hello endpoint returns database value")
def test_hello_endpoint(): ...

@scenario(FEATURE, "ADX branding is correctly applied")
def test_adx_branding(): ...

@scenario(FEATURE, "Application handles database unavailability gracefully")
def test_db_unavailable(): ...

@scenario(FEATURE, "README contains deployment URLs")
def test_readme_urls(): ...


# ── Shared state ──────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return {}


@pytest.fixture
def db_mode():
    return {"value": "normal"}


# ── Given ─────────────────────────────────────────────────────────────────

@given("the Market Health Dashboard service is running")
def service_running(): pass


@given(parsers.parse('the database contains a row with value "{value}"'))
def db_has_value(value): pass


@given("the database is unavailable")
def db_is_unavailable(db_mode):
    db_mode["value"] = "unavailable"


# ── When — frontend navigation ────────────────────────────────────────────

@when(parsers.parse('a user navigates to the frontend URL "{path}"'))
def navigate_to_url(path, ctx, client_with_db):
    ctx["response"] = client_with_db(path)


# ── When — API GET ────────────────────────────────────────────────────────

@when(parsers.parse('a GET request is made to "{path}"'))
def get_request(path, ctx, db_mode, client_with_db, client_db_unavailable):
    client = client_db_unavailable if db_mode["value"] == "unavailable" else client_with_db
    ctx["response"] = client(path)


# ── When — README ─────────────────────────────────────────────────────────

@when("a developer reads the README.md file")
def read_readme(ctx, readme_content):
    ctx["readme"] = readme_content


# ── Then ──────────────────────────────────────────────────────────────────

@then(parsers.parse("the HTTP response status code is {code:d}"))
def check_status_code(ctx, code):
    resp = ctx["response"]
    assert resp.status_code == code, (
        f"Expected {code}, got {resp.status_code}\nBody: {resp.text[:300]}"
    )


@then(parsers.parse('the page contains "{text}"'))
def page_contains(ctx, text):
    assert text in ctx["response"].text, f"Expected '{text}' in page body"


@then(parsers.parse('the page displays the text "{text}"'))
def page_displays(ctx, text):
    assert text in ctx["response"].text


@then(parsers.parse('the response JSON field "{field}" equals "{value}"'))
def json_field_equals(ctx, field, value):
    data = ctx["response"].json()
    assert data.get(field) == value, f"Expected {field}={value!r}, got {data}"


@then("the page header contains the ADX brand name")
def check_adx_header(ctx):
    assert "ADX" in ctx["response"].text


@then("the response contains a meaningful error message")
def check_error_message(ctx):
    data = ctx["response"].json()
    assert "detail" in data and len(data["detail"]) > 0


@then(parsers.parse('the README contains "{text}"'))
def readme_contains(ctx, text):
    assert text in ctx["readme"], f"Expected '{text}' in README.md"
