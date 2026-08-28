"""Postgres access: a lazily-opened pool and the schema this app needs."""

import logging
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voices (
    id         TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    duration   REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS voices_user_idx ON voices (user_id, created_at);
"""

# Opened on first use so importing the app never requires a live database.
_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(settings.database_url, min_size=1, max_size=8, open=True)
    return _pool


@contextmanager
def cursor():
    """A cursor in its own transaction, committed on clean exit."""
    with pool().connection() as conn, conn.cursor() as cur:
        yield cur


def init_schema() -> None:
    """Create tables if they are missing. Safe to run on every boot."""
    with cursor() as cur:
        cur.execute(SCHEMA)
    logger.info("Database schema ready.")
