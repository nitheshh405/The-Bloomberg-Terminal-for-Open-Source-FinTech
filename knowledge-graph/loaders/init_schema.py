"""
Knowledge Graph Schema Initializer
Runs the Cypher schema file against Neo4j to set up
constraints, indexes, and seed data.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from neo4j import AsyncGraphDatabase

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCHEMA_FILE = Path(__file__).parent.parent / "schema" / "schema.cypher"


async def init_schema() -> None:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j.uri,
        auth=(settings.neo4j.username, settings.neo4j.password),
    )

    schema_text = SCHEMA_FILE.read_text(encoding="utf-8")

    # Split on statement boundaries (double newlines or ;)
    statements = [
        s.strip()
        for s in schema_text.split(";")
        if s.strip() and not s.strip().startswith("//")
    ]

    logger.info("Executing %d Cypher statements...", len(statements))

    async with driver.session(database=settings.neo4j.database) as session:
        for i, stmt in enumerate(statements, 1):
            try:
                await session.run(stmt)
                logger.debug("Statement %d/%d: OK", i, len(statements))
            except Exception as exc:
                logger.warning("Statement %d failed (may be expected): %s", i, exc)

    await driver.close()
    logger.info("Schema initialization complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_schema())
