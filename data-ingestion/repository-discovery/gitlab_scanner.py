"""
GitLab Repository Scanner
Discovers fintech repositories on GitLab using topic and keyword search.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import AsyncIterator, Dict, List, Optional, Set

import httpx

from .github_scanner import FINTECH_TOPICS, RepositoryRecord

logger = logging.getLogger(__name__)


class GitLabScanner:
    """Scans GitLab for fintech repositories via its REST API."""

    BASE_URL = "https://gitlab.com/api/v4"

    def __init__(self, token: str, max_repos: int = 2000):
        self.token = token
        self.max_repos = max_repos
        self._seen: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GitLabScanner":
        self._client = httpx.AsyncClient(
            headers={"PRIVATE-TOKEN": self.token},
            timeout=30,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def discover(self) -> AsyncIterator[RepositoryRecord]:
        count = 0
        for topic in FINTECH_TOPICS[:15]:
            if count >= self.max_repos:
                return
            async for repo in self._search_by_topic(topic):
                if count >= self.max_repos:
                    return
                yield repo
                count += 1
            await asyncio.sleep(1)

    async def _search_by_topic(self, topic: str) -> AsyncIterator[RepositoryRecord]:
        page = 1
        while page <= 5:
            url = f"{self.BASE_URL}/projects"
            params = {
                "topic": topic,
                "order_by": "star_count",
                "sort": "desc",
                "per_page": 100,
                "page": page,
                "with_statistics": True,
                "min_access_level": 0,
            }
            try:
                resp = await self._request_with_backoff(url, params=params)
                resp.raise_for_status()
                projects = resp.json()
            except Exception as exc:
                logger.warning("GitLab search error for topic %s: %s", topic, exc)
                break

            if not projects:
                break

            for proj in projects:
                key = f"gitlab/{proj.get('path_with_namespace', '')}"
                if key in self._seen:
                    continue
                self._seen.add(key)
                yield self._parse(proj, topic)

            if len(projects) < 100:
                break
            page += 1
            await asyncio.sleep(0.5)


    async def _request_with_backoff(self, url: str, params: Optional[Dict] = None) -> httpx.Response:
        """GitLab request helper with adaptive backoff for API throttling windows."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            resp = await self._client.get(url, params=params)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                jitter = random.uniform(0, min(2, attempt))
                wait = min(120, retry_after + jitter + (2 ** (attempt - 1)))
                logger.warning(
                    "GitLab throttled (attempt=%s/%s). Sleeping %.1fs",
                    attempt,
                    max_attempts,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            return resp

        return resp

    def _parse(self, proj: Dict, discovery_topic: str) -> RepositoryRecord:
        from datetime import datetime
        def _dt(s):
            if not s:
                return None
            return datetime.fromisoformat(s.replace("Z", "+00:00"))

        ns = proj.get("namespace", {})
        return RepositoryRecord(
            source="gitlab",
            full_name=proj.get("path_with_namespace", ""),
            url=proj.get("web_url", ""),
            description=proj.get("description") or "",
            topics=proj.get("topics", []),
            language=proj.get("repository_languages", {}).get("primary"),
            stars=proj.get("star_count", 0),
            forks=proj.get("forks_count", 0),
            watchers=proj.get("star_count", 0),
            open_issues=proj.get("open_issues_count", 0),
            created_at=_dt(proj.get("created_at")),
            updated_at=_dt(proj.get("last_activity_at")),
            pushed_at=_dt(proj.get("last_activity_at")),
            license=proj.get("license", {}).get("key") if proj.get("license") else None,
            is_fork=(proj.get("forked_from_project") is not None),
            is_archived=proj.get("archived", False),
            default_branch=proj.get("default_branch", "main"),
            discovery_signals=[f"gitlab:topic:{discovery_topic}"],
            raw=proj,
        )
