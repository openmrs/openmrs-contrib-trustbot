# access-logging Specification

## Purpose

Gives every incoming HTTP request exactly one log entry through the
service's own structured logging system — rather than `uvicorn`'s
independent, unconfigurable built-in access log — so request visibility
honors `LOG_LEVEL` and the runtime admin log-level endpoint, and so
routine health checks don't dominate normal-level logs.

## Requirements

### Requirement: Every HTTP request is logged once, through the application's own logging system
The system SHALL log exactly one entry for every incoming HTTP request,
through the same logging configuration (format and level control) used
by the rest of the application, so request logging honors `LOG_LEVEL`
and runtime changes made via `POST /admin/log-level`.

#### Scenario: A request is logged at the configured level
- **WHEN** the application log level is `INFO` (the default) and a
  non-health request is received
- **THEN** exactly one log entry for that request is emitted, visible at
  `INFO`

#### Scenario: Runtime level change takes effect on the next request
- **WHEN** the log level is changed to `ERROR` via `POST
  /admin/log-level` and a non-health request is then received
- **THEN** no entry for that request appears, since `INFO` is now below
  the active threshold

### Requirement: Health check requests are logged at DEBUG
`GET /health` SHALL be logged at `DEBUG` level rather than `INFO`, so
routine health checks are not visible in normal-level logs.

#### Scenario: Health check at the default level
- **WHEN** the application log level is `INFO` (the default) and a `GET
  /health` request is received
- **THEN** no log entry for that request is visible

#### Scenario: Health check at DEBUG
- **WHEN** the application log level is `DEBUG` and a `GET /health`
  request is received
- **THEN** a log entry for that request is visible, identifying it as a
  health check

### Requirement: Requests to undefined routes are logged like any other request
A request to a path with no matching route SHALL be logged at the same
level as any other non-health request. This is a logging-noise
reduction only — such requests already receive a 404 before reaching
any application code, trigger no rule evaluation, and this requirement
does not add any form of IP- or hostname-based filtering.

#### Scenario: Request to a nonexistent path
- **WHEN** the application log level is `INFO` (the default) and a
  request to a path with no matching route is received
- **THEN** exactly one log entry for that request is emitted, visible
  at `INFO`, and the response is `404` with no rule evaluation

### Requirement: Log timestamps are compact and UTC
Every log entry the system emits, including the per-request access log
and every other log message, SHALL render its timestamp in UTC using a
compact `YYMMDD HH:MM:SS` format. This is distinct from the SQLite audit
log's `audit_log.timestamp` column, which remains ISO 8601 UTC as
already specified and is unaffected by this requirement.

#### Scenario: Any log entry is emitted
- **WHEN** the service emits a log entry at any level
- **THEN** its timestamp is rendered in UTC in `YYMMDD HH:MM:SS` format

#### Scenario: An audit log row is written
- **WHEN** a rule evaluation results in an audit log row
- **THEN** that row's `timestamp` column remains ISO 8601 UTC, unchanged
  by this requirement
