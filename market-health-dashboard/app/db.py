"""
Database module — async SQLAlchemy engine + session factory.
Reads connection details from environment variables (populated by Cloud Run / Secret Manager).
"""
import logging
import os
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

log = logging.getLogger(__name__)

_engine = None
AsyncSessionLocal = None


def _build_url() -> str:
    user = os.environ["DB_USER"]
    password = quote_plus(os.environ["DB_PASSWORD"])  # URL-encode special chars
    host = os.environ["DB_HOST"]
    name = os.environ["DB_NAME"]
    log.info("Connecting to DB at host=%s db=%s user=%s", host, name, user)
    return f"postgresql+asyncpg://{user}:{password}@{host}/{name}"


async def init_db() -> None:
    """Initialise the async engine and session factory (called once at startup)."""
    global _engine, AsyncSessionLocal
    url = _build_url()
    _engine = create_async_engine(
        url,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            "ssl": None,           # no SSL (Cloud SQL private IP)
            "server_settings": {}, # blank server settings
        },
    )
    AsyncSessionLocal = sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    log.info("DB engine initialised → %s", os.environ.get("DB_HOST"))



async def get_db():
    """FastAPI dependency — yields an async DB session per request."""
    if AsyncSessionLocal is None:
        raise RuntimeError("DB not initialised — call init_db() first.")
    async with AsyncSessionLocal() as session:
        yield session
