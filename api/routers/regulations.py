from fastapi import APIRouter, Depends, Query
from typing import Optional
from api.services.neo4j_service import Neo4jService, get_neo4j_service

router = APIRouter()


@router.get("/")
async def list_regulations(neo4j: Neo4jService = Depends(get_neo4j_service)):
    return await neo4j.run_query(
        "MATCH (rl:Regulation) RETURN rl ORDER BY rl.name", {}
    )


@router.get("/regulators")
async def list_regulators(neo4j: Neo4jService = Depends(get_neo4j_service)):
    return await neo4j.run_query(
        "MATCH (reg:Regulator) RETURN reg ORDER BY reg.name", {}
    )


@router.get("/{reg_id}/repositories")
async def regulation_repositories(
    reg_id: str,
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    return await neo4j.run_query(
        "MATCH (r:Repository)-[rel]->(rl:Regulation {id: $id}) "
        "RETURN r.full_name AS repo, r.innovation_score AS score, type(rel) AS relationship "
        "ORDER BY r.innovation_score DESC LIMIT $limit",
        {"id": reg_id, "limit": limit},
    )
