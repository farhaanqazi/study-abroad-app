"""ARQ worker configuration for the transactional-outbox drain.

Scheduling choice
-----------------
The outbox is drained by a **cron job** that fires every 10 seconds rather than
by per-event enqueued jobs. Rationale:

* The producer (LeadCaptureService) writes only a DB row in its transaction — it
  must NOT also touch Redis to enqueue a job (that would reintroduce the
  dual-write / commit-then-enqueue hazard the outbox exists to eliminate).
* A periodic drain is self-healing: rescheduled retries (``available_at`` in the
  future) and any rows written while the worker was down are picked up on the
  next tick with no extra bookkeeping.
* ``FOR UPDATE SKIP LOCKED`` in the claim query makes the drain safe to run from
  multiple worker replicas concurrently.

``drain_outbox`` is also registered as a normal function, so an operator (or a
test) can trigger an immediate drain via ``redis.enqueue_job("drain_outbox")``.

Redis connection is derived from ``settings.redis_url`` via
``RedisSettings.from_dsn`` — never hardcoded localhost.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.observability import bind_correlation_id, configure_logging, get_logger
from app.tasks.outbox_processor import drain_outbox

logger = get_logger(__name__)

# Drain cadence. Low latency for fresh leads without hammering Postgres.
DRAIN_INTERVAL_SECONDS = 10


def redis_settings() -> RedisSettings:
    """Build ARQ RedisSettings from the configured ``REDIS_URL`` DSN."""
    return RedisSettings.from_dsn(get_settings().redis_url)


async def drain_outbox_job(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ task wrapper around :func:`drain_outbox`.

    ARQ supplies a per-run ``job_id`` in ``ctx``; we bind it as the correlation
    id so every log line in this drain pass is traceable to the job.
    """
    bind_correlation_id(str(ctx.get("job_id") or ctx.get("job_try") or ""))
    return await drain_outbox()


async def _on_startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings())
    logger.info("worker_startup", interval_seconds=DRAIN_INTERVAL_SECONDS)


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_shutdown")


class WorkerSettings:
    """ARQ worker entrypoint config. Run with ``arq app.worker.WorkerSettings``."""

    functions = [drain_outbox_job]
    cron_jobs = [
        cron(
            drain_outbox_job,
            second=set(range(0, 60, DRAIN_INTERVAL_SECONDS)),
            run_at_startup=True,
            unique=True,
        ),
    ]
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    # Bound concurrency: each job is short and IO-bound; the drain itself batches.
    max_jobs = 10
    # arq's ``get_kwargs`` reads class attributes from ``__dict__`` directly, so
    # ``redis_settings`` must be a concrete RedisSettings value (not a method).
    # Built from REDIS_URL at import time — no hardcoded localhost.
    redis_settings = redis_settings()
