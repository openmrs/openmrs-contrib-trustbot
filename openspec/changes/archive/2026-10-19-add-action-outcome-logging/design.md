# Design

## Context

`src/engine/evaluator.py` is the single chokepoint every engine-routed
trigger passes through — `evaluate()` then, for each matched rule,
`execute_rule()`. `execute_rule()` already calls `record_event()` with
every field this proposal needs (`event.source`, `event.openmrs_id`,
`rule.name`, `action.type`, `result.status`, `result.detail`) — that's
exactly what gets written to the audit log. See proposal.md for the
full motivation.

## Goals / Non-Goals

**Goals:**
- One new INFO-level log line per attempted action, at the point
  `record_event()` is already called, so it is free for all four
  engine-routed trigger surfaces (`/trust`, `/trust-revoke`, native
  Discourse webhook, Discourse workflow) with a single code change.
- One new INFO-level line for "no rule matched," added inside
  `evaluate()` itself (also generic across all four surfaces), but only
  for events that successfully resolved an OpenMRS ID.
- A separate, bespoke INFO line for `/trust-status`, since it
  structurally never calls `evaluate()`/`execute_rule()`.

**Non-Goals:**
- No change to `debug-logging`'s existing DEBUG-level tracing, and no
  change to `access-logging`'s one-line-per-HTTP-request behavior.
- No new redaction mechanism. The new lines carry only the same fields
  already written to the audit log (and already logged at DEBUG) —
  nothing from request headers or raw payloads is introduced.
- No log line for a native Discourse webhook event name with no
  registered parser (see Decisions below).

## Decisions

### Hook the "action attempted" line at the `record_event()` call site
Rather than adding separate logging in each of `_handle_trust()`,
`_handle_revoke()`, and `src/api/webhooks.py`'s `_evaluate_and_execute()`,
one line inside `execute_rule()` covers all of them, since they all
call it. This also guarantees the logged fields can never drift from
what the audit log records, since both are built from the same
`result`/`event`/`rule`/`action` values at the same point.

### "No rule matched" is INFO only when an OpenMRS ID was actually resolved
`evaluate()` is called in two different states: either `event` already
has a real `openmrs_id` (a native webhook/workflow that parsed
successfully, or an authorized Slack command with non-blank text), or
`evaluate()` is never reached at all (an unrecognized webhook event
name returns `None` from `build_event()` before `evaluate()` is ever
called). Because of this, the "stay silent" requirement does not need
any special-casing inside `evaluate()` itself — it is already silent
for that case, simply because it is never invoked. The new INFO line
inside `evaluate()`'s "no matched rules" branch therefore only ever
fires for events that already have a resolved target, which is exactly
the boundary proposal.md and the spec describe.

### `/trust-status` logs separately, after all three sections resolve
`_handle_trust_status()` has no `TriggerEvent`, no rule, no action —
its three sections (Keycloak groups, Discourse trust level, audit
history) already independently degrade on failure (per its own
existing design). The new log line is added once, right before the
final `respond(...)` call, after all three `try`/`except` blocks have
resolved, summarizing which (if any) degraded.

## Risks / Trade-offs

See proposal.md's Impact section for the one identified risk
(`execute_rule()`'s catch-all exception detail becoming INFO-visible
rather than DEBUG-only) — not a new exposure, since the same string is
already logged at DEBUG today.
