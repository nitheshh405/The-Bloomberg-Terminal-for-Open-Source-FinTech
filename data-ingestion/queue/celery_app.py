"""
Celery Application — Distributed Ingestion Queue
=================================================
Wraps all heavy ingestion work in Celery tasks so:
  • GitHub rate-limit 403s are caught and retried automatically
  • Work is spread across multiple workers (horizontal scale)
  • Each task is idempotent — safe to retry on failure

Broker / Backend
────────────────
    Redis (default, single line docker-compose entry)
    Set CELERY_BROKER_URL and CELERY_RESULT_BACKEND in .env

Quick start
───────────
    # Terminal 1 — start Redis
    docker run -p 6379:6379 redis:7-alpine

    # Terminal 2 — start worker
    celery -A data_ingestion.queue.celery_app worker --loglevel=info --concurrency=4

    # Terminal 3 — start beat scheduler (for periodic tasks)
    celery -A data_ingestion.queue.celery_app beat --loglevel=info
"""

from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "redis://localhost:6379/0")
RESULT_URL  = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

app = Celery(
    "gitkt_ingestion",
    broker=BROKER_URL,
    backend=RESULT_URL,
    include=["data_ingestion.queue.ingestion_tasks"],
)

app.conf.update(
    # Serialisation
    task_serializer        = "json",
    result_serializer      = "json",
    accept_content         = ["json"],
    # Reliability
    task_acks_late         = True,       # re-queue on worker crash
    task_reject_on_worker_lost = True,
    worker_prefetch_multiplier = 1,      # one task at a time per worker slot
    # Retry defaults (overridden per-task where needed)
    task_max_retries       = 10,
    task_default_retry_delay = 60,       # 1 minute base backoff
    # Result TTL
    result_expires         = 86_400,     # 24 hours
    # Timezone
    timezone               = "UTC",
    enable_utc             = True,
)

# ── Periodic schedule (Celery Beat) ───────────────────────────────────────────

app.conf.beat_schedule = {
    # Full ingestion sweep — Monday 02:00 UTC (off-peak)
    "weekly-full-ingestion": {
        "task":     "data_ingestion.queue.ingestion_tasks.run_full_ingestion_sweep",
        "schedule": crontab(hour=2, minute=0, day_of_week="monday"),
    },
    # Incremental update — every 6 hours for recently active repos
    "incremental-refresh": {
        "task":     "data_ingestion.queue.ingestion_tasks.refresh_active_repos",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Compliance rescan — flagged repos after HITL rejection
    "compliance-rescan": {
        "task":     "data_ingestion.queue.ingestion_tasks.rescan_rejected_repos",
        "schedule": crontab(minute=30, hour="*/12"),
    },
}
