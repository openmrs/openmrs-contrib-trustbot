# Tasks

## 1. Config field

- [x] 1.1 In `src/config.py`'s `SlackConfig`, add
  `default_log_length: int = 10`. Verify with
  `pytest tests/unit/test_config.py` (existing tests unaffected since
  it has a default).
- [x] 1.2 Add a test to `tests/unit/test_config.py` confirming
  `SlackConfig` defaults `default_log_length` to `10` when omitted,
  and respects an explicit value from `config.yaml`. Verify with
  `pytest tests/unit/test_config.py`.

## 2. Audit query

- [x] 2.1 In `src/audit/db.py`, add
  `get_recent_activity(conn, *, limit=10) -> list[dict]`: same shape
  as `get_recent_events()` but with no `WHERE openmrs_id = ?` clause,
  selecting `openmrs_id` in addition to the columns
  `get_recent_events()` already selects, ordered by `id DESC`.
  `get_recent_events()` itself is unchanged.
- [x] 2.2 Add tests to `tests/unit/audit/test_db.py` covering: rows
  from multiple different `openmrs_id`s are all returned, newest
  first; `limit` is respected; an empty table returns an empty list.
  Verify with `pytest tests/unit/audit/test_db.py`.

## 3. `/trust-activity` command and formatter

- [x] 3.1 In `src/integrations/slack.py`, register `/trust-activity`
  alongside the other three commands in `create_slack_app()`
  (`@app.command("/trust-activity")`), with its own
  `handle_trust_activity_command` calling a new `_handle_trust_activity`,
  mirroring `handle_trust_status_command`/`_handle_trust_status`'s
  shape exactly (inline channel check, no `TriggerEvent`, no rules
  engine).
- [x] 3.2 Implement `_handle_trust_activity(command, context, respond)`:
  parse the command's `text` as the optional `n` argument (blank means
  use `context`'s configured default); reject a non-numeric or
  non-positive argument with an ephemeral `"Usage: ..."` response
  (mirroring the other three commands' usage-hint pattern); cap `n` at
  50 silently; call `get_recent_activity(context.audit_conn, limit=n)`;
  render the result via the new formatter (task 3.3) and `respond(...,
  response_type="in_channel")`. `SlackContext` will need a
  `default_log_length` field threaded through from `config.yaml` at
  app construction, alongside its existing fields.
- [x] 3.3 Implement `_format_activity_line(row) -> str` and
  `_format_activity_response(rows) -> str` in `src/integrations/slack.py`,
  implementing the phrasing table in design.md exactly, including its
  generic fallback for any `(trigger, action)` combination not listed,
  and a "no recorded activity yet" message when `rows` is empty.
- [x] 3.4 Add unit tests for `_format_activity_line`/
  `_format_activity_response` (new file
  `tests/unit/integrations/test_slack_activity_format.py` or added to
  the existing `tests/unit/integrations/test_slack.py`) covering every
  row in design.md's phrasing table, plus the fallback case and the
  empty-list case. Verify with `pytest tests/unit/integrations/`.
- [x] 3.5 Add integration tests (new file
  `tests/integration/test_slack_trust_activity_flow.py`, mirroring
  `test_slack_trust_status_flow.py`'s fixture/helper shape including
  its `capturing_respond()` helper) covering: default length when no
  argument given; an explicit valid length; a length above 50 is
  capped, not rejected; a non-numeric argument is rejected (ephemeral,
  `response_type` absent); a non-positive argument is rejected; wrong
  channel produces no response and logs a warning; the main response
  carries `response_type="in_channel"`. Verify with
  `pytest tests/integration/test_slack_trust_activity_flow.py`.
- [x] 3.6 Confirm `/trust-activity` shares the existing rate limiter —
  add a case to `tests/integration/test_slack_rate_limiting.py`
  alongside its existing three-command coverage. Verify with
  `pytest tests/integration/test_slack_rate_limiting.py`.

## 4. Documentation

- [x] 4.1 Add `slack.default_log_length` (with its default and
  purpose) to `openspec/specs/config-schema.md`'s and
  `config/config.example.yaml`'s `slack:` sections, alongside
  `trusted_channel_id`.
- [x] 4.2 Add `/trust-activity <n>` to the registered-commands list in
  `openspec/specs/overview.md` §5.3, and a brief §5.3.2 (mirroring
  §5.3.1's shape) describing its response and that it is read-only.
- [x] 4.3 Add `/trust-activity` to `README.md`'s endpoints table and
  its Slack-commands narrative, and mention it in `CLAUDE.md`'s
  current-state summary.

## 5. Final verification

- [x] 5.1 Run the full test suite with `pytest` and confirm every test
  passes.
- [x] 5.2 Manually start the service locally, issue `/trust` and
  `/trust-revoke` a couple of times to populate `audit_log`, then
  `/trust-activity` with no argument, an explicit small number, and an
  invalid argument, confirming the rendered lines read as expected and
  match design.md's phrasing table.

## Workflow follow-up

- Archive this change once all tasks above are complete and reviewed.
- Commit the resulting code, test, and documentation changes.
- Release as the next minor version once deployed and confirmed
  working in the Slack channel.
