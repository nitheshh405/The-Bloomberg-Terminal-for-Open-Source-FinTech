"""
FastAPI Application Entry Point
FinTech Intelligence Terminal REST API
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from api.routers import repositories, technologies, regulations, graph, intelligence, search, chat, hitl_review, index_report

logger = logging.getLogger(__name__)
settings = get_settings()

# Track application start time for uptime calculation
_app_start_time: float | None = None


class HealthStatus(str, Enum):
    """Health status indicators for the application and its dependencies."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health status of a single dependency."""
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(BaseModel):
    """Comprehensive health check response model."""
    status: HealthStatus
    version: str
    uptime_seconds: float
    dependencies: dict[str, DependencyHealth] = {}


async def check_dependency_health() -> dict[str, DependencyHealth]:
    """
    Check health of application dependencies.
    
    Returns:
        Dictionary mapping dependency names to their health status.
    """
    dependencies: dict[str, DependencyHealth] = {}
    
    # Add dependency checks here as the application grows
    # Example structure for future database/cache checks:
    # 
    # try:
    #     start = time.perf_counter()
    #     await db.execute("SELECT 1")
    #     latency = (time.perf_counter() - start) * 1000
    #     dependencies["database"] = DependencyHealth(
    #         status=HealthStatus.HEALTHY,
    #         latency_ms=round(latency, 2)
    #     )
    # except Exception as e:
    #     dependencies["database"] = DependencyHealth(
    #         status=HealthStatus.UNHEALTHY,
    #         message=str(e)
    #     )
    
    return dependencies


def determine_overall_status(dependencies: dict[str, DependencyHealth]) -> HealthStatus:
    """
    Determine overall application health based on dependency statuses.
    
    Args:
        dependencies: Dictionary of dependency health checks.
        
    Returns:
        Overall health status of the application.
    """
    if not dependencies:
        return HealthStatus.HEALTHY
    
    statuses = [dep.status for dep in dependencies.values()]
    
    if any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.UNHEALTHY
    if any(s == HealthStatus.DEGRADED for s in statuses):
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    global _app_start_time
    _app_start_time = time.time()
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
    response_model=HealthCheckResponse,
    summary="Application Health Check",
    description="Returns comprehensive health status including dependency checks and uptime.",
)
async def health_check() -> HealthCheckResponse:
    """
    Perform a comprehensive health check of the application.
    
    This endpoint is designed for use by load balancers, container orchestrators,
    and monitoring systems to assess the operational status of the application.
    
    Returns:
        HealthCheckResponse with overall status, version, uptime, and dependency health.
    """
    dependencies = await check_dependency_health()
    overall_status = determine_overall_status(dependencies)
    
    uptime = time.time() - _app_start_time if _app_start_time else 0.0
    
    return HealthCheckResponse(
        status=overall_status,
        version=settings.app_version,
        uptime_seconds=round(uptime, 2),
        dependencies=dependencies,
    )


@app.get(
    "/api/v1/health/live",
    tags=["Health"],
    summary="Liveness Probe",
    description="Simple liveness check for Kubernetes probes.",
)
async def liveness_probe() -> dict[str, str]:
    """
    Simple liveness probe for container orchestration.
    
    Returns 200 if the application process is running.
    """
    return {"status": "alive"}