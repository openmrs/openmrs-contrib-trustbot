"""Replaces uvicorn's built-in access log with our own, level-controlled one.

Uvicorn's `uvicorn.access` logger has `propagate = False` and its own
handler, configured by uvicorn's CLI before this app module is imported
-- so it is entirely independent of src/logging_setup.py's root-logger
setup, and LOG_LEVEL / POST /admin/log-level have no effect on it. See
openspec/changes/archive/*-add-access-logging/design.md for how this was
verified.

register_access_log_middleware() replaces it with a single log line per
request through the application's own logger: GET /health at DEBUG
(routine and frequent), everything else -- including 404s for undefined
routes -- at INFO.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from uvicorn.logging import DefaultFormatter

logger = logging.getLogger(__name__)

# Matches the compact timestamp format src/logging_setup.py's JsonFormatter
# already uses for every application log line.
_TIMESTAMP_FORMAT = "%y%m%d %H:%M:%S"


def silence_uvicorn_access_log() -> None:
    """Remove uvicorn's own access-log handler so it never logs independently.

    uvicorn.error (startup/shutdown/crash messages) is untouched -- see
    timestamp_uvicorn_error_log() for that one.
    """
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.propagate = False


def timestamp_uvicorn_error_log() -> None:
    """Add a timestamp prefix to uvicorn's own startup/shutdown/crash messages.

    uvicorn.error has no handler of its own -- it propagates to the
    "uvicorn" logger's handler, configured by uvicorn's CLI before this
    app module is imported (see silence_uvicorn_access_log()'s docstring)
    with no timestamp at all. This swaps in the same formatter class with
    a leading `%(asctime)s |`, keeping uvicorn's own message text and
    level prefix untouched.

    A no-op if uvicorn hasn't configured that handler yet -- e.g. when
    the app is only imported (every test, via TestClient) rather than
    actually served by uvicorn, "uvicorn" has no handler at all and its
    records propagate to the root logger's own (already timestamped)
    handler instead.
    """
    handlers = logging.getLogger("uvicorn").handlers
    if not handlers:
        return
    handlers[0].setFormatter(
        DefaultFormatter(
            fmt="%(asctime)s | %(levelprefix)s %(message)s",
            datefmt=_TIMESTAMP_FORMAT,
            use_colors=False,
        )
    )


def register_access_log_middleware(app: FastAPI) -> None:
    """Add one log line per request, replacing uvicorn's access log."""

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            logger.info("%s %s -> unhandled exception", request.method, request.url.path)
            raise  # never swallow the exception; FastAPI's own handling still applies

        level = logging.DEBUG if request.url.path == "/health" else logging.INFO
        logger.log(level, "%s %s -> %d", request.method, request.url.path, response.status_code)
        return response
