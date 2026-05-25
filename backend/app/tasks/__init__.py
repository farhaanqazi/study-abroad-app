"""Async task layer: transactional-outbox worker, senders, and ARQ wiring.

The lead-capture request path NEVER imports senders directly — it only writes an
``OutboxEvent`` in the same transaction as the business row (see
``app.services.leads``). The ARQ worker (``app.worker``) drains that outbox and
performs the real side effects defined here.
"""
