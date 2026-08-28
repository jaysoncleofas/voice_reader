"""Fixed-window rate limiting on shared Redis counters.

Synthesis is the expensive one: each call pins a CPU core for about ten seconds
on a server shared with other applications, so an unthrottled endpoint is a
denial-of-service risk against everything else on the box.

Limits fail **open**. If Redis is unreachable the request is allowed, because
locking every user out of the app is a worse outcome than briefly losing the
throttle.
"""

from dataclasses import dataclass

from app.cache import incr_window
from app.config import settings


@dataclass(frozen=True)
class Limit:
    count: int
    seconds: int

    @classmethod
    def parse(cls, spec: str) -> "Limit":
        """Parse a "count/seconds" spec, e.g. "20/3600"."""
        count, _, seconds = spec.partition("/")
        return cls(int(count), int(seconds or 60))


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    remaining: int
    limit: Limit

    @property
    def message(self) -> str:
        window = self.limit.seconds
        unit = "hour" if window >= 3600 else ("minute" if window >= 60 else "second")
        n = max(1, window // (3600 if unit == "hour" else 60 if unit == "minute" else 1))
        every = f"{n} {unit}s" if n > 1 else f"{unit}"
        return f"Rate limit reached - {self.limit.count} per {every}. Try again shortly."


def check(bucket: str, identity: str, spec: str) -> Verdict:
    """Count one hit against `bucket` for `identity` and say whether it passes."""
    limit = Limit.parse(spec)
    if not settings.rate_limit_enabled:
        return Verdict(True, limit.count, limit)

    used = incr_window(f"rl:{bucket}:{identity}", limit.seconds)
    if used is None:
        return Verdict(True, limit.count, limit)   # cache down: fail open
    return Verdict(used <= limit.count, max(0, limit.count - used), limit)


def speak(identity: str) -> Verdict:
    return check("speak", identity, settings.limit_speak)


def upload(identity: str) -> Verdict:
    return check("upload", identity, settings.limit_upload)


def auth(identity: str) -> Verdict:
    return check("auth", identity, settings.limit_auth)
