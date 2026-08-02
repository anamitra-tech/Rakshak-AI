"""
In-memory sliding-window rate limiting for api/server.py.

api/server.py is a plain stdlib http.server.BaseHTTPRequestHandler (see its
own module docstring: "runs with ZERO external [web framework]
dependencies"), so slowapi -- which webhook/app.py uses directly, since it's
FastAPI/Starlette -- can't attach to it (slowapi's key funcs and middleware
are Starlette-Request-shaped). This module wraps the exact same underlying
library slowapi itself is built on (`limits`), using the same moving-window
(sliding-window) strategy and the same in-memory storage, just called
directly instead of through a Starlette-specific decorator layer. One
library, one strategy, two call sites -- not two different rate-limiting
implementations.
"""
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

_storage = MemoryStorage()
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
