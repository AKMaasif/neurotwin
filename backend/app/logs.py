"""Request logging that cannot leak health data or credentials.

Only the method, a path with ids masked, the status and the duration are logged. Bodies, query strings and
headers are never logged.
"""
from __future__ import annotations

import logging
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("neurotwin.http")

_NUMERIC = re.compile(r"/[0-9]+(?=/|$)")
_PERSON = re.compile(r"(?<=/participants/)[^/]+")
_IMAGING_RUN = re.compile(r"(?<=/native/runs/)[^/]+")


def mask_path(path: str) -> str:
    """Hide record ids and person ids. Run uvicorn with --no-access-log: its own log prints raw paths."""
    return _NUMERIC.sub("/:id", _PERSON.sub(":person", _IMAGING_RUN.sub(":run", path)))


class SafeRequestLog(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        log.info("%s %s %s %.0fms", request.method, mask_path(request.url.path), response.status_code,
                 (time.perf_counter() - start) * 1000)
        return response
