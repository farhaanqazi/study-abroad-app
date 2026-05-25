"""ARQ worker entrypoint.

Launch with::

    cd backend && PYTHONPATH=. venv/bin/arq app.worker.WorkerSettings

The worker drains the transactional outbox on a fixed cron cadence (see
``app.tasks.arq_settings``). It performs the email/webhook side effects that the
request path deliberately deferred. Multiple replicas may run concurrently — the
claim query uses ``FOR UPDATE SKIP LOCKED``.

``WorkerSettings`` is re-exported here so the canonical launch path is
``app.worker.WorkerSettings``.
"""

from __future__ import annotations

from app.tasks.arq_settings import WorkerSettings

__all__ = ["WorkerSettings"]
