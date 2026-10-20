# Spec Delta

## ADDED Requirements

### Requirement: The immediate acknowledgment also signals in-channel visibility
The system SHALL set `response_type: "in_channel"` on the immediate
acknowledgment for `/trust`, `/trust-revoke`, `/trust-status`, and
`/trust-activity` whenever the command passes the same
channel-restriction and argument check that determines its eventual
response's visibility, and SHALL leave the acknowledgment ephemeral
otherwise — since Slack reveals the invoking command itself only when
the *immediate* acknowledgment carries this, not when a later,
delayed response does.

#### Scenario: A valid command's invocation is visible
- **WHEN** an authorized `/trust`, `/trust-revoke`, `/trust-status`,
  or `/trust-activity` command passes its channel-restriction and
  argument check
- **THEN** the immediate acknowledgment carries `response_type:
  "in_channel"`, so the command invocation itself is visible to the
  channel, in addition to its eventual response

#### Scenario: A wrong-channel command's invocation stays hidden
- **WHEN** a command is issued from a channel other than the trusted
  channel
- **THEN** the immediate acknowledgment carries no `response_type`,
  consistent with the fully silent rejection this already receives

#### Scenario: A missing or invalid argument's invocation stays hidden
- **WHEN** `/trust`, `/trust-revoke`, or `/trust-status` is issued
  with no OpenMRS ID, or `/trust-activity` is issued with a
  non-numeric or non-positive argument
- **THEN** the immediate acknowledgment carries no `response_type`,
  consistent with the usage hint that follows remaining ephemeral

#### Scenario: A rate-limited command is unaffected
- **WHEN** a Slack user has exceeded the configured command rate
  limit
- **THEN** the acknowledgment is whatever `rate_limit_middleware`
  already sends, decided before this check ever runs
