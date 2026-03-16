"""
Repository API Router
Endpoints for browsing, filtering, and retrieving repository intelligence.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from api.services.neo4j_service import Neo4jService, get_neo4j_service

router = APIRouter()


# ── Pydantic Models ────────────────────────────────────────────────────────────

class RepositorySummary(BaseModel):
    id: str
    full_name: str
    url: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    primary_sector: Optional[str] = None
    fintech_domains: List[str] = Field(default_factory=list)
    innovation_score: Optional[float] = None
    disruption_score: Optional[float] = None
    startup_score: Optional[float] = None
    compliance_risk_score: Optional[float] = None
    source: str = "github"


class RepositoryDetail(RepositorySummary):
    readme_snippet: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    contributors_count: int = 0
    commits_count: int = 0
    license: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    git_impression_score: Optional[float] = None
    velocity_score: Optional[float] = None
    maturity_score: Optional[float] = None
    ecosystem_score: Optional[float] = None
    sector_relevance_score: Optional[float] = None
    adoption_potential: Optional[float] = None
    regulatory_relevance_score: Optional[float] = None
    auditability_score: Optional[float] = None
    detected_technologies: List[str] = Field(default_factory=list)
    compliance_capabilities: List[str] = Field(default_factory=list)


class PaginatedRepositories(BaseModel):
    items: List[RepositorySummary]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedRepositories)
async def list_repositories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sector: Optional[str] = Query(None, description="Filter by financial sector"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    min_disruption: Optional[float] = Query(None, ge=0, le=100),
    source: Optional[str] = Query(None, description="github | gitlab | bitbucket"),
    language: Optional[str] = Query(None),
    order_by: str = Query("innovation_score", description="innovation_score | stars | disruption_score | startup_score"),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """List repositories with filtering and pagination."""
    offset = (page - 1) * page_size

    filters = []
    params: dict = {"offset": offset, "limit": page_size}

    if sector:
        filters.append("r.primary_sector = $sector")
        params["sector"] = sector
    if min_score is not None:
        filters.append("r.innovation_score >= $min_score")
        params["min_score"] = min_score
    if min_disruption is not None:
        filters.append("r.disruption_score >= $min_disruption")
        params["min_disruption"] = min_disruption
    if source:
        filters.append("r.source = $source")
        params["source"] = source
    if language:
        filters.append("toLower(r.language) = toLower($language)")
        params["language"] = language

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    VALID_ORDER = {"innovation_score", "stars", "disruption_score", "startup_score", "forks"}
    order_field = order_by if order_by in VALID_ORDER else "innovation_score"

    query = f"""
        MATCH (r:Repository)
        {where_clause}
        RETURN r
        ORDER BY r.{order_field} DESC NULLS LAST
        SKIP $offset LIMIT $limit
    """

    count_query = f"""
        MATCH (r:Repository)
        {where_clause}
        RETURN count(r) AS total
    """

    records, count_records = await neo4j.run_parallel(
        (query, params), (count_query, params)
    )

    total = count_records[0]["total"] if count_records else 0
    items = [RepositorySummary(**neo4j.flatten_node(r["r"])) for r in records]

    return PaginatedRepositories(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),  # ceiling division
    )


@router.get("/{repo_id:path}", response_model=RepositoryDetail)
async def get_repository(
    repo_id: str,
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Get full details for a specific repository."""
    records = await neo4j.run_query(
        "MATCH (r:Repository {id: $id}) RETURN r",
        {"id": repo_id},
    )
    if not records:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepositoryDetail(**neo4j.flatten_node(records[0]["r"]))


@router.get("/{repo_id:path}/similar", response_model=List[RepositorySummary])
async def get_similar_repositories(
    repo_id: str,
    limit: int = Query(10, ge=1, le=50),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Find repositories with similar technology profile."""
    records = await neo4j.run_query("""
        MATCH (r:Repository {id: $id})-[:IMPLEMENTS]->(t:Technology)
        WITH r, collect(t) AS techs
        MATCH (other:Repository)-[:IMPLEMENTS]->(t2:Technology)
        WHERE t2 IN techs AND other.id <> $id
        WITH other, count(t2) AS shared_techs
        RETURN other
        ORDER BY shared_techs DESC, other.innovation_score DESC
        LIMIT $limit
    """, {"id": repo_id, "limit": limit})

    return [RepositorySummary(**neo4j.flatten_node(r["other"])) for r in records]


@router.get("/{repo_id:path}/regulations", response_model=List[dict])
async def get_repository_regulations(
    repo_id: str,
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Get regulations this repository is subject to or supports compliance for."""
    return await neo4j.run_query("""
        MATCH (r:Repository {id: $id})-[rel]->(rl:Regulation)
        RETURN rl.name AS regulation,
               rl.full_name AS full_name,
               type(rel) AS relationship_type,
               rel.risk_level AS risk_level,
               rel.capabilities AS capabilities
    """, {"id": repo_id})


@router.get("/leaderboard/disruption", response_model=List[RepositorySummary])
async def disruption_leaderboard(
    sector: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Top repositories ranked by disruption potential score."""
    where = "WHERE r.disruption_score IS NOT NULL"
    params: dict = {"limit": limit}
    if sector:
        where += " AND r.primary_sector = $sector"
        params["sector"] = sector

    return [
        RepositorySummary(**neo4j.flatten_node(r["r"]))
        for r in await neo4j.run_query(
            f"MATCH (r:Repository) {where} RETURN r ORDER BY r.disruption_score DESC LIMIT $limit",
            params,
        )
    ]
