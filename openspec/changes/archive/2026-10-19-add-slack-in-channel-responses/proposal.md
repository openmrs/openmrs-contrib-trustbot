# Proposal

## Why

Trustbot's Slack slash-command responses are currently ephemeral
(Slack's default) — visible only to the person who issued the
command. The operator wants the actual results of `/trust`,
`/trust-revoke`, and `/trust-status` visible to the whole trusted
channel, so other members can see what access changes were made or
looked up without having to re-run the command themselves. Since
trustbot can only be invoked from the one designated private channel,
and everyone in that channel already has privileged access to issue
these same commands, sharing the outcome discloses nothing a channel
member could not already see by running the command themselves.

## What Changes

- The result message for every authorized `/trust`, `/trust-revoke`,
  and `/trust-status` command — the actual grant/revoke/status
  outcome, the "no rule is configured" message, and (for
  `/trust-status`) the "not found in Keycloak" message — is now posted
  with `response_type: "in_channel"`, visible to every member of the
  trusted channel.
- Two categories of message deliberately remain ephemeral (unchanged,
  visible only to the issuing user): the "Usage: `/trust
  <openmrs-id>`"-style hints shown when a command is issued with no
  target ID, and the rate-limit rejection message. Neither is a result
  worth broadcasting to the channel.
- No change to authorization, signature verification, channel
  restriction, rule evaluation, or audit logging — this only changes
  who can see the response text.

## Capabilities

### New Capabilities

- `slack-response-visibility`: which Slack command responses are
  posted `in_channel` (visible to the whole trusted channel) versus
  ephemeral (visible only to the issuing user).

### Modified Capabilities

- `slack-trust-command`: "The caller receives a clear response for
  every valid command" gains a one-sentence note that the response is
  posted in-channel, cross-referencing `slack-response-visibility`.
- `slack-revoke-command`: the same requirement, same one-sentence
  addition.
- `slack-trust-status-command`: "The response reports current access
  and recent history" and "Unknown OpenMRS ID is reported clearly"
  each gain the same one-sentence addition.
- `slack-command-rate-limiting`: "Exceeding the limit produces a
  visible rejection" gains a one-sentence note that the rejection is
  ephemeral, cross-referencing `slack-response-visibility`.

None of these requirements' existing scenarios change — each gets one
clarifying sentence in its description so a reader of that spec alone
learns the visibility fact, rather than needing to already know to
look at the new capability. The full behavior (which exact messages,
and why) still lives in `slack-response-visibility`, following the
same pattern `access-logging` and `action-outcome-logging` established
for cross-cutting concerns — the difference here is that, unlike
those two, the existing specs do make a direct, specific claim
("the caller receives a clear response") that visibility materially
qualifies, so a cross-reference belongs there too.

## Impact

- **Code**: `src/integrations/slack.py` — six existing `respond(...)`
  calls (two each in `_handle_trust()`, `_handle_revoke()`, and
  `_handle_trust_status()`) gain `response_type="in_channel"`. No
  other files change.
- **Tests, required, not optional**: `tests/integration/test_slack_trust_flow.py`,
  `test_slack_revoke_flow.py`, and `test_slack_trust_status_flow.py`
  all call the handler functions directly using `responses.append` as
  a stand-in for `respond`. Once any `respond()` call in the code
  under test passes `response_type` as a keyword argument,
  `responses.append(text, response_type=...)` raises `TypeError:
  list.append() takes no keyword arguments` — confirmed by actually
  running it — so every test in all three files breaks at collection
  time regardless of what it asserts, until that stand-in is replaced.
  This is required groundwork, not incidental cleanup.
- **Specs**: `openspec/specs/slack-trust-command/spec.md`,
  `slack-revoke-command/spec.md`, `slack-trust-status-command/spec.md`,
  and `slack-command-rate-limiting/spec.md` each gain one clarifying
  sentence (see Modified Capabilities above) — no requirement's
  scenarios change.
- **Out of scope**: no change to which messages exist or what they
  say, no change to the rate limiter itself, no change to any
  requirement's scenarios.
