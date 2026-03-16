"""
Conversational AI Router
Natural language interface over the FinTech Intelligence Terminal knowledge graph.
Uses Claude to translate user questions into Cypher queries and synthesize answers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.neo4j_service import Neo4jService, get_neo4j_service
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    cypher_query: Optional[str] = None
    data_used: Optional[List[Dict]] = None
    sources: List[str] = []


# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the AI analyst powering the FinTech Intelligence Terminal —
the Bloomberg Terminal for open-source financial technology innovation, built by Nithesh Gudipuri.
You track 47,000+ FinTech repositories across 14 autonomous AI agents, and publish the monthly
GitKT FinTech OSS Index — a citable benchmark of open-source financial innovation.

You have access to a Neo4j knowledge graph containing:
- Repository nodes (fintech repositories with innovation scores)
- Developer nodes (contributors with reputation scores)
- Organization nodes (companies and institutions)
- Technology nodes (fintech technologies)
- FinancialSector nodes (payments, trading, risk, AML, lending, etc.)
- Regulation nodes (BSA, Dodd-Frank, SOX, PCI-DSS, Basel III, etc.)
- Regulator nodes (SEC, FINRA, OCC, CFTC, CFPB, FinCEN, etc.)

Key node properties for Repository:
- innovation_score (0-100): overall innovation assessment
- disruption_score (0-100): probability of becoming critical infrastructure
- startup_score (0-100): startup/VC opportunity potential
- compliance_risk_score (0-100): regulatory compliance risk
- primary_sector: payments|trading|risk_management|aml_compliance|lending|digital_identity|blockchain_defi|regtech|wealth_management|insurtech
- stars, forks, contributors_count
- fintech_domains: list of applicable domains

When a user asks a question:
1. First, generate a Cypher query to fetch relevant data
2. Then synthesize a clear, professional answer based on the results

Format your response as JSON:
{
  "cypher_query": "MATCH ...",
  "answer": "Your detailed answer...",
  "key_findings": ["Finding 1", "Finding 2", ...]
}

Be specific, cite repository names and scores, and provide actionable insights for financial professionals."""


# ── Example query translations ─────────────────────────────────────────────────

EXAMPLE_QUERIES = {
    "AML compliance": """MATCH (r:Repository)-[:SUPPORTS_COMPLIANCE]->(rl:Regulation {id: "regulation:bsa"})
WHERE r.regulatory_relevance_score >= 50
RETURN r.full_name, r.innovation_score, r.stars ORDER BY r.innovation_score DESC LIMIT 10""",

    "emerging fintech infrastructure": """MATCH (r:Repository)
WHERE r.disruption_score >= 70 AND r.primary_sector IS NOT NULL
RETURN r.full_name, r.primary_sector, r.disruption_score, r.stars
ORDER BY r.disruption_score DESC LIMIT 15""",

    "payment processing disruption": """MATCH (r:Repository)-[:RELEVANT_TO]->(fs:FinancialSector {id: "sector:payments"})
WHERE r.disruption_score >= 60
RETURN r.full_name, r.disruption_score, r.startup_score, r.stars
ORDER BY r.disruption_score DESC LIMIT 10""",

    "high startup potential": """MATCH (r:Repository)
WHERE r.startup_score >= 65
RETURN r.full_name, r.primary_sector, r.startup_score, r.fintech_domains
ORDER BY r.startup_score DESC LIMIT 15""",
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    neo4j: Neo4jService = Depends(get_neo4j_service),
):
    """Process a natural language question about the FinTech ecosystem."""
    if not settings.anthropic.api_key:
        raise HTTPException(
            status_code=503,
            detail="Conversational AI unavailable — ANTHROPIC_API_KEY not configured",
        )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic.api_key)

    # Build message history for context
    messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
    ]

    # Step 1: Ask Claude to generate Cypher query + answer plan
    try:
        response = await client.messages.create(
            model=settings.anthropic.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        raw_content = response.content[0].text if response.content else "{}"

        # Parse AI response
        parsed = _parse_ai_response(raw_content)
        cypher_query = parsed.get("cypher_query", "")

        # Step 2: Execute Cypher query
        data = []
        if cypher_query:
            try:
                data = await neo4j.run_query(cypher_query, {})
            except Exception as exc:
                logger.warning("Cypher execution error: %s\nQuery: %s", exc, cypher_query)
                # Try a safe fallback query
                data = await neo4j.run_query(
                    "MATCH (r:Repository) RETURN r.full_name, r.innovation_score ORDER BY r.innovation_score DESC LIMIT 5",
                    {}
                )

        # Step 3: If data was retrieved, synthesize a final answer
        answer = parsed.get("answer", "")
        if data and not answer:
            # Ask Claude to synthesize based on actual data
            synthesis_prompt = f"""The user asked: {messages[-1]['content']}

Query results (first 20 records):
{json.dumps(data[:20], default=str, indent=2)}

Provide a concise, professional intelligence briefing answering the user's question."""

            synthesis = await client.messages.create(
                model=settings.anthropic.model,
                max_tokens=1500,
                system="You are an expert fintech intelligence analyst. Be specific, cite repo names and scores.",
                messages=[{"role": "user", "content": synthesis_prompt}],
            )
            answer = synthesis.content[0].text if synthesis.content else raw_content

        sources = [
            r.get("full_name") or r.get("name") or ""
            for r in data[:5]
            if isinstance(r, dict)
        ]

        return ChatResponse(
            answer=answer or raw_content,
            cypher_query=cypher_query,
            data_used=data[:20],
            sources=[s for s in sources if s],
        )

    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")


@router.get("/examples")
async def get_example_queries():
    """Return example natural language queries."""
    return {
        "examples": [
            "Which open-source technologies could improve AML compliance?",
            "Show emerging fintech infrastructure projects gaining traction.",
            "Which repositories could disrupt payment processing systems?",
            "Which technologies have high startup potential in RegTech?",
            "What are the top risk management open-source tools?",
            "Which repos are relevant to Basel III capital requirements?",
            "Show me the fastest growing DeFi infrastructure projects.",
            "What developer clusters are emerging in fintech?",
        ]
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_ai_response(content: str) -> Dict[str, Any]:
    """Extract structured data from AI response, handling various formats."""
    import re

    # Try direct JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from markdown
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try bare JSON object
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Return content as answer if no JSON found
    return {"answer": content, "cypher_query": ""}
