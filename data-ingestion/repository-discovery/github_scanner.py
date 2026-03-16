"""
GitHub Repository Scanner
Discovers fintech-related repositories using topic search, keyword search,
NLP README classification, and developer network traversal.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Optional, Set

import httpx

logger = logging.getLogger(__name__)

# ── Fintech topic tags recognized by GitHub ──────────────────────────────────

FINTECH_TOPICS: List[str] = [
    "fintech", "payments", "banking", "trading", "cryptocurrency",
    "blockchain", "defi", "digital-banking", "open-banking", "payment-gateway",
    "fraud-detection", "aml", "kyc", "compliance", "regtech",
    "risk-management", "credit-scoring", "lending", "insurtech",
    "robo-advisor", "algorithmic-trading", "high-frequency-trading",
    "market-data", "financial-data", "swift", "iso20022", "fix-protocol",
    "custody", "clearing", "settlement", "cbdc", "stablecoin",
    "identity-verification", "open-finance", "financial-infrastructure",
    "capital-markets", "wealth-management", "neobank",
]

# ── Keyword patterns for README / description NLP scan ───────────────────────

FINTECH_KEYWORDS: List[str] = [
    "payment processing", "financial transaction", "bank account",
    "credit risk", "fraud detection", "anti-money laundering",
    "know your customer", "regulatory compliance", "financial regulation",
    "trading system", "market microstructure", "portfolio management",
    "risk analytics", "financial messaging", "ISO 20022", "SWIFT",
    "FIX protocol", "open banking", "PSD2", "Basel III",
    "Dodd-Frank", "Sarbanes-Oxley", "fintech", "regtech",
    "digital wallet", "blockchain", "smart contract",
    "decentralized finance", "custody solution", "clearinghouse",
]


@dataclass
class RepositoryRecord:
    """Normalized record for a discovered Git repository."""

    source: str                    # "github" | "gitlab" | "bitbucket"
    full_name: str                 # "owner/repo"
    url: str
    description: str = ""
    topics: List[str] = field(default_factory=list)
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    contributors_count: int = 0
    commits_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    license: Optional[str] = None
    is_fork: bool = False
    is_archived: bool = False
    default_branch: str = "main"
    readme_snippet: str = ""
    discovery_signals: List[str] = field(default_factory=list)
    raw: Dict = field(default_factory=dict)


class GitHubScanner:
    """
    Discovers fintech repositories on GitHub using three strategies:
    1. Topic-based search (exact topic tags)
    2. Full-text keyword search across repo metadata
    3. Developer network traversal (follow contributors of known repos)
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, max_repos: int = 5000):
        self.token = token
        self.max_repos = max_repos
        self._seen: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GitHubScanner":
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._client = httpx.AsyncClient(headers=headers, timeout=30)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    # ── Public entry point ────────────────────────────────────────────────────

    async def discover(self) -> AsyncIterator[RepositoryRecord]:
        """Yield deduplicated RepositoryRecord objects from all strategies."""
        count = 0

        async for repo in self._topic_search():
            if count >= self.max_repos:
                return
            yield repo
            count += 1

        async for repo in self._keyword_search():
            if count >= self.max_repos:
                return
            yield repo
            count += 1

    # ── Strategy 1: Topic Search ──────────────────────────────────────────────

    async def _topic_search(self) -> AsyncIterator[RepositoryRecord]:
        for topic in FINTECH_TOPICS:
            query = f"topic:{topic} stars:>10"
            async for repo in self._search_repos(query, signal=f"topic:{topic}"):
                yield repo
            await asyncio.sleep(1)

    # ── Strategy 2: Keyword Search ────────────────────────────────────────────

    async def _keyword_search(self) -> AsyncIterator[RepositoryRecord]:
        for keyword in FINTECH_KEYWORDS[:20]:          # top 20 to stay within rate limits
            q = f'"{keyword}" in:readme,description stars:>5'
            async for repo in self._search_repos(q, signal=f"keyword:{keyword}"):
                yield repo
            await asyncio.sleep(2)

    # ── Core Search Helper ────────────────────────────────────────────────────

    async def _search_repos(
        self, query: str, signal: str, max_pages: int = 10
    ) -> AsyncIterator[RepositoryRecord]:
        page = 1
        while page <= max_pages:
            url = f"{self.BASE_URL}/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": 100,
                "page": page,
            }
            try:
                resp = await self._request_with_backoff(url, params=params)
                await self._handle_rate_limit(resp)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.warning("GitHub search error %s for %r: %s", exc.response.status_code, query, exc)
                break
            except Exception as exc:
                logger.error("Unexpected error during search: %s", exc)
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                full_name = item.get("full_name", "")
                if full_name in self._seen:
                    continue
                self._seen.add(full_name)

                record = self._parse_item(item)
                record.discovery_signals.append(signal)
                yield record

            if len(items) < 100:
                break
            page += 1
            await asyncio.sleep(0.5)

    # ── Rate limit handler ────────────────────────────────────────────────────

    async def _handle_rate_limit(self, response: httpx.Response) -> None:
        remaining = int(response.headers.get("x-ratelimit-remaining", 10))
        if remaining < 5:
            reset_ts = int(response.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = max(0, reset_ts - int(time.time())) + 2
            logger.warning("GitHub rate limit approaching — sleeping %ds", wait)
            await asyncio.sleep(wait)

    async def _request_with_backoff(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> httpx.Response:
        """Request helper with adaptive backoff for global-scale ingestion workloads."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            resp = await self._client.get(url, params=params, headers=headers)
            status = resp.status_code

            # GitHub search at scale regularly hits 403/429 throttling windows
            if status in (403, 429):
                retry_after = resp.headers.get("retry-after")
                if retry_after:
                    wait = int(retry_after)
                else:
                    reset_ts = int(resp.headers.get("x-ratelimit-reset", int(time.time()) + 60))
                    wait = max(1, reset_ts - int(time.time()))

                # Full-jitter exponential backoff to avoid synchronized retries
                jitter = random.uniform(0, min(3, attempt))
                sleep_for = min(120, wait + jitter + (2 ** (attempt - 1)))
                logger.warning(
                    "GitHub throttled (status=%s, attempt=%s/%s). Sleeping %.1fs",
                    status,
                    attempt,
                    max_attempts,
                    sleep_for,
                )
                await asyncio.sleep(sleep_for)
                continue

            return resp

        # Return the last response to preserve caller error handling path
        return resp

    # ── Parser ────────────────────────────────────────────────────────────────

    def _parse_item(self, item: Dict) -> RepositoryRecord:
        def _dt(s: Optional[str]) -> Optional[datetime]:
            if not s:
                return None
            return datetime.fromisoformat(s.replace("Z", "+00:00"))

        license_info = item.get("license") or {}
        return RepositoryRecord(
            source="github",
            full_name=item["full_name"],
            url=item.get("html_url", ""),
            description=item.get("description") or "",
            topics=item.get("topics", []),
            language=item.get("language"),
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
            watchers=item.get("watchers_count", 0),
            open_issues=item.get("open_issues_count", 0),
            created_at=_dt(item.get("created_at")),
            updated_at=_dt(item.get("updated_at")),
            pushed_at=_dt(item.get("pushed_at")),
            license=license_info.get("spdx_id"),
            is_fork=item.get("fork", False),
            is_archived=item.get("archived", False),
            default_branch=item.get("default_branch", "main"),
            raw=item,
        )

    # ── Contributor network traversal ─────────────────────────────────────────

    async def fetch_contributors(self, full_name: str, max_contributors: int = 50) -> List[str]:
        """Return list of contributor login names for a repository."""
        url = f"{self.BASE_URL}/repos/{full_name}/contributors"
        try:
            resp = await self._request_with_backoff(url, params={"per_page": max_contributors})
            await self._handle_rate_limit(resp)
            resp.raise_for_status()
            return [c["login"] for c in resp.json() if isinstance(c, dict)]
        except Exception as exc:
            logger.debug("Could not fetch contributors for %s: %s", full_name, exc)
            return []

    async def fetch_readme(self, full_name: str) -> str:
        """Return first 2000 chars of the default README (decoded)."""
        url = f"{self.BASE_URL}/repos/{full_name}/readme"
        try:
            resp = await self._request_with_backoff(url, headers={"Accept": "application/vnd.github.raw"})
            await self._handle_rate_limit(resp)
            resp.raise_for_status()
            return resp.text[:2000]
        except Exception:
            return ""
