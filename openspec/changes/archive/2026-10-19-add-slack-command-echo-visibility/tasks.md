# Tasks

## 1. Extract the shared `/trust-activity` argument-validity helper

- [x] 1.1 In `src/integrations/slack.py`, add
      `_trust_activity_argument_is_valid(text: str) -> bool` (`not text or
      (text.isdigit() and int(text) > 0)`) and replace the equivalent
      inline check inside `_handle_trust_activity()` with a call to it.
      Verify the existing `/trust-activity` tests
      (`tests/integration/test_slack_trust_activity_flow.py`) still pass
      unchanged, confirming the extraction preserved behavior.

## 2. Make `/trust` and `/trust-revoke`'s immediate ack channel-and-argument-aware

- [x] 2.1 In `handle_trust_command()`, call `build_trust_event(command,
      trusted_channel_id=context.trusted_channel_id)` before `ack()`; ack
      with `response_type="in_channel"` when it returns a event whose
      `openmrs_id` is non-blank, otherwise ack with no arguments (today's
      behavior unchanged). Mirror this in `handle_revoke_command()` using
      `build_revoke_event()`.
- [x] 2.2 Add tests that locate each listener via `app._listeners` (by
      matcher, as `tests/unit/integrations/test_slack.py` already does)
      and call its `.ack_function` directly with a constructed `command`
      dict and a capturing `ack`, covering for both `/trust` and
      `/trust-revoke`: valid command (in-channel ack), wrong channel
      (bare ack), missing OpenMRS ID (bare ack). Verify by running the
      new tests and confirming each asserts the exact `ack` call
      arguments.

## 3. Make `/trust-status` and `/trust-activity`'s immediate ack channel-and-argument-aware

- [x] 3.1 In `handle_trust_status_command()`, before `ack()`, compare
      `command.get("channel_id")` to `context.trusted_channel_id` and
      check `command.get("text", "").strip()` is non-blank; ack with
      `response_type="in_channel"` only when both hold, else bare `ack()`.
- [x] 3.2 In `handle_trust_activity_command()`, before `ack()`, compare
      `command.get("channel_id")` to `context.trusted_channel_id` and
      call `_trust_activity_argument_is_valid()` (from task 1.1) on
      `command.get("text", "").strip()`; ack with
      `response_type="in_channel"` only when both hold, else bare `ack()`.
- [x] 3.3 Add tests mirroring task 2.2's approach for `/trust-status`
      (valid command, wrong channel, missing OpenMRS ID) and
      `/trust-activity` (valid with no argument, valid with a numeric
      argument, wrong channel, non-numeric argument, non-positive
      argument). Verify by running the new tests and confirming each
      asserts the exact `ack` call arguments.

## 4. Full-suite verification

- [x] 4.1 Run the full test suite (`pytest`) and confirm it passes,
      including the existing integration tests for all four commands
      (`tests/integration/test_slack_*_flow.py`) and the existing
      rate-limiting tests (`tests/integration/test_slack_rate_limiting.py`),
      none of which call the listener's `ack_function` and so must be
      unaffected by this change.

## Workflow follow-up

- [x] Confirm live, against a real Slack workspace, that an `ack()` call
  with no text and `response_type: "in_channel"` reveals the command
  invocation without posting an extra empty bot message, per this
  project's practice of live-verifying platform-behavior assumptions
  before relying on them in production. Confirmed by the user.
- [x] Archive this change once implementation and verification are complete.
- [x] Consider releasing as a maintenance version (e.g. v1.5.1), per the
  user's own suggested framing, once deployed and confirmed. Tagged
  `v1.5.1`.
