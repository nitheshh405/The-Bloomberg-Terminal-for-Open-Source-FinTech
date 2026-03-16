"""
FastAPI Application Entry Point
FinTech Intelligence Terminal REST API
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config.settings import get_settings
from api.routers import repositories, technologies, regulations, graph, intelligence, search, chat, hitl_review, index_report

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bloomberg Terminal for Open-Source FinTech Innovation",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(repositories.router, prefix="/api/v1/repositories", tags=["Repositories"])
app.include_router(technologies.router, prefix="/api/v1/technologies", tags=["Technologies"])
app.include_router(regulations.router, prefix="/api/v1/regulations", tags=["Regulations"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Knowledge Graph"])
app.include_router(intelligence.router, prefix="/api/v1/intelligence", tags=["Intelligence"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Conversational AI"])
app.include_router(hitl_review.router, prefix="/api/v1/hitl", tags=["HITL Compliance Review"])
app.include_router(index_report.router, prefix="/api/v1/index", tags=["FinTech Intelligence Terminal OSS Index"])


@app.get(
    "/api/v1/health",
    tags=["Health"],
    summary="Health Check",
    response_description="Returns the health status and version of the API",
)
async def health_check() -> dict[str, str]:
    """
    Perform a health check on the API.

    Returns:
        dict: A dictionary containing the health status and application version.
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "app_name": settings.app_name,
    }