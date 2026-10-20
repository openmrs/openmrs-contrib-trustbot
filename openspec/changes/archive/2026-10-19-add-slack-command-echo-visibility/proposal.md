# Proposal

## Why

After deploying v1.5.0's in-channel-visibility work, the operator
noticed that only the *responses* appear in the private Slack channel
— the slash command invocations themselves (the "username used
`/command args`" line Slack renders automatically) still appear only
to the issuing user. Per Slack's own documented behavior, that line's
visibility is controlled specifically by whether the **immediate**
acknowledgment (within 3 seconds of the initial POST) carries
`response_type: "in_channel"` — not by whether a later, delayed
response to `response_url` does. trustbot's four command listeners
all call `ack()` with no arguments; `response_type="in_channel"` is
only ever set on the delayed `respond()` call. So today the delayed
response is visible but the command that triggered it is not —
backwards from the intent of the work that shipped in v1.5.0.

## What Changes

- Each of the four command listeners (`/trust`, `/trust-revoke`,
  `/trust-status`, `/trust-activity`) now computes, before calling
  `ack()`, the same channel-restriction and argument-presence/validity
  check that already exists further downstream, and sets
  `ack(response_type="in_channel")` when it passes, or leaves the ack
  exactly as it is today (plain `ack()`, ephemeral) when it doesn't.
- This check was verified, by reading the code, to be a **complete
  and exact** predictor of eventual visibility, not a heuristic: for
  every command, every `respond()` call that can be reached once the
  channel+argument check passes is already `response_type="in_channel"`
  (including "no rule is configured", which needs the rules engine
  but is already in-channel) — there is no case that passes the check
  and still ends up ephemeral later.
- Rate-limiting is unaffected: it's decided entirely in
  `rate_limit_middleware`, which runs before slack-bolt dispatches to
  the per-command listener at all, and already acks independently.
- No change to any existing `respond()` call's `response_type` — those
  are already correct.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `slack-response-visibility`: gains a new requirement for the
  immediate acknowledgment's visibility, alongside the existing
  requirements for the delayed response's visibility.
- `slack-trust-command`, `slack-revoke-command`,
  `slack-trust-status-command`, `slack-trust-activity-command`: each
  gains a one-sentence addition to their existing in-channel
  cross-reference, noting the immediate acknowledgment now also
  signals this — mirroring the same kind of cross-reference already
  added to these same four specs in `add-slack-in-channel-responses`.

## Impact

- **Code**: `src/integrations/slack.py` only — the four listener
  functions inside `create_slack_app()`, plus a small extracted helper
  for `/trust-activity`'s argument-validity check (reused by both the
  new ack-time check and the existing rejection logic, so the
  two-part condition can't drift into two different copies).
- **Tests**: the existing integration tests
  (`tests/integration/test_slack_trust_flow.py` and siblings) call
  `_handle_trust()` etc. directly, bypassing the listener wrapper
  entirely, so they cannot exercise this fix and don't need to
  change. New tests are needed that exercise the actual registered
  listener function — see design.md for the exact mechanism
  (`app._listeners[i].ack_function`), confirmed against the installed
  slack-bolt version.
- **Verification**: the user is confident the empty-text,
  `response_type: "in_channel"` ack shape works as Slack's own docs
  show it, but per this project's established practice for
  platform-behavior assumptions, this should still be confirmed
  against a real Slack workspace during apply.
- **Out of scope**: no change to any delayed `respond()` call, no
  change to the pre-existing, still-undocumented `"Usage: ..."`
  message wording, no new config, no new capability.
