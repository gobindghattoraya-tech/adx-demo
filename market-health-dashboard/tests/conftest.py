"""
pytest configuration and shared fixtures for Market Health Dashboard tests.
Uses function-scoped asyncio.run() to avoid event_loop sharing issues.
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── Env bootstrap (before app import) ────────────────────────────────────
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "test_db")

from app.main import app  # noqa: E402
from app.db import get_db  # noqa: E402


# ── Mock session helpers ──────────────────────────────────────────────────

def _make_mock_session(message: str | None = "Hello World") -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = message
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _make_unavailable_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=Exception("Connection refused"))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── Sync HTTP helper ──────────────────────────────────────────────────────

def _sync_get(override_fn, path: str) -> object:
    """
    Applies dependency override, makes GET request, clears override.
    Runs entirely in a fresh event loop per call to avoid contamination.
    """
    app.dependency_overrides[get_db] = override_fn

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path)

    try:
        return asyncio.run(_do())
    finally:
        app.dependency_overrides.clear()


# ── Public test fixtures ──────────────────────────────────────────────────

@pytest.fixture
def client_with_db():
    """Returns a callable: client_with_db(path) → httpx.Response using mock DB."""
    mock_session = _make_mock_session("Hello World")

    async def override():
        yield mock_session

    def _get(path):
        return _sync_get(override, path)

    return _get


@pytest.fixture
def client_db_unavailable():
    """Returns a callable: client_db_unavailable(path) → httpx.Response (DB raises)."""
    mock_session = _make_unavailable_session()

    async def override():
        yield mock_session

    def _get(path):
        return _sync_get(override, path)

    return _get


@pytest.fixture
def readme_content() -> str:
    readme_path = os.path.join(os.path.dirname(__file__), "..", "README.md")
    with open(readme_path, encoding="utf-8") as f:
        return f.read()
