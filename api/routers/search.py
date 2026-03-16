from fastapi import APIRouter, Depends, Query
from typing import Optional
from api.services.neo4j_service import Neo4jService, get_neo4j_service

router = APIRouter()


@router.get("/")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    node_type: Optional[str] = Query(None, description="Repository | Technology | Regulation"),
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Full-text search across repositories, technologies, and regulations."""
    if node_type == "Technology":
        cypher = (
            "CALL db.index.fulltext.queryNodes('technology_text', $q) "
            "YIELD node RETURN node LIMIT $limit"
        )
    elif node_type == "Regulation":
        cypher = (
            "CALL db.index.fulltext.queryNodes('regulation_text', $q) "
            "YIELD node RETURN node LIMIT $limit"
        )
    else:
        cypher = (
            "CALL db.index.fulltext.queryNodes('repository_text', $q) "
            "YIELD node, score RETURN node, score ORDER BY score DESC LIMIT $limit"
        )
    try:
        return await neo4j.run_query(cypher, {"q": q, "limit": limit})
    except Exception:
        # Fallback to simple CONTAINS match when full-text index not yet initialized
        return await neo4j.run_query(
            "MATCH (r:Repository) "
            "WHERE toLower(r.description) CONTAINS toLower($q) "
            "   OR toLower(r.full_name) CONTAINS toLower($q) "
            "RETURN r ORDER BY r.innovation_score DESC LIMIT $limit",
            {"q": q, "limit": limit},
        )
