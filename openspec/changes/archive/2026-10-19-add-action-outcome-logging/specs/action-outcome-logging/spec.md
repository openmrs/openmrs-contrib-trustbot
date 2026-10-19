# Spec Delta

## Purpose

Makes every decision the rules engine makes — and the read-only
`/trust-status` lookup — visible at INFO level (the production
default): who or what triggered it, the target OpenMRS ID, and the
outcome, without requiring DEBUG to be enabled.

## ADDED Requirements

### Requirement: Every attempted action is logged at INFO with source, target, and outcome
For every action a matched rule attempts, the system SHALL log, at
INFO level, the triggering event's source (the issuing Slack username
for a Slack command, or the Discourse webhook/workflow name for a
Discourse-originated event), the target OpenMRS ID, the matched rule's
action type, and the resulting outcome status
(`success`/`no_change`/`failure`/`dry_run`).

#### Scenario: A Slack command successfully changes access
- **WHEN** a `/trust` or `/trust-revoke` command passes authorization,
  matches an enabled rule, and that rule's action completes with
  status `success`
- **THEN** an INFO-level log entry identifies the issuing Slack
  username, the target OpenMRS ID, the action type, and the `success`
  status

#### Scenario: A Discourse webhook or workflow results in no change
- **WHEN** a Discourse webhook or workflow event matches an enabled
  rule and that rule's action completes with status `no_change`
- **THEN** an INFO-level log entry identifies the webhook/workflow
  name, the target OpenMRS ID, the action type, and the `no_change`
  status

#### Scenario: An action fails
- **WHEN** a matched rule's action completes with status `failure`
- **THEN** an INFO-level log entry identifies the triggering source,
  the target OpenMRS ID, the action type, and the `failure` status

#### Scenario: Dry-run mode is active
- **WHEN** a matched rule's action completes with status `dry_run`
- **THEN** an INFO-level log entry identifies the triggering source,
  the target OpenMRS ID, the action type, and the `dry_run` status

### Requirement: A parsed event or authorized command that matches no rule is logged at INFO
When a validly-parsed Discourse webhook/workflow event, or an
authorized Slack `/trust`/`/trust-revoke` command, matches zero enabled
rules, the system SHALL log an INFO-level entry identifying the
triggering source and the target OpenMRS ID, stating that no rule
matched — rather than producing no log output at INFO.

#### Scenario: A Slack command has no configured rule
- **WHEN** an authorized `/trust` command's target OpenMRS ID is
  resolved but no enabled rule's trigger matches `slack_trust_command`
- **THEN** an INFO-level log entry identifies the issuing Slack
  username and the target OpenMRS ID, and states that no rule matched

#### Scenario: A Discourse workflow name has no configured rule
- **WHEN** a Discourse workflow event is successfully parsed (its
  OpenMRS ID is resolved) but no enabled rule references that workflow
  name
- **THEN** an INFO-level log entry identifies the workflow name and
  the target OpenMRS ID, and states that no rule matched

### Requirement: An unrecognized Discourse webhook event name remains silent
A native Discourse webhook event name with no registered parser SHALL
continue to produce no log output beyond what already exists today —
this requirement does not add any new log line for that case, since no
OpenMRS ID is ever resolved for it and nothing was actionable.

#### Scenario: Discourse sends an event type with no registered parser
- **WHEN** a native Discourse webhook request's `X-Discourse-Event`
  name has no registered parser in `src/triggers/discourse_webhook.py`
- **THEN** the request is acknowledged with HTTP 200 and no
  action-outcome log entry is produced for it

### Requirement: /trust-status logs its own outcome at INFO
Since `/trust-status` never reaches the rules engine, the system SHALL
separately log, at INFO level, the issuing Slack username, the target
OpenMRS ID, and whether each of its three sections (Keycloak groups,
Discourse trust level, recent audit history) succeeded or degraded.

#### Scenario: All sections succeed
- **WHEN** an authorized `/trust-status` command successfully reads
  Keycloak groups, Discourse trust level, and recent audit history
- **THEN** an INFO-level log entry identifies the issuing Slack
  username, the target OpenMRS ID, and that all three sections
  succeeded

#### Scenario: A section degrades
- **WHEN** an authorized `/trust-status` command completes but one or
  more of its three sections fails (e.g. Keycloak is unreachable)
- **THEN** an INFO-level log entry identifies the issuing Slack
  username, the target OpenMRS ID, and which section(s) degraded
