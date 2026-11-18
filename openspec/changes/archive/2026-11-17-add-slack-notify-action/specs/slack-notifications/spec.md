# Spec Delta

## Purpose

Lets a rule post a templated, human-readable announcement to a Slack
channel as a rules-engine action, so the community can see automatic
trust changes (and any other rule outcome) happen without polling the
audit log or `/trust-activity`.

## ADDED Requirements

### Requirement: A matched rule can post a templated Slack message
A rule's actions list SHALL support a `slack_notify` action that posts a
message to Slack, with `${openmrs_id}` in its configured `message`
template interpolated from the firing event's target OpenMRS ID.

#### Scenario: A Discourse-triggered grant posts a notification
- **WHEN** a matched rule's actions include `slack_notify` with
  `message: "${openmrs_id} trusted by OpenMRS Talk"` and the rule fires
  for OpenMRS ID `jdoe`
- **THEN** the system posts "jdoe trusted by OpenMRS Talk" to Slack

### Requirement: The destination channel defaults to the trusted channel and is overridable
A `slack_notify` action's destination channel SHALL default to
`config.yaml`'s `slack.trusted_channel_id` when the action does not
specify a `channel`, and SHALL post to the specified channel (given as
either a Slack channel ID or a `#name`) when it does.

#### Scenario: No channel specified
- **WHEN** a `slack_notify` action has no `channel` field
- **THEN** the message is posted to the configured
  `slack.trusted_channel_id`

#### Scenario: An explicit channel is specified
- **WHEN** a `slack_notify` action specifies `channel: "#community"`
- **THEN** the message is posted to `#community` instead of the trusted
  channel

### Requirement: A notification's outcome is success, dry-run, or failure — never a no-op
A `slack_notify` action SHALL report `success` after a real post,
`dry_run` when dry-run mode is active (without calling the Slack API),
or `failure` on any Slack API error. It SHALL NOT report `no_change`,
since a notification has no prior state to compare against — "safe to
resend" is the only idempotency guarantee this action type makes.

#### Scenario: Normal operation
- **WHEN** dry-run mode is not active and the Slack API call succeeds
- **THEN** the action's result status is `success`

#### Scenario: Dry-run mode is active
- **WHEN** dry-run mode is active
- **THEN** the action does not call the Slack API, and its result
  status is `dry_run`

#### Scenario: The Slack API call fails
- **WHEN** the Slack API returns an error for the post attempt
- **THEN** the action's result status is `failure`

### Requirement: Permission or membership failures are logged with a troubleshooting hint
If a `slack_notify` post fails with a Slack error code indicating a
permission or channel-membership problem (`missing_scope`,
`not_in_channel`, or `channel_not_found`), the system SHALL log a message
naming the destination channel and stating that trustbot's token must be
authorized for `chat:write` and trustbot must be a member of that
channel. Any other Slack error code SHALL be logged without this hint.

#### Scenario: Bot is not a member of the destination channel
- **WHEN** a `slack_notify` post fails with error code `not_in_channel`
  for channel `#community`
- **THEN** the logged error names `#community` and states that
  trustbot's token must be authorized for `chat:write` and trustbot must
  be a member of that channel

#### Scenario: An unrelated Slack error occurs
- **WHEN** a `slack_notify` post fails with an error code other than
  `missing_scope`, `not_in_channel`, or `channel_not_found`
- **THEN** the logged error does not include the troubleshooting hint

### Requirement: Notification channel membership does not grant command privileges
Inviting trustbot into a channel so it can post notifications SHALL NOT
change which channel is authorized to issue `/trust`, `/trust-revoke`,
`/trust-status`, or `/trust-activity` — that authorization remains
governed solely by `slack.trusted_channel_id`, independent of which
channels the bot is a member of.

#### Scenario: A notification channel is not the trusted channel
- **WHEN** trustbot is a member of a channel (for posting notifications)
  that is not the configured `slack.trusted_channel_id`
- **THEN** a slash command issued from that channel is still rejected
  exactly as it would be from any other non-trusted channel
