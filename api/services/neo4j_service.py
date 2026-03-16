"""
Neo4j Service — shared database access layer for the FastAPI application.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.graph import Node

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_driver: Optional[AsyncDriver] = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.username, settings.neo4j.password),
            max_connection_pool_size=settings.neo4j.max_connection_pool,
        )
    return _driver


class Neo4jService:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver
        self._database = settings.neo4j.database

    async def run_query(self, cypher: str, params: Dict) -> List[Dict]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params)
            return [record.data() async for record in result]

    async def run_parallel(self, *queries: Tuple[str, Dict]) -> List[List[Dict]]:
        """Run multiple queries concurrently."""
        import asyncio
        return await asyncio.gather(*(self.run_query(q, p) for q, p in queries))

    @staticmethod
    def flatten_node(node: Any) -> Dict:
        """Convert a Neo4j Node object to a plain dict, safe for Pydantic."""
        if isinstance(node, Node):
            return dict(node.items())
        return node if isinstance(node, dict) else {}


async def get_neo4j_service() -> Neo4jService:
    return Neo4jService(await get_driver())
