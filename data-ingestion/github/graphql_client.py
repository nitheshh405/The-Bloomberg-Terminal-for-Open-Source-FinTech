"""
GitHub GraphQL Client
======================
Replaces multiple REST calls with a single GraphQL query per repository.

REST cost  (old): ~6 HTTP calls per repo  →  exhausts 5k limit in ~833 repos
GraphQL cost (new): 1 HTTP call per repo  →  5k repos per token per hour

Each query fetches in one round-trip:
  • Repository metadata (stars, forks, license, topics, language)
  • Last 100 commits (activity velocity)
  • Top 10 contributors by commit count
  • Latest 5 releases
  • Directory listing (manifest/CI/test detection)
  • Watchers count
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from data_ingestion.github.token_pool import GitHubTokenPool

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://api.github.com/graphql"

# ── GraphQL query (one round-trip replaces ~6 REST calls) ─────────────────────

_REPO_QUERY = """
query RepoIntel($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    nameWithOwner
    description
    url
    stargazerCount
    forkCount
    watchers { totalCount }
    diskUsage
    isArchived
    primaryLanguage { name }
    licenseInfo { spdxId }
    repositoryTopics(first: 10) {
      nodes { topic { name } }
    }
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100) {
            totalCount
            edges {
              node {
                committedDate
                author { user { login } }
              }
            }
          }
        }
      }
    }
    releases(first: 5, orderBy: { field: CREATED_AT, direction: DESC }) {
      totalCount
      nodes { tagName publishedAt }
    }
    openIssues:   issues(states: OPEN)   { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    # Root directory listing for manifest/CI detection
    object(expression: "HEAD:") {
      ... on Tree {
        entries { name type }
      }
    }
  }
  rateLimit {
    remaining
    resetAt
    cost
  }
}
"""


# ── Client ────────────────────────────────────────────────────────────────────

class GitHubGraphQLClient:
    """
    Async GraphQL client backed by the token pool.
    One `fetch_repo` call costs exactly 1 GraphQL point.
    """

    def __init__(self, token_pool: GitHubTokenPool) -> None:
        self._pool = token_pool

    async def fetch_repo(self, owner: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full metadata for owner/name in a single GraphQL request.
        Returns None on 404 (repo deleted / private).
        Retries automatically on rate-limit (handled by token pool).
        """
        headers = await self._pool.next_headers()
        headers["Content-Type"] = "application/json"

        payload = {
            "query": _REPO_QUERY,
            "variables": {"owner": owner, "name": name},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                _GRAPHQL_URL, json=payload, headers=headers
            ) as resp:
                # Update rate-limit tracking from response headers
                token = headers["Authorization"].split()[-1]
                self._pool.update_from_response_headers(dict(resp.headers), token)

                if resp.status == 200:
                    data = await resp.json()
                    if "errors" in data:
                        logger.warning("GraphQL errors for %s/%s: %s", owner, name, data["errors"])
                        return None
                    return self._normalize(data["data"]["repository"])

                if resp.status in (403, 429):
                    await self._pool.handle_rate_limit_response(dict(resp.headers), token)
                    # Tail-recurse: pool will sleep then pick next token
                    return await self.fetch_repo(owner, name)

                if resp.status == 404:
                    logger.debug("Repo not found: %s/%s", owner, name)
                    return None

                logger.error("GitHub GraphQL %s for %s/%s", resp.status, owner, name)
                return None

    async def fetch_repos_batch(
        self, repos: List[tuple[str, str]]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Fetch a list of (owner, name) tuples concurrently but throttled
        to max 10 parallel requests to be a polite API citizen.
        """
        import asyncio
        sem = asyncio.Semaphore(10)

        async def _fetch(owner: str, name: str):
            async with sem:
                return await self.fetch_repo(owner, name)

        return await asyncio.gather(*[_fetch(o, n) for o, n in repos])

    # ── Normalization ──────────────────────────────────────────────────────────

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten the nested GraphQL response into the flat schema used by agents."""
        if raw is None:
            return {}

        commits = []
        branch_ref = raw.get("defaultBranchRef") or {}
        target = branch_ref.get("target") or {}
        history = target.get("history") or {}
        for edge in history.get("edges", []):
            node = edge.get("node", {})
            commits.append({
                "date":   node.get("committedDate"),
                "author": ((node.get("author") or {}).get("user") or {}).get("login"),
            })

        total_commits = history.get("totalCount", 0)

        open_issues   = (raw.get("openIssues")   or {}).get("totalCount", 0)
        closed_issues = (raw.get("closedIssues") or {}).get("totalCount", 0)

        # Deduplicate contributors from commit list
        contributors = list({
            c["author"] for c in commits if c.get("author")
        })

        root_entries = []
        obj = raw.get("object") or {}
        for entry in obj.get("entries", []):
            root_entries.append(entry.get("name", ""))

        releases      = raw.get("releases", {})
        release_nodes = releases.get("nodes", [])

        topics = [
            n["topic"]["name"]
            for n in (raw.get("repositoryTopics") or {}).get("nodes", [])
        ]

        return {
            "id":                    raw.get("id"),
            "full_name":             raw.get("nameWithOwner"),
            "url":                   raw.get("url"),
            "description":           raw.get("description"),
            "stars":                 raw.get("stargazerCount", 0),
            "forks":                 raw.get("forkCount", 0),
            "watchers":              (raw.get("watchers") or {}).get("totalCount", 0),
            "is_archived":           raw.get("isArchived", False),
            "language":              (raw.get("primaryLanguage") or {}).get("name"),
            "license":               (raw.get("licenseInfo") or {}).get("spdxId"),
            "topics":                topics,
            "open_issues":           open_issues,
            "closed_issues":         closed_issues,
            "commits_last_100":      commits,
            "commits_total_count":   total_commits,
            "contributors_sampled":  contributors,
            "release_count":         releases.get("totalCount", 0),
            "latest_release_tag":    release_nodes[0].get("tagName") if release_nodes else None,
            "latest_release_date":   release_nodes[0].get("publishedAt") if release_nodes else None,
            "root_files":            root_entries,
            # Convenience flags derived from root directory listing
            "has_tests":  any("test" in f.lower() for f in root_entries),
            "has_ci":     any(f in (".github", ".travis.yml", "Jenkinsfile") for f in root_entries),
            "has_docs":   any(f in ("docs", "doc", "documentation") for f in root_entries),
            "manifest_file": next(
                (f for f in root_entries
                 if f in ("requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml")),
                None,
            ),
        }
