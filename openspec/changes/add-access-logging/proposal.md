# Proposal

## Why

After a week in production, the service's logs are noisy and the real
request-source IP is missing. Two root causes:

1. `uvicorn`'s built-in access logger is entirely separate from this
   service's own logging system (`src/logging_setup.py`'s root-logger
   setup) — it has its own handler and `propagate=False`, so `LOG_LEVEL`
   and the `POST /admin/log-level` endpoint have zero effect on it.
   Every request, including the Docker healthcheck hitting `GET /health`
   every 30 seconds, is logged at INFO by `uvicorn.access`, forcing the
   operator to `grep -v` it out manually.
2. The stdout JSON log's timestamp (`2026-10-18T14:32:07-0400`) is long
   and carries a variable UTC offset, making `docker compose logs` less
   scannable than it could be.

Separately, nothing currently caps the size of Docker's own log files on
disk, and the real client IP is being lost behind the production nginx
reverse proxy (confirmed: our code already prefers `X-Forwarded-For`
when present — `src/api/webhooks.py`'s `_source_ip()` — nginx just isn't
sending it yet). Both are being fixed as part of the same pass: an
explicit log-rotation setting in `docker-compose.yml`, and documentation
of the reverse-proxy assumption so it's never silently re-broken.

## What Changes

- Replace `uvicorn`'s built-in access logging with a small ASGI
  middleware that logs exactly one summary line per HTTP request through
  the existing `JsonFormatter`/root-logger system, so it honors
  `LOG_LEVEL` and the admin log-level endpoint like every other log line.
  - Every request logs at INFO by default.
  - `GET /health` specifically logs at DEBUG, since it is expected,
    frequent, and uninteresting in normal operation.
  - A request to a route that doesn't exist (scanner/bot traffic, e.g.
    `GET /.aws/credentials.bak`) logs at the same INFO level as any
    other request — not specially demoted; these already 404 before
    reaching any application code, so they are noise, not a security
    concern, and this proposal does not add any IP/hostname filtering.
- Change the stdout JSON log's `timestamp` field
  (`src/logging_setup.py`'s `JsonFormatter`) from ISO-8601-with-offset to
  a compact `YYMMDD HH:MM:SS` format, rendered in UTC. This applies to
  every log line the service emits, not just the new access-log line.
  **This does not touch** the SQLite `audit_log.timestamp` column, which
  is separately spec'd (`overview.md`'s schema) as ISO 8601 UTC and
  stays exactly as it is.
- Add a `logging:` block to `docker-compose.yml` capping on-disk log
  growth (`json-file` driver, `max-size: "10m"`, `max-file: "5"`).
- Add a short section to `README.md` documenting two operating
  assumptions: (1) the service expects to sit behind a reverse proxy
  that sets `X-Forwarded-For`/`X-Real-IP` — without that, per-source-IP
  rate limiting on the Discourse webhook degrades to a single shared
  bucket for all callers behind the proxy, and if the service is also
  reachable directly (bypassing the proxy), a caller could forge
  `X-Forwarded-For` to dodge that rate limit; and (2) every logged
  timestamp is UTC.

## Capabilities

### New Capabilities

- `access-logging`: one line logged per HTTP request, replacing
  `uvicorn`'s built-in access log, with `/health` demoted to DEBUG and
  every log entry's timestamp rendered as compact UTC.

### Modified Capabilities

(none — the existing `debug-logging` capability's detailed header/body
tracing for `/webhook/discourse`, `/slack/commands`, and
`/admin/log-level` is unaffected; this proposal adds one additional,
simpler summary line on top of it, for every request including those
three)

## Impact

- **Code**: `src/main.py` (disable `uvicorn`'s access log, register the
  new middleware), a new small middleware module, `src/logging_setup.py`
  (`JsonFormatter`'s timestamp format).
- **Tests**: new unit tests for the middleware's per-route log level and
  the new timestamp format; existing DEBUG-logging tests are unaffected.
- **Ops**: `docker-compose.yml` (new `logging:` block).
- **Docs**: `README.md` (reverse-proxy assumption, UTC timestamps).
- **Out of scope**: no IP/hostname allowlisting or request filtering —
  the three endpoints that can mutate Keycloak state are already fully
  protected by signature verification regardless of source; this
  proposal is about log noise and format, not access control.
