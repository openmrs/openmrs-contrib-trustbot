# Tasks

## 1. Make result messages in-channel

- [x] 1.1 In `src/integrations/slack.py`'s `_handle_trust()`, add
  `response_type="in_channel"` to the `"No rule is configured to
  handle \`/trust\`..."` message and to the final
  `respond(_format_response(...))` call. Do not touch the `"Usage:
  ..."` message.
- [x] 1.2 In `_handle_revoke()`, make the same two changes (mirroring
  1.1) for the `"No rule is configured to handle \`/trust-revoke\`..."`
  message and the final `respond(_format_revoke_response(...))` call.
  Do not touch the `"Usage: ..."` message.
- [x] 1.3 In `_handle_trust_status()`, add
  `response_type="in_channel"` to the `` "`{openmrs_id}` was not found
  in Keycloak." `` message and to the final
  `respond(_format_trust_status_response(...))` call. Do not touch the
  `"Usage: ..."` message.
- [x] 1.4 Confirm the rate-limit rejection (`ack(text=RATE_LIMITED_MESSAGE)`
  in `rate_limit_middleware`) and the three bare `ack()` calls are
  unchanged — verify with `grep -n "response_type" src/integrations/slack.py`
  showing exactly 6 matches.

## 2. Fix the test harness and verify visibility

- [x] 2.1 In `tests/integration/test_slack_trust_flow.py`, replace the
  `responses.append` stand-in with a local `respond(text, **kwargs)`
  helper that appends `(text, kwargs)` tuples (per design.md), update
  every existing `responses[0]` text assertion to `responses[0][0]`,
  and add an assertion that `responses[0][1].get("response_type") ==
  "in_channel"` for at least the successful-grant and
  target-already-trusted scenarios. Verify with
  `pytest tests/integration/test_slack_trust_flow.py`.
- [x] 2.2 Make the same changes to
  `tests/integration/test_slack_revoke_flow.py` (mirroring 2.1).
  Verify with `pytest tests/integration/test_slack_revoke_flow.py`.
- [x] 2.3 Make the same changes to
  `tests/integration/test_slack_trust_status_flow.py`. Note this file
  also has tests using `lambda *_: None` as the `respond` stand-in
  (from the add-action-outcome-logging change) — those are unaffected
  and need no change. Verify with
  `pytest tests/integration/test_slack_trust_status_flow.py`.
- [x] 2.4 Add a test (in whichever of the three files most naturally
  fits, or a new one) confirming a "no rule configured" response also
  carries `response_type="in_channel"`.

## 3. Final verification

- [x] 3.1 Run the full test suite with `pytest` and confirm every test
  passes.
- [x] 3.2 Run `grep -rn "responses\[0\]\b" tests/integration/test_slack_trust_flow.py tests/integration/test_slack_revoke_flow.py tests/integration/test_slack_trust_status_flow.py`
  and confirm no remaining bare (un-indexed-into-tuple) `responses[0]`
  string assertions were missed.

## Workflow follow-up

- Archive this change once all tasks above are complete and reviewed.
- Commit the resulting code and test changes.
- Release as the next patch or minor version once deployed and
  confirmed working in the Slack channel.
