# slack-response-visibility Specification

## Purpose

Determines which of trustbot's Slack command responses are visible to
the whole trusted channel versus only to the issuing user, since
Slack's default (ephemeral) hides every response from everyone except
the person who typed the command.

## Requirements

### Requirement: Result messages are posted in-channel
The result message for an authorized `/trust`, `/trust-revoke`,
`/trust-status`, or `/trust-activity` command — the actual outcome,
the "no rule is configured" message, the "not found in Keycloak"
message, and the recent-activity list — SHALL be posted with
`response_type: "in_channel"`, visible to every member of the trusted
channel, not only the issuing user.

#### Scenario: A /trust command changes access
- **WHEN** an authorized `/trust` command's matched rule completes
  (granted, already trusted, dry-run, or failed)
- **THEN** the response is posted `in_channel`

#### Scenario: A /trust-revoke command changes access
- **WHEN** an authorized `/trust-revoke` command's matched rule
  completes (revoked, already not trusted, dry-run, or failed)
- **THEN** the response is posted `in_channel`

#### Scenario: A /trust-status lookup completes
- **WHEN** an authorized `/trust-status` command successfully reports
  (fully or partially) on a target OpenMRS ID, or reports that the
  target was not found
- **THEN** the response is posted `in_channel`

#### Scenario: No rule is configured for a command
- **WHEN** an authorized `/trust` or `/trust-revoke` command's target
  OpenMRS ID is resolved but no enabled rule matches
- **THEN** the "no rule is configured" response is posted `in_channel`

#### Scenario: A /trust-activity lookup completes
- **WHEN** an authorized `/trust-activity` command successfully lists
  recent activity
- **THEN** the response is posted `in_channel`

### Requirement: Usage hints and rate-limit rejections remain ephemeral
A usage hint (shown when a command is issued with no target OpenMRS
ID, or with an invalid argument) and a rate-limit rejection message
SHALL remain ephemeral, visible only to the issuing user — neither is
a result worth broadcasting to the channel.

#### Scenario: A command is issued with no target ID
- **WHEN** `/trust`, `/trust-revoke`, `/trust-status`, or
  `/trust-activity` is issued with no OpenMRS ID (or, for
  `/trust-activity`, an invalid argument)
- **THEN** the usage hint is visible only to the issuing user

#### Scenario: A user is rate limited
- **WHEN** a Slack user exceeds the configured command rate limit
- **THEN** the rate-limit rejection message is visible only to that
  user

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
