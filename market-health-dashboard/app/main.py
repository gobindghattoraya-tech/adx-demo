"""
Market Health Dashboard — FastAPI Application Factory
Lifespan: initialises async DB engine on startup.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import router
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB pool on startup, dispose on shutdown."""
    await init_db()
    yield


app = FastAPI(
    title="Market Health Dashboard",
    description="ADX Platform — 3-tier proof-of-concept (FastAPI + Cloud SQL + Cloud Run)",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)
