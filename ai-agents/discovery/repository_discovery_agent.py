"""
Repository Discovery Agent (Agent 1 of 10)

Continuously scans GitHub, GitLab, and Bitbucket for fintech-related repositories.
Deduplicates, normalizes, and upserts records into the knowledge graph.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from ai_agents.base.base_agent import AgentResult, BaseAgent
from data_ingestion.repository_discovery.github_scanner import GitHubScanner, RepositoryRecord
from data_ingestion.repository_discovery.gitlab_scanner import GitLabScanner

logger = logging.getLogger(__name__)

UPSERT_REPO_CYPHER = """
MERGE (r:Repository {id: $id})
SET r += {
  source:             $source,
  full_name:          $full_name,
  url:                $url,
  description:        $description,
  topics:             $topics,
  topics_text:        $topics_text,
  language:           $language,
  stars:              $stars,
  forks:              $forks,
  watchers:           $watchers,
  open_issues:        $open_issues,
  license:            $license,
  is_fork:            $is_fork,
  is_archived:        $is_archived,
  default_branch:     $default_branch,
  readme_snippet:     $readme_snippet,
  discovery_signals:  $discovery_signals,
  created_at:         datetime($created_at),
  updated_at:         datetime($updated_at),
  pushed_at:          datetime($pushed_at),
  last_ingested_at:   datetime($now)
}
RETURN r.id AS id
"""

UPSERT_ORG_CYPHER = """
MERGE (o:Organization {name: $org_name})
ON CREATE SET o.created_at = datetime($now)
WITH o
MATCH (r:Repository {id: $repo_id})
MERGE (r)-[:MAINTAINED_BY]->(o)
"""


class RepositoryDiscoveryAgent(BaseAgent):
    """Agent 1: Discovers and ingests fintech repositories from all sources."""

    def __init__(self, github_token: str, gitlab_token: str = "", **kwargs):
        super().__init__(name="RepositoryDiscoveryAgent", **kwargs)
        self.github_token = github_token
        self.gitlab_token = gitlab_token

    async def _run(self, result: AgentResult) -> AgentResult:
        repos: List[RepositoryRecord] = []

        # ── GitHub discovery ──────────────────────────────────────────────────
        logger.info("[%s] Starting GitHub discovery", self.name)
        async with GitHubScanner(self.github_token) as gh:
            async for repo in gh.discover():
                repos.append(repo)
                if len(repos) % 500 == 0:
                    logger.info("[%s] Collected %d repos so far...", self.name, len(repos))

        # ── GitLab discovery ──────────────────────────────────────────────────
        if self.gitlab_token:
            logger.info("[%s] Starting GitLab discovery", self.name)
            async with GitLabScanner(self.gitlab_token) as gl:
                async for repo in gl.discover():
                    repos.append(repo)

        logger.info("[%s] Total repos discovered: %d", self.name, len(repos))
        result.items_processed = len(repos)

        # ── Batch upsert into Neo4j ───────────────────────────────────────────
        created = 0
        updated = 0
        errors = 0

        for batch in self._chunk(repos, 100):
            tasks = [self._upsert_repo(r) for r in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    errors += 1
                    result.errors.append(str(outcome))
                elif outcome == "created":
                    created += 1
                else:
                    updated += 1

        result.items_created = created
        result.items_updated = updated
        result.insights.append(
            f"Discovered {len(repos)} repositories: {created} new, {updated} updated, {errors} errors"
        )
        return result

    async def _upsert_repo(self, repo: RepositoryRecord) -> str:
        now = datetime.now(timezone.utc).isoformat()
        repo_id = f"{repo.source}:{repo.full_name}"

        def _iso(dt):
            return dt.isoformat() if dt else now

        # Check if exists
        existing = await self._neo4j_query(
            "MATCH (r:Repository {id: $id}) RETURN r.id", {"id": repo_id}
        )

        params = {
            "id": repo_id,
            "source": repo.source,
            "full_name": repo.full_name,
            "url": repo.url,
            "description": repo.description[:500] if repo.description else "",
            "topics": repo.topics,
            "topics_text": " ".join(repo.topics),
            "language": repo.language or "",
            "stars": repo.stars,
            "forks": repo.forks,
            "watchers": repo.watchers,
            "open_issues": repo.open_issues,
            "license": repo.license or "",
            "is_fork": repo.is_fork,
            "is_archived": repo.is_archived,
            "default_branch": repo.default_branch,
            "readme_snippet": repo.readme_snippet[:2000],
            "discovery_signals": repo.discovery_signals,
            "created_at": _iso(repo.created_at),
            "updated_at": _iso(repo.updated_at),
            "pushed_at": _iso(repo.pushed_at),
            "now": now,
        }

        await self._neo4j_write(UPSERT_REPO_CYPHER, params)

        # Link to organization if present
        parts = repo.full_name.split("/")
        if len(parts) == 2:
            await self._neo4j_write(UPSERT_ORG_CYPHER, {
                "org_name": parts[0],
                "repo_id": repo_id,
                "now": now,
            })

        return "updated" if existing else "created"
