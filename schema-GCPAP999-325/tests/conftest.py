"""
conftest.py
-----------
Shared pytest fixtures for the adx_exchange schema BDD test suite.

Design principles:
 - SRP: each fixture has exactly one responsibility.
 - DRY: connection logic is centralised — no duplication across test files.
 - Test isolation: every test function gets a fresh cursor and a rolled-back
   transaction, so tests cannot pollute each other.
"""

import os
import pytest
import pg8000
from google.cloud.sql.connector import Connector, IPTypes

# ── Configuration ─────────────────────────────────────────────────────────────

INSTANCE_CONNECTION_NAME = (
    "sbx-ag-build-adx-7i0q-1:europe-west2:ag-adx-postgres"
)
DB_USER     = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME     = "adx_exchange"

# ── Session-level connector (opened once, closed when the session ends) ────────

@pytest.fixture(scope="session")
def sql_connector():
    """Lifecycle management for the Cloud SQL Connector — opened once per session."""
    conn = Connector()
    yield conn
    conn.close()


# ── Session-level connection (shared across all tests for speed) ───────────────

@pytest.fixture(scope="session")
def db_connection(sql_connector):
    """
    A single pg8000 connection to adx_exchange, shared for the full session.
    autocommit is OFF so individual tests can roll back cleanly.
    """
    conn = sql_connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        ip_type=IPTypes.PRIVATE,
    )
    conn.autocommit = False
    yield conn
    conn.close()


# ── Function-level cursor with automatic rollback (test isolation) ─────────────

@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """
    Fresh cursor for each test.  The transaction is always rolled back after
    the test completes — ensuring zero side effects between tests.
    """
    cursor = db_connection.cursor()
    yield cursor
    try:
        db_connection.rollback()
    except Exception:
        pass
    finally:
        cursor.close()
