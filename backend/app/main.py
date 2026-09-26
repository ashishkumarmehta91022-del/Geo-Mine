"""FastAPI application entry point.

Run from the backend/ directory with:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health, processing
from app.config import settings
from app.db import probe_database
from app.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Bounded startup connectivity check — logs status, never blocks unbounded."""
    connected, detail = await asyncio.to_thread(probe_database)
    if connected:
        logger.info("Database connected at startup")
    else:
        logger.warning("Database not available at startup (%s) — API continues; see /api/health", detail)
    yield


app = FastAPI(
    title="CMPDI AI Reporting Platform API",
    description=(
        "API foundation for SIH 2026 problem SIH26023 — AI-powered geological, "
        "mining and other reporting solution for CMPDI / CIL subsidiaries."
    ),
    version="0.2.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(processing.router)
