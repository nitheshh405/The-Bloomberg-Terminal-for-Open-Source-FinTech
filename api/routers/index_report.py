"""
FinTech Intelligence Terminal OSS Index — REST API
====================================
Endpoints for fetching, previewing, and downloading monthly index reports.

Routes
──────
  GET  /api/v1/index/latest           → current month's index (JSON)
  GET  /api/v1/index/{year}/{month}   → specific month's index (JSON)
  GET  /api/v1/index/history          → last 12 months of headline metrics
  GET  /api/v1/index/latest/markdown  → current month Markdown (text/markdown)
  POST /api/v1/index/compute          → trigger on-demand computation (admin only)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependency: Neo4j driver ───────────────────────────────────────────────────

def _get_driver():
    """Lazy import to avoid circular dependency with app startup."""
    try:
        from api.dependencies import get_neo4j_driver
        return get_neo4j_driver()
    except Exception:
        return None


# ── Pydantic response models ───────────────────────────────────────────────────

from pydantic import BaseModel, Field


class TechSurgeOut(BaseModel):
    tech_name:      str
    category:       str
    repo_count_now: int
    repo_count_30d: int
    mom_pct:        float
    surge_label:    str


class BreakoutOut(BaseModel):
    repo_id:              str
    full_name:            str
    current_score:        float
    predicted_score_90d:  float
    slope_per_week:       float
    trajectory_class:     str
    external_signal_score: float = 0.0
    innovation_signal:    float = 0.0


class AcquisitionOut(BaseModel):
    repo_id:          str
    full_name:        str
    disruption_score: float
    adoption_score:   float
    contributor_orgs: int
    rationale:        str


class FITIndexOut(BaseModel):
    period:                   str
    published_at:             str
    total_repos_tracked:      int
    innovation_velocity_30d:  float
    compliance_coverage_gap:  float
    supply_chain_risk_score:  float
    new_repos_this_month:     int
    active_contributors_30d:  int
    regulatory_gaps_detected: int
    highest_disruption_score: float
    top_supply_chain_dep:     str
    supply_chain_alert:       str
    compliance_alert:         str
    emerging_surges:              List[TechSurgeOut]   = Field(default_factory=list)
    predicted_breakout_repos:     List[BreakoutOut]    = Field(default_factory=list)
    predicted_acquisitions:       List[AcquisitionOut] = Field(default_factory=list)
    headline:                     str = ""


class HistoricalRow(BaseModel):
    period:             str
    published_at:       Optional[str]
    total_repos:        int
    velocity:           float
    compliance_gap:     float
    supply_chain_risk:  float


class ComputeResponse(BaseModel):
    period:             str
    total_repos:        int
    velocity:           float
    breakouts_found:    int
    acquisitions_found: int
    message:            str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _index_not_found(period: str):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No index found for period '{period}'. "
               f"Trigger computation via POST /api/v1/index/compute",
    )


def _load_index_from_neo4j(driver, period: str) -> Optional[Dict[str, Any]]:
    """Read a stored FITIndex node from Neo4j by period."""
    import json as _json
    _Q = """
    MATCH (idx:FITIndex {period: $period})
    RETURN idx.index_json AS json_str, idx.period AS period
    """
    try:
        with driver.session() as s:
            rec = s.run(_Q, period=period).single()
            if rec and rec["json_str"]:
                return _json.loads(rec["json_str"])
    except Exception as exc:
        logger.warning("Neo4j unavailable when loading index %s: %s", period, exc)
    return None


def _index_to_out(d: Dict[str, Any]) -> FITIndexOut:
    """Convert a raw index dict to the Pydantic output model."""
    from ai_agents.reporting.fit_index_agent import (
        FITIndex, BreakoutPrediction, AcquisitionPrediction, TechSurge
    )
    from datetime import datetime, timezone

    surges = [TechSurge(**s) for s in d.get("emerging_surges", [])]
    breakouts = [BreakoutPrediction(**b) for b in d.get("predicted_breakout_repos", [])]
    acquisitions = [AcquisitionPrediction(**a) for a in d.get("predicted_acquisitions", [])]

    idx = FITIndex(
        period                   = d["period"],
        published_at             = datetime.fromisoformat(d["published_at"]),
        total_repos_tracked      = d["total_repos_tracked"],
        innovation_velocity_30d  = d["innovation_velocity_30d"],
        compliance_coverage_gap  = d["compliance_coverage_gap"],
        supply_chain_risk_score  = d["supply_chain_risk_score"],
        new_repos_this_month     = d.get("new_repos_this_month", 0),
        active_contributors_30d  = d.get("active_contributors_30d", 0),
        regulatory_gaps_detected = d.get("regulatory_gaps_detected", 0),
        highest_disruption_score = d.get("highest_disruption_score", 0.0),
        top_supply_chain_dep     = d.get("top_supply_chain_dep", ""),
        supply_chain_alert       = d.get("supply_chain_alert", ""),
        compliance_alert         = d.get("compliance_alert", ""),
        emerging_surges          = surges,
        predicted_breakout_repos = breakouts,
        predicted_acquisitions   = acquisitions,
    )

    return FITIndexOut(
        period                   = idx.period,
        published_at             = idx.published_at.isoformat(),
        total_repos_tracked      = idx.total_repos_tracked,
        innovation_velocity_30d  = idx.innovation_velocity_30d,
        compliance_coverage_gap  = idx.compliance_coverage_gap,
        supply_chain_risk_score  = idx.supply_chain_risk_score,
        new_repos_this_month     = idx.new_repos_this_month,
        active_contributors_30d  = idx.active_contributors_30d,
        regulatory_gaps_detected = idx.regulatory_gaps_detected,
        highest_disruption_score = idx.highest_disruption_score,
        top_supply_chain_dep     = idx.top_supply_chain_dep,
        supply_chain_alert       = idx.supply_chain_alert,
        compliance_alert         = idx.compliance_alert,
        emerging_surges          = [
            TechSurgeOut(
                tech_name=s.tech_name, category=s.category,
                repo_count_now=s.repo_count_now, repo_count_30d=s.repo_count_30d,
                mom_pct=s.mom_pct, surge_label=s.surge_label,
            ) for s in surges
        ],
        predicted_breakout_repos = [
            BreakoutOut(
                repo_id=b.repo_id, full_name=b.full_name,
                current_score=b.current_score,
                predicted_score_90d=b.predicted_score_90d,
                slope_per_week=b.slope_per_week,
                trajectory_class=b.trajectory_class,
                external_signal_score=b.external_signal_score,
                innovation_signal=b.innovation_signal,
            ) for b in breakouts
        ],
        predicted_acquisitions   = [
            AcquisitionOut(
                repo_id=a.repo_id, full_name=a.full_name,
                disruption_score=a.disruption_score,
                adoption_score=a.adoption_score,
                contributor_orgs=a.contributor_orgs,
                rationale=a.rationale,
            ) for a in acquisitions
        ],
        headline = idx.headline,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/latest", response_model=FITIndexOut, summary="Get current month's index")
async def get_latest_index():
    """
    Returns the most recently computed FinTech Intelligence Terminal OSS Index.
    If the current month has not been computed yet, returns last month's.
    """
    driver = _get_driver()
    now    = datetime.now(timezone.utc)

    for period in [now.strftime("%Y-%m"), (now.replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m")]:
        data = _load_index_from_neo4j(driver, period) if driver else None
        if data:
            return _index_to_out(data)

    # Graceful stub when Neo4j is offline / not yet computed
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Index not yet computed. Run POST /api/v1/index/compute or wait for the monthly Celery task.",
    )


@router.get("/{year}/{month}", response_model=FITIndexOut, summary="Get index for a specific month")
async def get_index_by_period(year: int, month: int):
    """
    Fetch the FIT Index for a specific year/month (e.g. /2026/03).
    """
    if not (2024 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid year or month")

    period = f"{year}-{month:02d}"
    driver = _get_driver()
    data   = _load_index_from_neo4j(driver, period) if driver else None

    if not data:
        _index_not_found(period)

    return _index_to_out(data)


@router.get("/history", response_model=List[HistoricalRow], summary="Last 12 months of index summaries")
async def get_index_history(limit: int = Query(default=12, ge=1, le=60)):
    """
    Returns a time-series of headline metrics across the last N monthly editions.
    Useful for dashboard trend charts.
    """
    driver = _get_driver()
    if not driver:
        return []

    try:
        from ai_agents.reporting.fit_index_agent import FITIndexAgent
        agent   = FITIndexAgent(driver)
        records = agent.get_historical(limit=limit)
        return [
            HistoricalRow(
                period            = r["period"],
                published_at      = str(r.get("published_at", "")),
                total_repos       = int(r.get("total_repos",      0)),
                velocity          = float(r.get("velocity",       0.0)),
                compliance_gap    = float(r.get("compliance_gap", 0.0)),
                supply_chain_risk = float(r.get("supply_chain_risk", 0.0)),
            )
            for r in records
        ]
    except Exception as exc:
        logger.error("History query failed: %s", exc)
        return []


@router.get("/latest/markdown", response_class=PlainTextResponse, summary="Current month index as Markdown")
async def get_latest_index_markdown():
    """
    Returns the current month's index rendered as GitHub-flavoured Markdown.
    Ready to paste into arXiv/SSRN abstract, blog, or LinkedIn.
    """
    driver = _get_driver()
    now    = datetime.now(timezone.utc)
    period = now.strftime("%Y-%m")
    data   = _load_index_from_neo4j(driver, period) if driver else None

    if not data:
        raise HTTPException(status_code=503, detail="Index not yet computed for this period.")

    idx_out = _index_to_out(data)
    # Re-render markdown from the stored data
    from ai_agents.reporting.fit_index_agent import (
        FITIndex, TechSurge, BreakoutPrediction, AcquisitionPrediction
    )
    from ai_agents.reporting.index_publisher import render_markdown
    from datetime import datetime as _dt

    idx = FITIndex(
        period                   = data["period"],
        published_at             = _dt.fromisoformat(data["published_at"]),
        total_repos_tracked      = data["total_repos_tracked"],
        innovation_velocity_30d  = data["innovation_velocity_30d"],
        compliance_coverage_gap  = data["compliance_coverage_gap"],
        supply_chain_risk_score  = data["supply_chain_risk_score"],
        new_repos_this_month     = data.get("new_repos_this_month", 0),
        active_contributors_30d  = data.get("active_contributors_30d", 0),
        regulatory_gaps_detected = data.get("regulatory_gaps_detected", 0),
        highest_disruption_score = data.get("highest_disruption_score", 0.0),
        top_supply_chain_dep     = data.get("top_supply_chain_dep", ""),
        supply_chain_alert       = data.get("supply_chain_alert", ""),
        compliance_alert         = data.get("compliance_alert", ""),
        emerging_surges          = [TechSurge(**s) for s in data.get("emerging_surges", [])],
        predicted_breakout_repos = [BreakoutPrediction(**b) for b in data.get("predicted_breakout_repos", [])],
        predicted_acquisitions   = [AcquisitionPrediction(**a) for a in data.get("predicted_acquisitions", [])],
    )
    return render_markdown(idx)


@router.post("/compute", response_model=ComputeResponse, summary="Trigger index computation (admin)")
async def trigger_index_computation(period: Optional[str] = None):
    """
    Manually trigger index computation for the given period (default: current month).
    In production this is called automatically by the monthly Celery beat task.
    Requires admin role in production (auth middleware enforces this).
    """
    driver = _get_driver()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j driver not available — ensure NEO4J_URI is configured",
        )

    try:
        from ai_agents.reporting.fit_index_agent import FITIndexAgent
        from ai_agents.reporting.index_publisher import IndexPublisher

        agent = FITIndexAgent(driver)
        index = agent.run(period=period)

        # Also write files to disk
        publisher = IndexPublisher()
        paths     = publisher.publish(index)
        logger.info("Index %s published: %s", index.period, paths)

        return ComputeResponse(
            period             = index.period,
            total_repos        = index.total_repos_tracked,
            velocity           = index.innovation_velocity_30d,
            breakouts_found    = len(index.predicted_breakout_repos),
            acquisitions_found = len(index.predicted_acquisitions),
            message            = (
                f"FinTech Intelligence Terminal OSS Index {index.period} computed and saved. "
                f"Files: {list(paths.values())}"
            ),
        )
    except Exception as exc:
        logger.exception("Index computation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index computation failed: {exc}",
        )
