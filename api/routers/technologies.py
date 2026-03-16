from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from api.services.neo4j_service import Neo4jService, get_neo4j_service

router = APIRouter()


@router.get("/")
async def list_technologies(
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    where = "WHERE t.id IS NOT NULL"
    params: dict = {"limit": limit}
    if category:
        where += " AND t.category = $category"
        params["category"] = category
    return await neo4j.run_query(
        f"MATCH (t:Technology) {where} "
        "OPTIONAL MATCH (t)<-[:IMPLEMENTS]-(r:Repository) "
        "RETURN t, count(r) AS repo_count ORDER BY repo_count DESC LIMIT $limit",
        params,
    )


@router.get("/{tech_id}")
async def get_technology(tech_id: str, neo4j: Neo4jService = Depends(get_neo4j_service)):
    from fastapi import HTTPException
    records = await neo4j.run_query("MATCH (t:Technology {id: $id}) RETURN t", {"id": tech_id})
    if not records:
        raise HTTPException(status_code=404, detail="Technology not found")
    return records[0]
