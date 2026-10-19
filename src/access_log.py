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

logger = logging.getLogger(__name__)


def silence_uvicorn_access_log() -> None:
    """Remove uvicorn's own access-log handler so it never logs independently.

    uvicorn.error (startup/shutdown/crash messages) is untouched.
    """
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.propagate = False


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
