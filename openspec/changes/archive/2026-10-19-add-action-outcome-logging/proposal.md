# Proposal

## Why

After running in production, the operator reports that at INFO level
(the production default) there is no visibility into what the rules
engine actually did. The access log added in `add-access-logging`
reports only the HTTP method, path, and status code — it confirms a
request completed, not what it accomplished. Even at DEBUG, the
request isn't fully traceable from a single line: `execute_rule()`
logs the rule name, action type, status, and detail, but not the
triggering event's source (the issuing Slack username, or which
Discourse webhook/workflow fired) or the target OpenMRS ID — that
context lives in a separate DEBUG line from `evaluate()`. An operator
watching production logs today cannot tell who ran `/trust`, for whom,
or whether it succeeded, without dropping to DEBUG and correlating two
separate lines per event.

## What Changes

- Every Slack slash command (`/trust`, `/trust-revoke`, `/trust-status`)
  and every Discourse webhook/workflow that reaches the rules engine
  produces a new INFO-level log line identifying: the triggering
  source (Slack username, or the Discourse webhook/workflow name), the
  target OpenMRS ID, and the outcome (`success` / `no_change` /
  `failure` / `dry_run`).
- `/trust-status` gets its own INFO-level line reporting the issuing
  Slack username, the target OpenMRS ID, and whether each of its three
  sections (Keycloak groups, Discourse trust level, audit history)
  succeeded or degraded — it never reaches the rules engine, so it
  needs separate handling from the other two commands.
- A validly-parsed event or authorized command that matches zero rules
  (e.g. `/trust` issued when no rule references `slack_trust_command`,
  or a Discourse workflow name no rule references) now also produces
  an INFO-level line, naming the event and stating that no rule
  matched — treated as another known, visible outcome, the same way
  `no_change` already is. This is an assumption beyond the literal
  request, included because leaving it silent would mean the single
  most diagnostically useful case (a misconfigured or missing rule)
  produces no visible signal at all. **This explicitly does not apply**
  to a native Discourse webhook event name with no registered parser
  at all (`build_event()` returning `None` before an OpenMRS ID ever
  exists) — that stays exactly as silent as it is today; per
  `discourse-webhook-trigger`'s existing spec, an unrecognized event
  name is acknowledged, not an error, and this proposal does not
  change that.

## Capabilities

### New Capabilities

- `action-outcome-logging`: every action the rules engine attempts (or
  decides not to attempt, for lack of a matching rule), and the
  `/trust-status` read-only lookup, produces an INFO-level log line
  identifying who/what triggered it, the target OpenMRS ID, and the
  outcome.

### Modified Capabilities

(none — `debug-logging`'s existing DEBUG-level header/payload tracing
requirements are unaffected; `access-logging`'s one-line-per-HTTP-request
behavior is unaffected. This proposal adds a new, additional line
alongside both, for every request that reaches an action decision.)

## Impact

- **Code**: `src/engine/evaluator.py` (`evaluate()`, `execute_rule()`),
  `src/integrations/slack.py` (`_handle_trust_status()`).
- **Tests**: new unit tests covering the new INFO lines for each
  outcome (success, no_change, failure, dry_run, no-rule-matched) and
  confirming the silent-for-unparseable-webhook-event behavior is
  unchanged.
- **Risk, not newly introduced**: `execute_rule()`'s catch-all
  `except Exception as exc: detail=f"Unexpected error: {exc}"` is
  already logged at DEBUG today; this proposal makes that same string
  visible at INFO by default instead of opt-in. The common failure
  paths (`UserNotFoundError`, `KeycloakConnectionError`) already return
  hardcoded, sanitized messages rather than raw exception text; only a
  genuinely unexpected, uncaught exception could carry unanticipated
  content, and that exposure already exists today at DEBUG.
