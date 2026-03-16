"""
Knowledge Graph API Router
Endpoints for graph exploration, visualization data, and network queries.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.services.neo4j_service import Neo4jService, get_neo4j_service

router = APIRouter()


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict = {}
    size: float = 1.0
    color: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1.0
    properties: Dict = {}


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    node_count: int
    edge_count: int


# Node type → color mapping (for D3.js visualization)
NODE_COLORS = {
    "Repository": "#4f8ef7",
    "Developer": "#f7a24f",
    "Organization": "#4ff78e",
    "Technology": "#f74f4f",
    "FinancialSector": "#9b4ff7",
    "Regulation": "#f7e64f",
    "Regulator": "#4ff7e6",
    "GeographicRegion": "#f74fb0",
}


@router.get("/overview", response_model=GraphResponse)
async def graph_overview(
    sector: Optional[str] = None,
    min_score: float = Query(50.0, ge=0, le=100),
    limit: int = Query(100, ge=10, le=500),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Return a subgraph for the innovation radar visualization."""
    where = "WHERE r.innovation_score >= $min_score"
    params: dict = {"min_score": min_score, "limit": limit}
    if sector:
        where += " AND r.primary_sector = $sector"
        params["sector"] = sector

    # Fetch nodes
    repo_records = await neo4j.run_query(f"""
        MATCH (r:Repository) {where}
        RETURN r.id AS id, r.full_name AS name, r.primary_sector AS sector,
               r.innovation_score AS score, r.stars AS stars,
               r.disruption_score AS disruption
        ORDER BY r.innovation_score DESC LIMIT $limit
    """, params)

    tech_records = await neo4j.run_query(f"""
        MATCH (r:Repository)-[:IMPLEMENTS]->(t:Technology)
        {where}
        RETURN DISTINCT t.id AS id, t.name AS name, t.category AS category,
               count(r) AS repo_count
        ORDER BY repo_count DESC LIMIT 50
    """, params)

    sector_records = await neo4j.run_query("""
        MATCH (fs:FinancialSector) RETURN fs.id AS id, fs.name AS name
    """, {})

    # Build nodes
    nodes: List[GraphNode] = []
    seen_ids = set()

    for r in repo_records:
        node_id = r["id"]
        if node_id not in seen_ids:
            nodes.append(GraphNode(
                id=node_id,
                label=r["name"].split("/")[-1] if r["name"] else node_id,
                type="Repository",
                properties=r,
                size=max(1.0, min((r.get("score") or 0) / 20, 10.0)),
                color=NODE_COLORS["Repository"],
            ))
            seen_ids.add(node_id)

    for t in tech_records:
        node_id = t["id"]
        if node_id not in seen_ids:
            nodes.append(GraphNode(
                id=node_id,
                label=t["name"],
                type="Technology",
                properties=t,
                size=max(1.0, min(t.get("repo_count", 1) / 5, 8.0)),
                color=NODE_COLORS["Technology"],
            ))
            seen_ids.add(node_id)

    for s in sector_records:
        node_id = s["id"]
        if node_id not in seen_ids:
            nodes.append(GraphNode(
                id=node_id,
                label=s["name"],
                type="FinancialSector",
                properties=s,
                size=3.0,
                color=NODE_COLORS["FinancialSector"],
            ))
            seen_ids.add(node_id)

    # Fetch edges
    edge_records = await neo4j.run_query(f"""
        MATCH (r:Repository)-[rel:IMPLEMENTS]->(t:Technology)
        {where}
        RETURN r.id AS source, t.id AS target,
               "IMPLEMENTS" AS label, rel.confidence AS weight
        LIMIT 300
    """, params)

    sector_edges = await neo4j.run_query(f"""
        MATCH (r:Repository)-[rel:RELEVANT_TO]->(fs:FinancialSector)
        {where}
        RETURN r.id AS source, fs.id AS target,
               "RELEVANT_TO" AS label, rel.confidence AS weight
        LIMIT 200
    """, params)

    edges = [
        GraphEdge(
            source=e["source"],
            target=e["target"],
            label=e["label"],
            weight=e.get("weight") or 1.0,
        )
        for e in edge_records + sector_edges
        if e["source"] in seen_ids and e["target"] in seen_ids
    ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
    )


@router.get("/technology-ecosystem", response_model=GraphResponse)
async def technology_ecosystem_graph(
    technology_id: Optional[str] = None,
    depth: int = Query(2, ge=1, le=3),
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Graph centered on a technology and its connected repos/sectors."""
    if technology_id:
        records = await neo4j.run_query("""
            MATCH (t:Technology {id: $id})<-[:IMPLEMENTS]-(r:Repository)
            OPTIONAL MATCH (r)-[:RELEVANT_TO]->(fs:FinancialSector)
            RETURN t, r, fs
            LIMIT 200
        """, {"id": technology_id})
    else:
        records = await neo4j.run_query("""
            MATCH (t:Technology)<-[:IMPLEMENTS]-(r:Repository)
            WHERE r.innovation_score >= 60
            OPTIONAL MATCH (r)-[:RELEVANT_TO]->(fs:FinancialSector)
            RETURN t, r, fs LIMIT 300
        """, {})

    nodes = []
    edges = []
    seen = set()

    for rec in records:
        for key in ["t", "r", "fs"]:
            node_data = rec.get(key)
            if not node_data:
                continue
            props = dict(node_data.items()) if hasattr(node_data, "items") else {}
            node_id = props.get("id") or props.get("full_name", "")
            node_type = list(node_data.labels)[0] if hasattr(node_data, "labels") else key.upper()
            if node_id and node_id not in seen:
                nodes.append(GraphNode(
                    id=node_id,
                    label=props.get("name") or props.get("full_name", node_id),
                    type=node_type,
                    properties=props,
                    color=NODE_COLORS.get(node_type, "#aaaaaa"),
                ))
                seen.add(node_id)

    return GraphResponse(
        nodes=nodes, edges=edges,
        node_count=len(nodes), edge_count=len(edges)
    )


@router.get("/stats")
async def graph_stats(neo4j: Neo4jService = Depends(get_neo4j_service)):
    """Platform-wide statistics for the dashboard overview cards."""
    results = await neo4j.run_query("""
        CALL {
            MATCH (r:Repository) RETURN count(r) AS total_repos
        }
        CALL {
            MATCH (d:Developer) RETURN count(d) AS total_devs
        }
        CALL {
            MATCH (t:Technology) RETURN count(t) AS total_techs
        }
        CALL {
            MATCH (r:Repository) WHERE r.disruption_score >= 70
            RETURN count(r) AS high_disruption_count
        }
        CALL {
            MATCH (r:Repository) WHERE r.startup_score >= 65
            RETURN count(r) AS startup_signal_count
        }
        CALL {
            MATCH (r:Repository) RETURN avg(r.innovation_score) AS avg_innovation_score
        }
        RETURN total_repos, total_devs, total_techs,
               high_disruption_count, startup_signal_count,
               round(avg_innovation_score, 2) AS avg_innovation_score
    """, {})

    return results[0] if results else {}
