"""Redis-backed cache and counters.

Everything here degrades to a no-op when Redis is unreachable: a cache miss is
survivable, and taking the whole app down because a cache is down would be a
worse failure than the one it prevents. Callers always have a database path.
"""

import json
import logging
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_warned = False


def client() -> redis.Redis | None:
    """A shared client, or None when caching is switched off."""
    global _client
    if not settings.cache_enabled:
        return None
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url,
            socket_timeout=0.25,          # never let a slow cache stall a request
            socket_connect_timeout=0.25,
            decode_responses=True,
        )
    return _client


def _degrade(exc: Exception) -> None:
    """Log the first failure only; a dead cache should not flood the log."""
    global _warned
    if not _warned:
        logger.warning("Cache unavailable, continuing without it: %s", exc)
        _warned = True


def get_json(key: str) -> Any | None:
    conn = client()
    if conn is None:
        return None
    try:
        raw = conn.get(key)
    except Exception as exc:  # noqa: BLE001 - any Redis fault degrades to a miss
        _degrade(exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    conn = client()
    if conn is None:
        return
    try:
        conn.setex(key, ttl or settings.cache_ttl, json.dumps(value))
    except Exception as exc:  # noqa: BLE001
        _degrade(exc)


def delete(*keys: str) -> None:
    conn = client()
    if conn is None or not keys:
        return
    try:
        conn.delete(*keys)
    except Exception as exc:  # noqa: BLE001
        _degrade(exc)


def incr_window(key: str, window: int) -> int | None:
    """Increment a fixed-window counter, returning its new value.

    None means the counter could not be read, which callers treat as "allow":
    a broken cache must not lock people out of the app.
    """
    conn = client()
    if conn is None:
        return None
    try:
        pipe = conn.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)   # only the first hit sets the TTL
        return pipe.execute()[0]
    except Exception as exc:  # noqa: BLE001
        _degrade(exc)
        return None


def healthy() -> bool:
    conn = client()
    if conn is None:
        return False
    try:
        return bool(conn.ping())
    except Exception:  # noqa: BLE001
        return False
