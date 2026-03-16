"""
Base Agent class for the FinTech Intelligence Terminal.
All specialized agents extend this class and share:
- Structured logging
- Neo4j connection via shared driver
- Elasticsearch access
- Anthropic AI client for reasoning tasks
- Lifecycle hooks (setup / teardown / run)
- Metrics collection
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from elasticsearch import AsyncElasticsearch
import anthropic

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardized output from any agent run."""

    agent_name: str
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"          # "running" | "success" | "partial" | "failed"
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    errors: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def finish(self, status: str = "success") -> "AgentResult":
        self.completed_at = datetime.now(timezone.utc)
        self.status = status
        return self


class BaseAgent(ABC):
    """
    Abstract base class for all platform agents.

    Subclasses must implement:
        async def _run(self) -> AgentResult
    """

    def __init__(
        self,
        name: str,
        neo4j_uri: str,
        neo4j_auth: tuple[str, str],
        neo4j_database: str = "fintech",
        es_hosts: Optional[List[str]] = None,
        anthropic_api_key: str = "",
    ):
        self.name = name
        self._neo4j_uri = neo4j_uri
        self._neo4j_auth = neo4j_auth
        self._neo4j_database = neo4j_database
        self._es_hosts = es_hosts or ["http://localhost:9200"]
        self._anthropic_api_key = anthropic_api_key

        self._driver: Optional[AsyncDriver] = None
        self._es: Optional[AsyncElasticsearch] = None
        self._ai: Optional[anthropic.AsyncAnthropic] = None

        self._run_count = 0
        self._total_items_processed = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """Initialize connections. Called before the first run."""
        self._driver = AsyncGraphDatabase.driver(
            self._neo4j_uri, auth=self._neo4j_auth
        )
        self._es = AsyncElasticsearch(self._es_hosts)
        if self._anthropic_api_key:
            self._ai = anthropic.AsyncAnthropic(api_key=self._anthropic_api_key)
        logger.info("[%s] Agent initialized", self.name)

    async def teardown(self) -> None:
        """Close connections. Called after the last run."""
        if self._driver:
            await self._driver.close()
        if self._es:
            await self._es.close()
        logger.info("[%s] Agent shut down", self.name)

    async def run(self) -> AgentResult:
        """Public entry point. Wraps _run with timing and error handling."""
        import uuid
        run_id = str(uuid.uuid4())[:8]
        result = AgentResult(
            agent_name=self.name,
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self._run_count += 1
        logger.info("[%s] Starting run #%d (id=%s)", self.name, self._run_count, run_id)

        try:
            result = await self._run(result)
            if result.status == "running":
                result.finish("success")
            self._total_items_processed += result.items_processed
            logger.info(
                "[%s] Run #%d completed in %.1fs — processed=%d created=%d updated=%d",
                self.name, self._run_count,
                result.duration_seconds or 0,
                result.items_processed,
                result.items_created,
                result.items_updated,
            )
        except Exception as exc:
            result.errors.append(str(exc))
            result.finish("failed")
            logger.exception("[%s] Run #%d failed: %s", self.name, self._run_count, exc)

        return result

    @abstractmethod
    async def _run(self, result: AgentResult) -> AgentResult:
        """Core agent logic. Must be implemented by subclasses."""

    # ── Neo4j helpers ─────────────────────────────────────────────────────────

    async def _neo4j_query(
        self, cypher: str, params: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a Cypher query and return list of record dicts."""
        async with self._driver.session(database=self._neo4j_database) as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def _neo4j_write(self, cypher: str, params: Optional[Dict] = None) -> None:
        """Execute a write Cypher statement."""
        async with self._driver.session(database=self._neo4j_database) as session:
            await session.run(cypher, params or {})

    # ── Elasticsearch helpers ────────────────────────────────────────────────

    async def _es_index(self, index: str, doc_id: str, body: Dict) -> None:
        await self._es.index(index=index, id=doc_id, document=body)

    async def _es_search(self, index: str, query: Dict) -> List[Dict]:
        resp = await self._es.search(index=index, body=query)
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    # ── AI helpers ────────────────────────────────────────────────────────────

    async def _ai_classify(self, text: str, system_prompt: str) -> str:
        """Ask Claude to classify or analyze text. Returns assistant response."""
        if not self._ai:
            return ""
        message = await self._ai.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        return message.content[0].text if message.content else ""

    # ── Utility ───────────────────────────────────────────────────────────────

    def _chunk(self, lst: list, size: int):
        """Yield successive chunks from lst."""
        for i in range(0, len(lst), size):
            yield lst[i : i + size]
