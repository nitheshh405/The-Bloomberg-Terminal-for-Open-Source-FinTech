"""
HITL Review Router
==================
REST endpoints for the compliance officer dashboard panel:

  GET  /api/v1/hitl/pending           — list items awaiting review
  GET  /api/v1/hitl/stats             — aggregate counts by status
  POST /api/v1/hitl/{repo_id}/approve — approve a single claim
  POST /api/v1/hitl/{repo_id}/reject  — reject a single claim
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

# HITL imports (Neo4j driver injected via dependency)
from knowledge_graph.hitl.hitl_queue import HITLQueueItem, HITLQueueManager, HITLStats
from api.auth.rbac import require_role  # RBAC guard (Fix 3)

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────────

class ReviewAction(BaseModel):
    framework_id:   str
    requirement_id: str
    reviewer:       str  # pulled from JWT in production; explicit here for dev


class ReviewResponse(BaseModel):
    success: bool
    message: str


# ── Driver dependency (lightweight — no full Neo4j service needed here) ────────

def _get_neo4j():
    """
    Returns a live Neo4j driver or None if not configured.
    Mirrors the pattern in api/services/neo4j_service.py.
    """
    try:
        from config.settings import get_settings
        import neo4j
        s = get_settings()
        return neo4j.GraphDatabase.driver(
            s.neo4j.uri,
            auth=(s.neo4j.username, s.neo4j.password),
        )
    except Exception:
        return None


def get_hitl_manager(driver=Depends(_get_neo4j)) -> Optional[HITLQueueManager]:
    if driver is None:
        return None
    return HITLQueueManager(driver)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/pending",
    response_model=List[dict],
    summary="List compliance claims awaiting human review",
)
async def get_pending_queue(
    limit: int = Query(50, ge=1, le=200),
    mgr: Optional[HITLQueueManager] = Depends(get_hitl_manager),
    # Uncomment to enforce RBAC once OIDC is wired:
    # _: str = Depends(require_role("compliance_officer")),
):
    if mgr is None:
        # Return empty list gracefully when Neo4j is not available
        return []
    items = mgr.get_pending_queue(limit=limit)
    return [vars(i) for i in items]


@router.get(
    "/stats",
    response_model=dict,
    summary="HITL queue statistics by status",
)
async def get_hitl_stats(
    mgr: Optional[HITLQueueManager] = Depends(get_hitl_manager),
):
    if mgr is None:
        return {"pending": 0, "approved": 0, "rejected": 0, "auto": 0, "total": 0}
    stats = mgr.get_stats()
    return {
        "pending":  stats.pending,
        "approved": stats.approved,
        "rejected": stats.rejected,
        "auto":     stats.auto,
        "total":    stats.total,
        "review_backlog": stats.review_backlog,
    }


@router.post(
    "/{repo_id}/approve",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a compliance claim (compliance officer action)",
)
async def approve_claim(
    repo_id: str,
    body: ReviewAction,
    mgr: Optional[HITLQueueManager] = Depends(get_hitl_manager),
    # _: str = Depends(require_role("compliance_officer")),
):
    if mgr is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    ok = mgr.approve(repo_id, body.framework_id, body.requirement_id, body.reviewer)
    if not ok:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ReviewResponse(success=True, message="Claim approved and Neo4j updated")


@router.post(
    "/{repo_id}/reject",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a compliance claim (compliance officer action)",
)
async def reject_claim(
    repo_id: str,
    body: ReviewAction,
    mgr: Optional[HITLQueueManager] = Depends(get_hitl_manager),
    # _: str = Depends(require_role("compliance_officer")),
):
    if mgr is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")
    ok = mgr.reject(repo_id, body.framework_id, body.requirement_id, body.reviewer)
    if not ok:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ReviewResponse(success=True, message="Claim rejected and flagged for re-scan")
