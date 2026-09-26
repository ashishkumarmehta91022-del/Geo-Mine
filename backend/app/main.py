"""FastAPI application entry point.

Run from the backend/ directory with:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.config import settings
from app.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="CMPDI AI Reporting Platform API",
    description=(
        "API foundation for SIH 2026 problem SIH26023 — AI-powered geological, "
        "mining and other reporting solution for CMPDI / CIL subsidiaries."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
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
