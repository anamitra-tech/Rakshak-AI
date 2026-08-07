"""
Redis-backed sliding-window rate limiting for api/server.py.

api/server.py is a plain stdlib http.server.BaseHTTPRequestHandler (see its
own module docstring: "runs with ZERO external [web framework]
dependencies"), so slowapi -- which webhook/app.py uses directly, since it's
FastAPI/Starlette -- can't attach to it (slowapi's key funcs and middleware
are Starlette-Request-shaped). This module wraps the exact same underlying
library slowapi itself is built on (`limits`), using the same moving-window
(sliding-window) strategy, just called directly instead of through a
Starlette-specific decorator layer. One library, one strategy, two call
sites -- not two different rate-limiting implementations.

Storage is Redis (Upstash free tier), configured via the REDIS_URL env var,
and it is the *same* Redis instance webhook/app.py's slowapi Limiter points
at -- see webhook/app.py's Limiter construction. That's the point: both
deployed processes now hit one shared counter per identity instead of two
independent per-process ones. This makes no functional difference at
today's scale (one instance per service -- a single process's own
MemoryStorage was already correctly enforcing its limits), but it's the
architecture that's actually correct once either service scales past one
instance, which per-process memory never could be regardless of how well it
worked today. REDIS_URL is required, not optional-with-a-memory-fallback:
a silent fallback would mean the two services could quietly stop sharing a
counter without anything failing loudly to say so.
"""
import os

from dotenv import load_dotenv
from limits import parse
from limits.storage import RedisStorage
from limits.strategies import MovingWindowRateLimiter

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

_REDIS_URL = os.getenv("REDIS_URL")
if not _REDIS_URL:
    raise RuntimeError(
        "REDIS_URL is not set. api/server.py's rate limiter requires a "
        "shared Redis instance (Upstash free tier) -- the same one "
        "webhook/app.py's slowapi Limiter uses -- so limits are enforced "
        "consistently across both processes. Set REDIS_URL in .env."
    )

_storage = RedisStorage(_REDIS_URL)
_limiter = MovingWindowRateLimiter(_storage)
_parsed_cache: dict[str, object] = {}


def _item(rate: str):
    item = _parsed_cache.get(rate)
    if item is None:
        item = parse(rate)
        _parsed_cache[rate] = item
    return item


def allow(rate: str, *identifiers: str) -> bool:
    """True if this hit is within [rate] (e.g. "30/minute") for the given
    [identifiers] (e.g. endpoint path + caller identity); False if the
    caller should get a 429. Records the hit either way -- matching
    `limits`' own hit()-also-consumes semantics -- so a caller must not
    call this speculatively without following through on the request."""
    return _limiter.hit(_item(rate), *identifiers)
