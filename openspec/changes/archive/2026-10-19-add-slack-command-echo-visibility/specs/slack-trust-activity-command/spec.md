# Spec Delta

## MODIFIED Requirements

### Requirement: The response lists the most recent activity, newest first
The system SHALL respond with the `n` most recent `audit_log` rows
across all OpenMRS IDs, newest first, each rendered as a single
human-readable bulleted line (not raw data), posted in-channel,
visible to every member of the trusted channel — see the
`slack-response-visibility` capability, whose immediate-acknowledgment
requirement also makes the command invocation itself visible to the
channel for every such command.

#### Scenario: Activity exists
- **WHEN** an authorized `/trust-activity` command runs and `audit_log`
  has at least one row
- **THEN** the response lists up to `n` of the most recent rows,
  newest first, each as a human-readable line

#### Scenario: No activity yet
- **WHEN** an authorized `/trust-activity` command runs and
  `audit_log` is empty
- **THEN** the response states that there is no recorded activity yet
