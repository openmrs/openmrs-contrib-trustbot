# Spec Delta

## MODIFIED Requirements

### Requirement: The response reports current access and recent history
For a target OpenMRS ID that exists in Keycloak, the system SHALL respond
in Slack with: the OpenMRS ID, its current Keycloak group memberships
(the community-access-relevant groups), its current Discourse trust
level, and a summary of its most recent audit log entries (action,
trigger, timestamp, and outcome). This response is posted in-channel,
visible to every member of the trusted channel, not only the issuing
user — see the `slack-response-visibility` capability.

#### Scenario: Status requested for an existing user
- **WHEN** a `/trust-status <openmrs-id>` command passes authorization
  checks and the target OpenMRS ID exists in Keycloak
- **THEN** the response includes the OpenMRS ID, its current Keycloak
  group memberships, its current Discourse trust level, and a summary of
  its most recent audit log entries

### Requirement: Unknown OpenMRS ID is reported clearly
If the target OpenMRS ID does not exist in Keycloak, the system SHALL
respond with a message identifying that the user was not found, rather
than an empty or misleading status. This response is posted in-channel,
visible to every member of the trusted channel, not only the issuing
user — see the `slack-response-visibility` capability.

#### Scenario: Target OpenMRS ID does not exist
- **WHEN** a `/trust-status <openmrs-id>` command passes authorization
  checks and the target OpenMRS ID does not exist in Keycloak
- **THEN** the response states that the OpenMRS ID was not found
