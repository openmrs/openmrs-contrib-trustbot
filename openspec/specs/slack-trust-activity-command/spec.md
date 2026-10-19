# slack-trust-activity-command Specification

## Purpose

Lets a trusted community member see a concise, human-readable feed of
trustbot's recent activity — Keycloak-group-mutating outcomes from
both Slack commands and Discourse triggers — via the read-only
`/trust-activity [<n>]` Slack command, without changing any state.

## Requirements

### Requirement: Slack request signature is verified before any processing
The system SHALL verify the Slack request signature (using the
configured signing secret) on every incoming `/trust-activity` command
before taking any other action, including before checking the source
channel.

#### Scenario: Invalid or missing signature
- **WHEN** a `/trust-activity` command request's signature does not
  validate against the configured Slack signing secret
- **THEN** the service rejects the request and takes no further action

### Requirement: Commands are restricted to the designated trusted channel
The system SHALL only act on `/trust-activity` commands issued from
the channel ID configured as `slack.trusted_channel_id`. Commands from
any other channel SHALL be rejected silently (no action is taken and
no response is sent) and logged at WARNING level or above.

#### Scenario: Command issued from an unauthorized channel
- **WHEN** a `/trust-activity` command is issued from a channel other
  than the configured trusted channel
- **THEN** the service takes no action, sends no response, and logs
  the rejection at WARNING level

### Requirement: The command never triggers rule evaluation
A `/trust-activity` command SHALL NOT be evaluated against
`rules.yaml` and SHALL NOT cause any action (Keycloak group changes or
otherwise) to be executed. It only reads and reports existing audit
history.

#### Scenario: Valid command from the trusted channel
- **WHEN** a `/trust-activity` command passes signature verification
  and is issued from the trusted channel
- **THEN** the system reads recent audit history and responds without
  evaluating any rule or executing any action

### Requirement: The response lists the most recent activity, newest first
The system SHALL respond with the `n` most recent `audit_log` rows
across all OpenMRS IDs, newest first, each rendered as a single
human-readable bulleted line (not raw data), posted in-channel,
visible to every member of the trusted channel — see the
`slack-response-visibility` capability.

#### Scenario: Activity exists
- **WHEN** an authorized `/trust-activity` command runs and `audit_log`
  has at least one row
- **THEN** the response lists up to `n` of the most recent rows,
  newest first, each as a human-readable line

#### Scenario: No activity yet
- **WHEN** an authorized `/trust-activity` command runs and
  `audit_log` is empty
- **THEN** the response states that there is no recorded activity yet

### Requirement: n defaults to config, is overridable, and is capped
`n` SHALL default to `config.yaml`'s `slack.default_log_length`
(default `10`) when the command is issued with no argument, SHALL be
overridable by a positive integer argument, and SHALL be capped at a
hard maximum of 50 — a request for more than 50 SHALL silently return
50 rather than erroring.

#### Scenario: No argument given
- **WHEN** `/trust-activity` is issued with no argument
- **THEN** the response includes up to `slack.default_log_length` rows

#### Scenario: A valid argument is given
- **WHEN** `/trust-activity 5` is issued
- **THEN** the response includes up to 5 rows

#### Scenario: An argument above the cap is given
- **WHEN** `/trust-activity 500` is issued
- **THEN** the response includes up to 50 rows, not 500, and no error
  is shown

### Requirement: An invalid argument is reported as a usage error
A `/trust-activity` argument that is not a positive integer SHALL
produce a usage-hint response rather than being silently ignored or
causing an error.

#### Scenario: A non-numeric argument is given
- **WHEN** `/trust-activity banana` is issued
- **THEN** the response states the correct usage, visible only to the
  issuing user

#### Scenario: A non-positive argument is given
- **WHEN** `/trust-activity 0` or `/trust-activity -5` is issued
- **THEN** the response states the correct usage, visible only to the
  issuing user

### Requirement: Each line is rendered according to its trigger and outcome
Each reported row SHALL be rendered as a short, human-readable line
reflecting its trigger type, action, and outcome status, prefixed with
its timestamp in the compact UTC format used elsewhere in the
service's logs. A row whose trigger or action is not one of the
recognized combinations SHALL still be rendered, using a generic
fallback phrasing that names the trigger, action, and status plainly,
rather than being dropped or causing an error.

#### Scenario: A Slack-issued grant succeeded
- **WHEN** a reported row has trigger `slack_trust_command`, action
  `keycloak_add_groups`, and status `success`
- **THEN** the line reads "{issuing Slack username} issued
  `/trust {openmrs-id}`"

#### Scenario: A Slack-issued grant found no change needed
- **WHEN** a reported row has trigger `slack_trust_command`, action
  `keycloak_add_groups`, and status `no_change`
- **THEN** the line states the command was issued and that the target
  was already trusted

#### Scenario: A Slack-issued grant was simulated (dry-run)
- **WHEN** a reported row has trigger `slack_trust_command`, action
  `keycloak_add_groups`, and status `dry_run`
- **THEN** the line reflects both the dry-run nature and that no real
  change was made

#### Scenario: A Slack-issued grant failed
- **WHEN** a reported row has trigger `slack_trust_command`, action
  `keycloak_add_groups`, and status `failure`
- **THEN** the line states the command was issued and includes the
  failure detail

#### Scenario: A Slack-issued revoke succeeded
- **WHEN** a reported row has trigger `slack_revoke_command`, action
  `keycloak_remove_groups`, and status `success`
- **THEN** the line reads "{issuing Slack username} issued
  `/trust-revoke {openmrs-id}`"

#### Scenario: A Discourse-triggered grant succeeded
- **WHEN** a reported row has trigger `webhook` or `workflow`, action
  `keycloak_add_groups`, and status `success`
- **THEN** the line reads "Discourse trusted {openmrs-id}", without
  naming a specific webhook or workflow (that detail is not captured
  by the audit log today)

#### Scenario: A Discourse-triggered revoke succeeded
- **WHEN** a reported row has trigger `webhook` or `workflow`, action
  `keycloak_remove_groups`, and status `success`
- **THEN** the line reads "Discourse revoked trust for {openmrs-id}"

#### Scenario: A row's trigger or action is not one of the recognized combinations
- **WHEN** a reported row's trigger/action combination has no
  dedicated phrasing
- **THEN** the line still renders, plainly naming the trigger, action,
  and status rather than being omitted or causing an error
