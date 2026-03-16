"""
GitKT FinTech OSS Index — Monthly Celery Task
===============================================
Runs on the 1st of every month at 06:00 UTC.

  compute_monthly_index   — aggregate all agent outputs → GitKTIndex
  publish_index_to_disk   — write .tex, .md, .json files

Beat schedule (add to celery_app.py beat_schedule):
    "monthly-gitkt-index": {
        "task":     "data_ingestion.queue.index_tasks.compute_monthly_index",
        "schedule": crontab(day_of_month=1, hour=6, minute=0),
    }
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _get_neo4j_driver():
    from neo4j import GraphDatabase
    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


# ── Celery task ────────────────────────────────────────────────────────────────

try:
    from data_ingestion.queue.celery_app import celery_app
    from celery.schedules import crontab

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.index_tasks.compute_monthly_index",
        max_retries=3,
        default_retry_delay=300,   # 5-minute retry on failure
    )
    def compute_monthly_index(self, period: Optional[str] = None) -> dict:
        """
        Monthly Celery task: compute + save + publish the GitKT FinTech OSS Index.

        Triggered automatically on the 1st of every month at 06:00 UTC.
        Can also be triggered manually:
            from data_ingestion.queue.index_tasks import compute_monthly_index
            compute_monthly_index.apply_async()

        Args:
            period: "YYYY-MM" override — defaults to current month.

        Returns:
            dict with period, total_repos, velocity, breakouts, acquisitions.
        """
        now    = datetime.now(timezone.utc)
        period = period or now.strftime("%Y-%m")
        logger.info("GitKT Index task started for period=%s", period)

        driver = None
        try:
            driver = _get_neo4j_driver()

            from ai_agents.reporting.gitkt_index_agent import GitKTIndexAgent
            from ai_agents.reporting.index_publisher import IndexPublisher

            # Compute
            agent = GitKTIndexAgent(driver)
            index = agent.run(period=period)

            # Publish to disk
            output_dir = os.getenv("INDEX_OUTPUT_DIR", "automation/index-reports")
            publisher  = IndexPublisher(output_dir=output_dir)
            paths      = publisher.publish(index)

            logger.info(
                "GitKT Index %s complete | repos=%d | velocity=%+.1f%% | breakouts=%d | acquisitions=%d",
                index.period,
                index.total_repos_tracked,
                index.innovation_velocity_30d,
                len(index.predicted_breakout_repos),
                len(index.predicted_acquisitions),
            )
            logger.info("Published to: %s", list(paths.values()))

            return {
                "period":          index.period,
                "total_repos":     index.total_repos_tracked,
                "velocity":        index.innovation_velocity_30d,
                "breakouts":       len(index.predicted_breakout_repos),
                "acquisitions":    len(index.predicted_acquisitions),
                "files":           paths,
                "headline":        index.headline,
            }

        except Exception as exc:
            logger.error("GitKT Index computation failed: %s", exc)
            raise self.retry(exc=exc)

        finally:
            if driver:
                driver.close()

    # ── Register in beat schedule ──────────────────────────────────────────────

    # Patch into the existing beat schedule (defined in celery_app.py)
    if hasattr(celery_app, "conf") and hasattr(celery_app.conf, "beat_schedule"):
        celery_app.conf.beat_schedule["monthly-gitkt-index"] = {
            "task":     "data_ingestion.queue.index_tasks.compute_monthly_index",
            "schedule": crontab(day_of_month="1", hour="6", minute="0"),
            "kwargs":   {},
        }

except ImportError:
    # Celery not installed — define a plain function fallback for testing / CLI use
    def compute_monthly_index(period: Optional[str] = None) -> dict:  # type: ignore[misc]
        """Plain-function fallback when Celery is not installed."""
        now    = datetime.now(timezone.utc)
        period = period or now.strftime("%Y-%m")
        driver = _get_neo4j_driver()

        try:
            from ai_agents.reporting.gitkt_index_agent import GitKTIndexAgent
            from ai_agents.reporting.index_publisher import IndexPublisher

            agent = GitKTIndexAgent(driver)
            index = agent.run(period=period)

            publisher = IndexPublisher()
            paths     = publisher.publish(index)

            return {
                "period":       index.period,
                "total_repos":  index.total_repos_tracked,
                "velocity":     index.innovation_velocity_30d,
                "breakouts":    len(index.predicted_breakout_repos),
                "acquisitions": len(index.predicted_acquisitions),
                "files":        paths,
            }
        finally:
            driver.close()
