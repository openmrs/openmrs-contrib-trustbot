# Tasks

## 1. Log every attempted action at INFO

- [x] 1.1 In `src/engine/evaluator.py`'s `execute_rule()`, add an
  INFO-level log call right after computing `result` (same place
  `record_event()` is called), logging `event.type`, `event.source`,
  `event.openmrs_id`, `rule.name`, `action.type`, `result.status`, and
  `result.detail`. Keep the existing DEBUG lines unchanged.
- [x] 1.2 Add tests to `tests/unit/engine/test_evaluator.py` (following
  the existing `test_execute_rule_logs_action_attempt_and_result_at_debug`
  pattern, but `caplog.at_level("INFO")`, with assertions inside the
  `with` block per the established `caplog` handler-level gotcha)
  covering `success`, `no_change`, `failure`, and `dry_run` outcomes,
  each asserting the INFO log contains the source and openmrs_id in
  addition to rule/action/status. Verify with
  `pytest tests/unit/engine/test_evaluator.py`.

## 2. Log "no rule matched" at INFO for resolved events only

- [x] 2.1 In `src/engine/evaluator.py`'s `evaluate()`, in the branch
  where `matched` is empty, add an INFO-level log call alongside the
  existing `logger.debug("no rules matched")` line, including
  `event.type`, `event.name`, `event.source`, and `event.openmrs_id`.
- [x] 2.2 Add a test to `tests/unit/engine/test_evaluator.py` asserting
  the INFO log appears (with source/openmrs_id) when `evaluate()`
  returns no matches for an event that has a real `openmrs_id`. Verify
  with `pytest tests/unit/engine/test_evaluator.py`.
- [x] 2.3 Add a test to `tests/unit/api/test_webhooks.py` (or extend an
  existing one) confirming that a native Discourse webhook event name
  with no registered parser (per
  `test_native_webhook_valid_signature_with_unsupported_event_name_takes_no_action`
  in `tests/security/test_discourse_webhook.py`) produces no
  action-outcome log line at all — since `build_event()` returns
  `None` before `evaluate()` is ever called, confirming the silent
  boundary from design.md holds. Verify with
  `pytest tests/unit/api/test_webhooks.py tests/security/test_discourse_webhook.py`.

## 3. Log /trust-status's own outcome at INFO

- [x] 3.1 In `src/integrations/slack.py`'s `_handle_trust_status()`,
  add an INFO-level log call after all three `try`/`except` blocks
  resolve (groups, trust level, recent events) and before the final
  `respond(...)` call, logging `command.get("user_name")`, `openmrs_id`,
  and which of the three sections (if any) degraded.
- [x] 3.2 Add tests to `tests/unit/integrations/test_slack.py` (or
  `tests/integration/test_slack_trust_status_flow.py`, matching
  whichever file already exercises `_handle_trust_status` most
  directly) covering: all three sections succeed, and at least one
  section degrades. Verify with
  `pytest tests/unit/integrations/test_slack.py tests/integration/test_slack_trust_status_flow.py`.

## 4. Final verification

- [x] 4.1 Run the full test suite with `pytest` and confirm every test
  passes.
- [x] 4.2 Manually start the service locally at the default (INFO)
  level, issue one of each (`/trust`, `/trust-revoke`, a Discourse
  workflow call, and `/trust-status`), and confirm each produces a
  readable INFO-level line with source, target OpenMRS ID, and
  outcome — not just the generic access-log line.

## Workflow follow-up

- Archive this change once all tasks above are complete and reviewed.
- Commit the resulting code and test changes.
- Release as the next patch or minor version once deployed and
  confirmed in production logs.
