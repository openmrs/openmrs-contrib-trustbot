# Spec Delta

## MODIFIED Requirements

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
