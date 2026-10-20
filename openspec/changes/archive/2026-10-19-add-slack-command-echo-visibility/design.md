# Design

## Context

Confirmed by reading the current code: all four listeners in
`create_slack_app()` (`src/integrations/slack.py`) call `ack()` with
no arguments, then delegate to their `_handle_*` function, where
`response_type="in_channel"` is set only on the later `respond()`
call (POSTed to `response_url`). Per Slack's documented behavior, the
command-invocation echo's visibility is controlled by the *immediate*
acknowledgment's `response_type`, not the delayed response's. See
proposal.md for the full investigation establishing that the
channel+argument check already used downstream is a complete, exact
predictor of eventual visibility for every command — there is no
case that passes it and still ends up ephemeral later.

## Goals / Non-Goals

**Goals:**
- Set `response_type="in_channel"` on the immediate `ack()` exactly
  when the eventual response will be in-channel, for all four
  commands.
- Reuse existing validation logic rather than duplicating business
  rules; where a pure, cheap function already exists
  (`build_trust_event`/`build_revoke_event`), call it again rather
  than re-implementing its check.

**Non-Goals:**
- No change to any `respond()` call's existing `response_type`.
- No change to `rate_limit_middleware` — it already decides and acks
  independently, before any per-command listener runs.
- No restructuring of `_handle_trust()`/`_handle_revoke()`/
  `_handle_trust_status()`/`_handle_trust_activity()`'s own logic or
  signatures.

## Decisions

### Call the existing builders again rather than changing their callers' signatures
For `/trust` and `/trust-revoke`, `build_trust_event()`/
`build_revoke_event()` (`src/triggers/slack.py`) already compute
exactly "is the channel right, and is there a non-blank OpenMRS ID" —
returning `None` for a wrong channel, or a `TriggerEvent` whose
`openmrs_id` is blank for a missing argument. Calling this a second
time, once in the listener (to decide the ack) and once inside
`_handle_trust`/`_handle_revoke` (as today, for the actual work), is
cheap and side-effect-free — it only reads from `command` and builds
a plain object. This was chosen over changing `_handle_trust()`'s
signature to accept a pre-built event, which would also require
updating `tests/integration/test_slack_trust_flow.py` and
`test_slack_revoke_flow.py`, which call it directly with a raw
`command` dict today.

For `/trust-status` and `/trust-activity`, there is no such builder —
the channel check is inline. The listener repeats the same one-line
`command.get("channel_id") == context.trusted_channel_id` comparison
already in `_handle_trust_status()`/`_handle_trust_activity()`.

### Extract `/trust-activity`'s argument-validity check into a shared helper
Unlike the other three commands' simple "is text blank" check,
`/trust-activity`'s argument validity is two conditions
(`text.isdigit() and int(text) > 0`). Duplicating that as raw
inline code in both the listener and `_handle_trust_activity()` risks
the two copies drifting apart later. Extract it once:

```python
def _trust_activity_argument_is_valid(text: str) -> bool:
    return not text or (text.isdigit() and int(text) > 0)
```

used by both the new ack-time check and the existing rejection logic.

### Testing: call the registered listener's `ack_function` directly
Confirmed by inspecting the installed slack-bolt version: `app._listeners`
is a list of `CustomListener` objects, each with an `.ack_function`
attribute holding the exact decorated function (e.g.
`handle_trust_command`), and `.matchers` whose `.func(body)` identifies
which command a listener is registered for — the same
`matcher.func({"command": "/trust"})` pattern already used in
`tests/unit/integrations/test_slack.py`. New tests find the right
listener this way, then call `listener.ack_function(ack=..., command=...,
respond=...)` directly — the same "reach into the registered object
and call it with manually-constructed kwargs" approach
`tests/integration/test_slack_rate_limiting.py` already uses for the
middleware function, bypassing slack-bolt's HTTP/signature layer
(out of scope here, already covered elsewhere) without needing a
live Slack token.

## Risks / Trade-offs

- **Calling `build_trust_event`/`build_revoke_event` twice per
  request** → Negligible: both are pure, in-memory, no I/O.
- **The empty-text, `response_type: "in_channel"` ack shape is
  assumed to work as Slack's docs show** → The user is confident in
  this, but it should still be confirmed against a real Slack
  workspace during apply, per this project's established practice for
  platform-behavior assumptions (the Discourse header/payload
  surprises earlier in this project's history are exactly why).
