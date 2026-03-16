"""
Celery Ingestion Tasks
======================
Each task is idempotent, retries on GitHub rate limits, and uses
the GraphQL client (1 request per repo instead of 6).

Rate-limit error handling pattern
───────────────────────────────────
  GitHub returns HTTP 403 with header X-RateLimit-Remaining: 0.
  We read X-RateLimit-Reset (Unix epoch) and schedule a retry
  with countdown = reset_epoch - now + 5s buffer.
  Celery's self.retry() suspends the task without blocking a worker thread.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from data_ingestion.queue.celery_app import app
from data_ingestion.github.token_pool import GitHubTokenPool
from data_ingestion.github.graphql_client import GitHubGraphQLClient

logger = logging.getLogger(__name__)


# ── Shared token pool (created once per worker process) ────────────────────────

_token_pool: Optional[GitHubTokenPool] = None

def _get_pool() -> GitHubTokenPool:
    global _token_pool
    if _token_pool is None:
        _token_pool = GitHubTokenPool.from_env()
    return _token_pool


# ── Helper: run async code from sync Celery task ──────────────────────────────

def _run(coro):
    """Run a coroutine in a fresh event loop (safe inside Celery worker)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Base task class with shared retry logic ───────────────────────────────────

class IngestTask(Task):
    abstract = True
    max_retries = 10

    def on_rate_limit(self, reset_at: int) -> None:
        """Reschedule this task to run after the rate-limit window resets."""
        countdown = max(5, reset_at - int(time.time()) + 5)
        logger.warning(
            "Rate-limited. Retrying task %s in %ds", self.name, countdown
        )
        raise self.retry(countdown=countdown)


# ── Task 1: Ingest a single repository ────────────────────────────────────────

@app.task(
    bind=True,
    base=IngestTask,
    name="data_ingestion.queue.ingestion_tasks.ingest_repo",
    queue="ingestion",
    acks_late=True,
)
def ingest_repo(self: IngestTask, owner: str, name: str) -> Dict[str, Any]:
    """
    Fetch metadata for a single repo via GraphQL and write to Neo4j.
    Retries up to 10 times on rate-limit or transient errors.
    """
    try:
        pool   = _get_pool()
        client = GitHubGraphQLClient(pool)
        result = _run(client.fetch_repo(owner, name))

        if result is None:
            return {"status": "skipped", "repo": f"{owner}/{name}"}

        # Write to Neo4j (import lazily to avoid circular deps)
        _write_to_neo4j(result)

        return {"status": "ok", "repo": f"{owner}/{name}", "stars": result.get("stars")}

    except Exception as exc:
        error_str = str(exc).lower()
        # Detect GitHub rate-limit errors surfaced as exceptions
        if "rate limit" in error_str or "403" in error_str:
            reset_at = int(time.time()) + 3600   # conservative default
            self.on_rate_limit(reset_at)

        try:
            raise self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for %s/%s: %s", owner, name, exc)
            return {"status": "failed", "repo": f"{owner}/{name}", "error": str(exc)}


# ── Task 2: Full sweep — queues ingest_repo for every known stale repo ─────────

@app.task(
    name="data_ingestion.queue.ingestion_tasks.run_full_ingestion_sweep",
    queue="orchestration",
)
def run_full_ingestion_sweep() -> Dict[str, Any]:
    """
    Reads stale repos from Neo4j and fans out one ingest_repo task per repo.
    This is the weekly Monday 02:00 UTC task from celery beat.
    """
    repos = _fetch_stale_repos_from_neo4j(limit=5000)
    logger.info("Queuing ingestion for %d stale repos", len(repos))

    # Fan out — each repo becomes its own task, processed by worker pool
    job_ids = []
    for owner, name in repos:
        result = ingest_repo.apply_async(
            args=[owner, name],
            queue="ingestion",
            retry=False,      # outer orchestration task doesn't retry
        )
        job_ids.append(result.id)

    return {"queued": len(job_ids), "job_ids": job_ids[:10]}   # truncate for readability


# ── Task 3: Incremental refresh of recently active repos ──────────────────────

@app.task(
    name="data_ingestion.queue.ingestion_tasks.refresh_active_repos",
    queue="orchestration",
)
def refresh_active_repos() -> Dict[str, Any]:
    """Refresh repos that had commits in the last 7 days (high-velocity tracking)."""
    repos = _fetch_active_repos_from_neo4j(days=7, limit=500)
    logger.info("Queuing refresh for %d active repos", len(repos))
    for owner, name in repos:
        ingest_repo.apply_async(args=[owner, name], queue="ingestion", priority=5)
    return {"refreshed": len(repos)}


# ── Task 4: Rescan repos with HITL-rejected compliance claims ─────────────────

@app.task(
    name="data_ingestion.queue.ingestion_tasks.rescan_rejected_repos",
    queue="compliance",
)
def rescan_rejected_repos() -> Dict[str, Any]:
    """Re-run compliance analysis on repos whose claims were rejected by officers."""
    repos = _fetch_rejected_repos_from_neo4j(limit=100)
    logger.info("Compliance rescan for %d repos", len(repos))
    for owner, name in repos:
        ingest_repo.apply_async(args=[owner, name], queue="compliance", priority=8)
    return {"rescanned": len(repos)}


# ── Neo4j helpers (thin layer — full service in api/services/neo4j_service.py) ─

def _write_to_neo4j(repo_data: Dict[str, Any]) -> None:
    """Upsert a normalised repo dict into Neo4j."""
    try:
        from config.settings import get_settings
        import neo4j as _neo4j
        s = get_settings()
        with _neo4j.GraphDatabase.driver(
            s.neo4j.uri, auth=(s.neo4j.username, s.neo4j.password)
        ) as driver:
            with driver.session() as session:
                session.run(
                    """
                    MERGE (r:Repository {id: $id})
                    SET r += $props, r.updated_at = datetime()
                    """,
                    id=repo_data.get("id") or repo_data.get("full_name", ""),
                    props={k: v for k, v in repo_data.items()
                           if k not in ("commits_last_100", "contributors_sampled", "root_files")
                           and v is not None},
                )
    except Exception as exc:
        logger.warning("Neo4j write failed (non-fatal): %s", exc)


def _fetch_stale_repos_from_neo4j(limit: int) -> List[tuple]:
    """Return (owner, name) pairs for repos not updated in 7+ days."""
    try:
        from config.settings import get_settings
        import neo4j as _neo4j
        s = get_settings()
        with _neo4j.GraphDatabase.driver(
            s.neo4j.uri, auth=(s.neo4j.username, s.neo4j.password)
        ) as driver:
            with driver.session() as session:
                records = session.run(
                    """
                    MATCH (r:Repository)
                    WHERE r.updated_at < datetime() - duration('P7D')
                       OR r.updated_at IS NULL
                    RETURN r.full_name AS full_name
                    LIMIT $limit
                    """,
                    limit=limit,
                )
                result = []
                for rec in records:
                    full_name = rec["full_name"] or ""
                    parts = full_name.split("/", 1)
                    if len(parts) == 2:
                        result.append(tuple(parts))
                return result
    except Exception:
        return []


def _fetch_active_repos_from_neo4j(days: int, limit: int) -> List[tuple]:
    try:
        from config.settings import get_settings
        import neo4j as _neo4j
        s = get_settings()
        with _neo4j.GraphDatabase.driver(
            s.neo4j.uri, auth=(s.neo4j.username, s.neo4j.password)
        ) as driver:
            with driver.session() as session:
                records = session.run(
                    f"""
                    MATCH (r:Repository)
                    WHERE r.updated_at > datetime() - duration('P{days}D')
                    RETURN r.full_name AS full_name
                    LIMIT $limit
                    """,
                    limit=limit,
                )
                return [
                    tuple(r["full_name"].split("/", 1))
                    for r in records
                    if r["full_name"] and "/" in r["full_name"]
                ]
    except Exception:
        return []


def _fetch_rejected_repos_from_neo4j(limit: int) -> List[tuple]:
    try:
        from config.settings import get_settings
        import neo4j as _neo4j
        s = get_settings()
        with _neo4j.GraphDatabase.driver(
            s.neo4j.uri, auth=(s.neo4j.username, s.neo4j.password)
        ) as driver:
            with driver.session() as session:
                records = session.run(
                    """
                    MATCH (r:Repository)-[rel:COMPLIES_WITH]->()
                    WHERE rel.hitl_status = 'rejected'
                    RETURN DISTINCT r.full_name AS full_name
                    LIMIT $limit
                    """,
                    limit=limit,
                )
                return [
                    tuple(r["full_name"].split("/", 1))
                    for r in records
                    if r["full_name"] and "/" in r["full_name"]
                ]
    except Exception:
        return []
