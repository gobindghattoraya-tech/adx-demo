"""
Route handlers — Single Responsibility Principle.
Each handler has one job and one job only.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import HealthResponse, HelloResponse

log = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """Serve the ADX-branded frontend page with 'Hello World' from the DB."""
    try:
        result = await db.execute(text("SELECT text FROM messages LIMIT 1"))
        message = result.scalar_one_or_none() or "Hello World"
    except Exception as exc:
        log.warning("DB read failed on index: %s", exc)
        message = "Hello World"
    return templates.TemplateResponse(
        request, "index.html", {"message": message}
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    """Liveness check — returns 200 when the service is up."""
    return HealthResponse(status="ok")


@router.get("/hello", response_model=HelloResponse, tags=["data"])
async def hello(db: AsyncSession = Depends(get_db)) -> HelloResponse:
    """Return 'Hello World' sourced from the PostgreSQL messages table."""
    try:
        result = await db.execute(text("SELECT text FROM messages LIMIT 1"))
        message = result.scalar_one_or_none()
        if message is None:
            raise HTTPException(status_code=404, detail="No message found in database")
        return HelloResponse(message=message)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("DB error on /hello: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        )


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request) -> HTMLResponse:
    """Serve the Good Book Certified™ dashboard shell.
    All data is loaded client-side via fetch() calls to /api/v1/* endpoints.
    """
    return templates.TemplateResponse(request, "dashboard.html", {})
