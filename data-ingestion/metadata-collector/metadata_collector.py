"""
Metadata Collector
Enriches Repository nodes with deep metadata that the discovery scanner
doesn't collect: commit history, contributor stats, release history,
CI/CD signals, documentation presence, dependency file detection, and
language composition.

Designed to run after RepositoryDiscoveryAgent — it takes repos already
in Neo4j and enriches them with data that requires additional API calls.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITLAB_API = "https://gitlab.com/api/v4"

# Files whose presence signals specific capabilities
MANIFEST_FILES = [
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile",
    "package.json", "go.mod", "pom.xml", "build.gradle", "Cargo.toml", "Gemfile",
]

CI_FILES = [
    ".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml",
    "Jenkinsfile", ".travis.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml",
]

DOC_FILES = [
    "docs/", "doc/", "documentation/", "mkdocs.yml", ".readthedocs.yaml",
    "sphinx/", "docusaurus.config.js",
]

TEST_PATTERNS = [
    "tests/", "test/", "spec/", "__tests__/", "pytest.ini", "jest.config.js",
    "cypress.config.js", "test_", "_test.go",
]

SDK_PATTERNS = [
    "sdk/", "client/", "clients/", "bindings/", "lib/",
]

API_DOC_PATTERNS = [
    "openapi.yaml", "openapi.json", "swagger.yaml", "swagger.json",
    "api-docs/", "apidoc/",
]


@dataclass
class RepoMetadata:
    """Enriched metadata for one repository."""

    repo_id: str
    full_name: str
    source: str = "github"

    # Commit activity
    commits_last_year: int = 0
    commits_last_month: int = 0
    commit_frequency_weekly: float = 0.0  # avg commits/week over last year

    # Contributors
    contributors_count: int = 0
    top_contributor_logins: List[str] = field(default_factory=list)
    contributor_orgs: List[str] = field(default_factory=list)

    # Releases
    release_count: int = 0
    latest_release_tag: str = ""
    latest_release_at: Optional[str] = None
    days_since_release: int = 9999

    # Language composition (lang → % of bytes)
    language_breakdown: Dict[str, float] = field(default_factory=dict)

    # Capability signals
    manifest_file: Optional[str] = None    # primary manifest detected
    has_tests: bool = False
    has_ci: bool = False
    has_docs: bool = False
    has_api_docs: bool = False
    has_sdk: bool = False

    # Engagement
    subscriber_count: int = 0


@dataclass
class CollectionResult:
    repo_id: str
    success: bool = True
    error: str = ""


class GitHubMetadataClient:
    """Async GitHub REST client for metadata enrichment."""

    def __init__(self, token: str, session: aiohttp.ClientSession):
        self._token = token
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        url = f"{GITHUB_API}{path}"
        try:
            async with self._session.get(
                url, headers=self._headers, params=params or {}, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (404, 451):
                    return None
                if resp.status == 403:
                    logger.warning("GitHub rate limit hit for %s", path)
                    await asyncio.sleep(60)
                    return None
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("GitHub request failed for %s: %s", path, exc)
            return None

    async def _get_list(self, path: str, params: Optional[Dict] = None) -> List:
        data = await self._get(path, params)
        return data if isinstance(data, list) else []

    async def get_commit_activity(self, full_name: str) -> Dict:
        """Weekly commit activity for the last year (52 weeks)."""
        data = await self._get(f"/repos/{full_name}/stats/commit_activity")
        if not isinstance(data, list):
            return {"commits_last_year": 0, "commits_last_month": 0, "frequency_weekly": 0.0}
        weekly_totals = [week.get("total", 0) for week in data]
        total = sum(weekly_totals)
        last_4_weeks = sum(weekly_totals[-4:]) if len(weekly_totals) >= 4 else sum(weekly_totals)
        avg_weekly = total / max(len(weekly_totals), 1)
        return {
            "commits_last_year": total,
            "commits_last_month": last_4_weeks,
            "frequency_weekly": round(avg_weekly, 2),
        }

    async def get_contributors(self, full_name: str, limit: int = 30) -> List[Dict]:
        """Top contributors with login and org affiliation."""
        data = await self._get_list(
            f"/repos/{full_name}/contributors",
            {"per_page": limit, "anon": "false"},
        )
        return [
            {"login": c.get("login", ""), "contributions": c.get("contributions", 0)}
            for c in data[:limit]
            if c.get("type") == "User"
        ]

    async def get_releases(self, full_name: str) -> Dict:
        """Release count and latest release info."""
        data = await self._get_list(
            f"/repos/{full_name}/releases", {"per_page": 100}
        )
        if not data:
            return {"release_count": 0, "latest_tag": "", "latest_at": None, "days_since": 9999}
        count = len(data)
        latest = data[0]
        latest_at = latest.get("published_at") or latest.get("created_at")
        days_since = 9999
        if latest_at:
            try:
                dt = datetime.fromisoformat(latest_at.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - dt).days
            except (ValueError, TypeError):
                pass
        return {
            "release_count": count,
            "latest_tag": latest.get("tag_name", ""),
            "latest_at": latest_at,
            "days_since": days_since,
        }

    async def get_languages(self, full_name: str) -> Dict[str, float]:
        """Language composition as percentage breakdown."""
        data = await self._get(f"/repos/{full_name}/languages")
        if not isinstance(data, dict) or not data:
            return {}
        total_bytes = sum(data.values())
        return {lang: round(bytes_ / total_bytes * 100, 1) for lang, bytes_ in data.items()}

    async def get_contents_list(self, full_name: str, path: str = "") -> List[str]:
        """List of item names at a repository path."""
        data = await self._get_list(f"/repos/{full_name}/contents/{path}")
        return [item.get("name", "") for item in data if isinstance(item, dict)]

    async def detect_capabilities(self, full_name: str) -> Dict:
        """Detect presence of tests, CI, docs, SDK, API docs from root contents."""
        root_items = await self.get_contents_list(full_name)
        root_set = {item.lower() for item in root_items}

        # Detect manifest
        manifest = None
        for mf in MANIFEST_FILES:
            if mf.lower() in root_set:
                manifest = mf
                break

        # Detect CI
        has_ci = any(
            ci.split("/")[0].lower() in root_set or ci.lower() in root_set
            for ci in CI_FILES
        )

        # Detect docs
        has_docs = any(
            doc.rstrip("/").lower() in root_set
            for doc in DOC_FILES
        )

        # Detect tests
        has_tests = any(
            t.rstrip("/").lower() in root_set
            for t in TEST_PATTERNS
        )

        # Detect SDK
        has_sdk = any(
            sdk.rstrip("/").lower() in root_set
            for sdk in SDK_PATTERNS
        )

        # Detect API docs
        has_api_docs = any(
            api.rstrip("/").lower() in root_set
            for api in API_DOC_PATTERNS
        )

        return {
            "manifest_file": manifest,
            "has_tests": has_tests,
            "has_ci": has_ci,
            "has_docs": has_docs,
            "has_sdk": has_sdk,
            "has_api_docs": has_api_docs,
        }

    async def get_subscribers(self, full_name: str) -> int:
        data = await self._get(f"/repos/{full_name}")
        return (data or {}).get("subscribers_count", 0)


class MetadataCollector:
    """
    Collects deep metadata for repositories already in Neo4j
    and writes enriched properties back.

    Usage:
        async with MetadataCollector(github_token, neo4j_uri, ...) as collector:
            result = await collector.run()
    """

    def __init__(
        self,
        github_token: str,
        neo4j_uri: str,
        neo4j_auth: tuple[str, str],
        neo4j_database: str = "fintech",
        batch_size: int = 20,
        staleness_days: int = 7,
    ):
        self._github_token = github_token
        self._neo4j_uri = neo4j_uri
        self._neo4j_auth = neo4j_auth
        self._neo4j_database = neo4j_database
        self._batch_size = batch_size
        self._staleness_days = staleness_days
        self._session: Optional[aiohttp.ClientSession] = None
        self._driver = None

    async def __aenter__(self):
        from neo4j import AsyncGraphDatabase
        self._driver = AsyncGraphDatabase.driver(self._neo4j_uri, auth=self._neo4j_auth)
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
        if self._driver:
            await self._driver.close()

    async def _neo4j_query(self, cypher: str, params: Dict = None) -> List[Dict]:
        async with self._driver.session(database=self._neo4j_database) as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def _neo4j_write(self, cypher: str, params: Dict = None) -> None:
        async with self._driver.session(database=self._neo4j_database) as session:
            await session.run(cypher, params or {})

    async def run(self) -> Dict:
        """Collect metadata for all stale repositories."""
        repos = await self._fetch_stale_repos()
        logger.info("[MetadataCollector] Enriching %d repositories", len(repos))

        processed = 0
        errors = 0
        gh_client = GitHubMetadataClient(self._github_token, self._session)

        for batch in self._chunk(repos, self._batch_size):
            tasks = [self._enrich_repo(repo, gh_client) for repo in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    logger.warning("Metadata collection error: %s", outcome)
                    errors += 1
                elif isinstance(outcome, CollectionResult):
                    if outcome.success:
                        processed += 1
                    else:
                        errors += 1

            # Gentle rate-limit pause between batches
            await asyncio.sleep(1)

        return {"processed": processed, "errors": errors, "total": len(repos)}

    async def _fetch_stale_repos(self) -> List[Dict]:
        return await self._neo4j_query(f"""
            MATCH (r:Repository)
            WHERE r.source = 'github'
              AND (
                r.metadata_collected_at IS NULL
                OR r.metadata_collected_at < datetime() - duration({{days: {self._staleness_days}}})
              )
            RETURN r.id AS id,
                   r.full_name AS full_name,
                   r.source AS source
            ORDER BY r.stars DESC
            LIMIT 5000
        """)

    async def _enrich_repo(
        self, repo: Dict, gh_client: GitHubMetadataClient
    ) -> CollectionResult:
        repo_id = repo["id"]
        full_name = repo.get("full_name", "")

        if not full_name or "/" not in full_name:
            return CollectionResult(repo_id=repo_id, success=False,
                                    error="invalid full_name")

        try:
            # Parallel fetch of all metadata
            commit_activity, contributors, releases, languages, capabilities, subscribers = (
                await asyncio.gather(
                    gh_client.get_commit_activity(full_name),
                    gh_client.get_contributors(full_name),
                    gh_client.get_releases(full_name),
                    gh_client.get_languages(full_name),
                    gh_client.detect_capabilities(full_name),
                    gh_client.get_subscribers(full_name),
                    return_exceptions=True,
                )
            )

            # Safely extract values even if some calls errored
            def safe(v, default):
                return v if not isinstance(v, Exception) else default

            commit_activity = safe(commit_activity, {})
            contributors = safe(contributors, [])
            releases = safe(releases, {})
            languages = safe(languages, {})
            capabilities = safe(capabilities, {})
            subscribers = safe(subscribers, 0)

            contributor_logins = [c["login"] for c in contributors[:10]]

            now = datetime.now(timezone.utc).isoformat()
            await self._neo4j_write("""
                MATCH (r:Repository {id: $id})
                SET r.commits_last_year          = $commits_last_year,
                    r.commits_last_month         = $commits_last_month,
                    r.commit_frequency_weekly    = $commit_freq,
                    r.contributors_count         = $contributor_count,
                    r.contributors_list_logins   = $contributor_logins,
                    r.release_count              = $release_count,
                    r.latest_release_tag         = $latest_tag,
                    r.latest_release_at          = $latest_at,
                    r.days_since_release         = $days_since,
                    r.language_breakdown         = $languages,
                    r.manifest_file              = $manifest_file,
                    r.has_tests                  = $has_tests,
                    r.has_ci                     = $has_ci,
                    r.has_docs                   = $has_docs,
                    r.has_sdk                    = $has_sdk,
                    r.has_api_docs               = $has_api_docs,
                    r.subscriber_count           = $subscribers,
                    r.metadata_collected_at      = datetime($now)
            """, {
                "id": repo_id,
                "commits_last_year": commit_activity.get("commits_last_year", 0),
                "commits_last_month": commit_activity.get("commits_last_month", 0),
                "commit_freq": commit_activity.get("frequency_weekly", 0.0),
                "contributor_count": len(contributors),
                "contributor_logins": contributor_logins,
                "release_count": releases.get("release_count", 0),
                "latest_tag": releases.get("latest_tag", ""),
                "latest_at": releases.get("latest_at") or now,
                "days_since": releases.get("days_since", 9999),
                "languages": list(languages.keys())[:5],
                "manifest_file": capabilities.get("manifest_file"),
                "has_tests": capabilities.get("has_tests", False),
                "has_ci": capabilities.get("has_ci", False),
                "has_docs": capabilities.get("has_docs", False),
                "has_sdk": capabilities.get("has_sdk", False),
                "has_api_docs": capabilities.get("has_api_docs", False),
                "subscribers": subscribers,
                "now": now,
            })

            return CollectionResult(repo_id=repo_id, success=True)

        except Exception as exc:
            logger.warning("[MetadataCollector] Failed %s: %s", repo_id, exc)
            return CollectionResult(repo_id=repo_id, success=False, error=str(exc))

    @staticmethod
    def _chunk(lst: list, size: int):
        for i in range(0, len(lst), size):
            yield lst[i: i + size]
