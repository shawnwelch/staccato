"""Procrastinate app. The queue lives in Postgres (Neon) — transactional with
the rows it references, no Redis, and Render workers just run
`procrastinate worker`.

Queues:
  interactive — a user is watching a spinner (URL analyses from the API)
  batch       — channel classification fan-outs; throttleable via env
"""

from __future__ import annotations

import procrastinate

from staccato_backend.config import get_settings

QUEUE_INTERACTIVE = "interactive"
QUEUE_BATCH = "batch"


def _make_connector() -> procrastinate.BaseConnector:
    settings = get_settings()
    dsn = settings.procrastinate_database_url or settings.database_url
    if settings.env == "test" or not dsn.startswith("postgresql"):
        # Tests, and dev-on-SQLite where there's no Postgres to host the
        # queue: jobs run in-memory (enqueue works; run a worker inline or
        # accept that jobs don't persist across processes in this mode).
        from procrastinate import testing

        return testing.InMemoryConnector()
    # Procrastinate wants a plain psycopg DSN, not an SQLAlchemy URL.
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    return procrastinate.PsycopgConnector(conninfo=dsn)


app = procrastinate.App(connector=_make_connector(), import_paths=["staccato_backend.jobs.tasks"])
