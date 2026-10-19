# Tasks

## 1. Compact UTC timestamp format

- [x] 1.1 In `src/logging_setup.py`, change `JsonFormatter.format()` to
  compute the `timestamp` field as
  `datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%y%m%d %H:%M:%S")`
  instead of `self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")`. Do not
  touch `logging.Formatter.converter` (keep the UTC conversion local to
  this formatter, per design.md).
- [x] 1.2 Add a test to `tests/unit/test_logging_setup.py` asserting a
  logged record's `timestamp` field matches the pattern
  `^\d{6} \d{2}:\d{2}:\d{2}$`, then verify with
  `pytest tests/unit/test_logging_setup.py`.
- [x] 1.3 Confirm `src/audit/db.py`'s audit log writer is untouched —
  verify with `grep -n timestamp src/audit/db.py` showing no changes
  needed, and `pytest tests/unit/audit/` passing — since
  `audit_log.timestamp` must remain ISO 8601 UTC per `overview.md`'s
  schema, independent of this change.

## 2. Access-log middleware, replacing uvicorn's built-in access log

- [x] 2.1 Create `src/access_log.py` with `silence_uvicorn_access_log()`
  (clears `logging.getLogger("uvicorn.access")`'s handlers and sets
  `propagate = False`) and `register_access_log_middleware(app)` (adds
  the `@app.middleware("http")` function from design.md: logs
  `method path -> status` at DEBUG for `/health`, INFO for everything
  else, and on an exception from `call_next`, logs then re-raises
  without swallowing it). Verify the module imports cleanly with
  `python -c "import src.access_log"`.
- [x] 2.2 Wire both into `src/main.py`: call
  `silence_uvicorn_access_log()` and `register_access_log_middleware(app)`
  during app construction (after `app = FastAPI(...)`). Verify by
  starting the service locally (`uvicorn src.main:app --port 8080`,
  with `.env` sourced) and confirming a `curl localhost:8080/health`
  produces no access-log line in the terminal at the default `INFO`
  level, with no `uvicorn.access`-style line either.
- [x] 2.3 Add tests (new file `tests/unit/test_access_log.py`, following
  `tests/unit/test_main.py`'s `app_client` fixture pattern) covering:
  `GET /health` produces no visible log at `INFO` but does at `DEBUG`;
  a normal request (e.g. `GET /health` is the only unauthenticated GET
  route — use it, or a request to an undefined path) is visible at
  `INFO`; a request to an undefined path returns `404` and is logged at
  `INFO`; changing the level via `POST /admin/log-level` takes effect on
  the next request without a restart. Verify with
  `pytest tests/unit/test_access_log.py`.
- [x] 2.4 Confirm the existing DEBUG header/body tracing in
  `src/api/webhooks.py`, `src/api/admin.py`, and
  `src/integrations/slack.py` is unaffected — verify with
  `pytest tests/unit/api/ tests/unit/integrations/test_slack.py` and
  `pytest tests/security/` all passing unchanged.

## 3. Bound Docker log growth

- [x] 3.1 Add a `logging:` block to `docker-compose.yml`'s `trustbot`
  service: `driver: "json-file"` with `options: {max-size: "10m",
  max-file: "5"}`. Verify with
  `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`.

## 4. Document operating assumptions in README.md

- [x] 4.1 Add a short section to `README.md` documenting that the
  service expects to run behind a reverse proxy that sets
  `X-Forwarded-For`/`X-Real-IP` (linking to the existing
  `_source_ip()` behavior in `src/api/webhooks.py`), including the risk
  that per-source-IP rate limiting degrades to one shared bucket
  without those headers, or could be bypassed by a caller who reaches
  the service directly if it's also exposed outside the proxy.
- [x] 4.2 In the same section (or immediately after), note that every
  logged timestamp is UTC.

## 5. Final verification

- [x] 5.1 Run the full test suite with `pytest` and confirm every test
  passes.
- [x] 5.2 Run `grep -rn "formatTime\|%Y-%m-%dT" src/logging_setup.py`
  and confirm the old ISO-8601-with-offset format string is gone.

## Workflow follow-up

- Archive this change once all tasks above are complete and reviewed.
- Commit the resulting code, test, ops, and documentation changes.
- Consider a version bump/tag once deployed and confirmed quiet in
  production logs for a few days.
