# Spec Delta

## Purpose

Determines which of trustbot's Slack command responses are visible to
the whole trusted channel versus only to the issuing user, since
Slack's default (ephemeral) hides every response from everyone except
the person who typed the command.

## ADDED Requirements

### Requirement: Result messages are posted in-channel
The result message for an authorized `/trust`, `/trust-revoke`, or
`/trust-status` command — the actual outcome, the "no rule is
configured" message, and the "not found in Keycloak" message — SHALL
be posted with `response_type: "in_channel"`, visible to every member
of the trusted channel, not only the issuing user.

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

### Requirement: Usage hints and rate-limit rejections remain ephemeral
A usage hint (shown when a command is issued with no target OpenMRS
ID) and a rate-limit rejection message SHALL remain ephemeral, visible
only to the issuing user — neither is a result worth broadcasting to
the channel.

#### Scenario: A command is issued with no target ID
- **WHEN** `/trust`, `/trust-revoke`, or `/trust-status` is issued with
  no OpenMRS ID
- **THEN** the usage hint is visible only to the issuing user

#### Scenario: A user is rate limited
- **WHEN** a Slack user exceeds the configured command rate limit
- **THEN** the rate-limit rejection message is visible only to that
  user
