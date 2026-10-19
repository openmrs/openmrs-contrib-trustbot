# Design

## Context

The service is run via `uvicorn src.main:app --host 0.0.0.0 --port 8080`
(the `Dockerfile`'s `CMD`). Uvicorn's CLI configures its own logging
(`uvicorn`, `uvicorn.error`, `uvicorn.access` loggers, each with
`propagate: False` and its own handler) before our app module is
imported. Our own `src/logging_setup.py` only ever touches the root
logger, so it has never interacted with `uvicorn.access` at all — that's
why `LOG_LEVEL`/`POST /admin/log-level` have no effect on access-log
noise today.

Verified empirically (not assumed): because `Config.load()` imports the
app module *after* uvicorn's own `dictConfig` has already run, code in
`src/main.py` executes after `uvicorn.access` already exists as a
configured logger — and Python's `logging` module lets us mutate an
already-configured logger's handlers/propagation after the fact. A
throwaway test app that clears `uvicorn.access`'s handlers and sets
`propagate = False` at module level, run for real with
`uvicorn app:app`, produced zero access-log lines for a served request,
while uvicorn's startup banner (from the separate `uvicorn.error`
logger) was unaffected. No `Dockerfile`/`CMD` change is needed.

See proposal.md for the full motivation.

## Goals / Non-Goals

**Goals:**
- One log line per HTTP request, through the existing `JsonFormatter`/
  root-logger system (so `LOG_LEVEL` and the admin endpoint govern it).
- `GET /health` demoted to DEBUG; every other request (including 404s
  for unmatched routes) at INFO.
- Every log line's timestamp rendered as compact UTC (`YYMMDD
  HH:MM:SS`), without touching the separately-spec'd ISO 8601 UTC
  `audit_log.timestamp` column.

**Non-Goals:**
- No IP/hostname allowlisting or request filtering of any kind.
- No change to the existing `debug-logging` capability's detailed
  header/body tracing for the three real endpoints — this adds one
  additional, simpler line on top of it, nothing is removed.
- No change to `uvicorn.error` (startup/shutdown/crash messages stay
  exactly as they are — only `uvicorn.access` is silenced).

## Decisions

### Silence `uvicorn.access` from application code, not the Dockerfile
Clearing `uvicorn.access`'s handlers and setting `propagate = False` in
`src/main.py` keeps the fix self-contained in code we own and test,
rather than depending on a CLI flag (`--no-access-log`) living only in
the `Dockerfile`'s `CMD` where it's easy to lose track of or override by
accident during some future deployment change.

### New middleware as a FastAPI `@app.middleware("http")` function
This wraps the entire ASGI app, including Starlette's own routing — so
it naturally logs a line for requests to undefined routes too (they hit
this middleware, get a 404 from the router, and the middleware logs
that outcome) with no special-casing needed to "catch" scanner traffic.
Implemented as:

```python
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
```

The exception path logs and re-raises rather than swallowing, so a 500
from a route handler is never hidden by this middleware, and FastAPI's
normal exception handling is untouched.

### Compact UTC timestamp computed directly from `record.created`
Rather than mutating `logging.Formatter.converter` globally (which would
silently affect the behavior of any other formatter that might exist in
the process), `JsonFormatter.format()` computes the timestamp directly:
`datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%y%m%d %H:%M:%S")`.
This keeps the UTC conversion local to our own formatter rather than a
process-wide side effect.

## Risks / Trade-offs

- **Silencing `uvicorn.access` removes visibility into
  protocol-level noise that never reaches our middleware** (e.g. a
  malformed request uvicorn rejects before building an ASGI scope at
  all) → Accepted: this is the same category of noise as scanner
  traffic hitting undefined routes, which this proposal already treats
  as uninteresting; `uvicorn.error` still captures genuine server-level
  problems.
- **Changing the timestamp format applies to every log line the
  service emits, not just the new access-log line** → Mitigation: this
  is an explicit, deliberate part of the proposal (not a side effect),
  and the service has a single operator today; if log aggregation
  tooling is ever added later, it will be built against the new format.
