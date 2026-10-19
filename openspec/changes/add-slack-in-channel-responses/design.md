# Design

## Context

`slack-bolt`'s `Respond.__call__` and `Ack.__call__` both accept
`response_type` as a direct keyword argument (confirmed by reading the
installed library source, not just Slack's docs) — Slack's own
mechanism for choosing `"ephemeral"` (default) versus `"in_channel"`
visibility on a slash-command response. See proposal.md for which of
`src/integrations/slack.py`'s six `respond(...)` calls change.

## Goals / Non-Goals

**Goals:**
- Six existing `respond(...)` calls gain `response_type="in_channel"`;
  no new messages, no content changes.
- The three integration test files that call the handler functions
  directly (bypassing slack-bolt's HTTP dispatch, per their own
  docstrings) keep working after the real `respond()` calls under test
  start passing a keyword argument their current stand-in can't
  accept.

**Non-Goals:**
- No change to `slack-trust-command`, `slack-revoke-command`,
  `slack-trust-status-command`, or `slack-command-rate-limiting` —
  none of them specify response visibility today, so none become
  inaccurate.
- No change to authorization, rule evaluation, or audit logging.

## Decisions

### Fix the test stand-in with a small recording helper, not a signature change
`tests/integration/test_slack_trust_flow.py`,
`test_slack_revoke_flow.py`, and `test_slack_trust_status_flow.py` each
pass `responses.append` directly as the `respond` argument to
`_handle_trust()`/`_handle_revoke()`/`_handle_trust_status()`. Once any
`respond(...)` call in the code under test includes
`response_type="in_channel"`, `responses.append(text,
response_type="in_channel")` raises `TypeError: list.append() takes no
keyword arguments` — `list.append` only ever accepts one positional
argument, confirmed by actually running it.

Fix: replace the bare `responses.append` stand-in in each of the three
files with a small local helper that accepts `*args, **kwargs` and
records both, e.g.:

```python
responses = []

def respond(text, **kwargs):
    responses.append((text, kwargs))
```

Existing assertions that check `responses[0]` as a string need to
become `responses[0][0]` (the text) and, where this proposal adds
coverage, `responses[0][1].get("response_type")` (the visibility).
This keeps the fix mechanical and localized to the three files that
actually break, rather than changing `_handle_trust()` etc.'s own
signatures or behavior.

## Risks / Trade-offs

None identified beyond the required test-harness fix above, which is
small, mechanical, and isolated to three files already identified.
