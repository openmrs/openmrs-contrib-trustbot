# Spec Delta

## MODIFIED Requirements

### Requirement: Exceeding the limit produces a visible rejection
A Slack user who has exceeded the configured limit SHALL have their
command rejected before its normal authorization checks, with a visible
Slack response explaining they are rate limited — unlike the silent
rejection used for an unauthorized-channel command. This rejection
message is ephemeral, visible only to the rate-limited user — see the
`slack-response-visibility` capability.

#### Scenario: Slack user exceeds the configured limit
- **WHEN** a Slack user has already issued `max_requests` commands within
  the current `window_seconds` window
- **THEN** the service responds in Slack with a message indicating the
  user is rate limited, and does not evaluate the command against the
  rules engine or any read-only lookup
