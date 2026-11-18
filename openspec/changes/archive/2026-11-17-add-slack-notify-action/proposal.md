# Proposal

## Why

Discourse-triggered trust grants/revocations (and, in principle, any rule)
happen silently today — the only visibility is the audit log and the
`/trust-activity` Slack command, both of which require someone to go
looking. The community wants an announcement posted automatically (e.g.
to the trusted Slack channel) when `/`trust-activity`-worthy events like a
Discourse "trusted" grant or revoke actually happen, without anyone having
to poll for it.

## What Changes

- Add a new, generic `slack_notify` action type to the rules engine:
  `type: slack_notify`, a required `message:` template (`${openmrs_id}`
  interpolated from the firing `TriggerEvent`), and an optional `channel:`
  (Slack channel ID or `#name`) that defaults to `config.yaml`'s
  `slack.trusted_channel_id` when omitted.
- New standalone Slack Web API client wiring (`chat.postMessage`, reusing
  the existing `SLACK_BOT_TOKEN`) for posting outside any live Slack
  request context — the existing `slack_bolt.App`/`ack()`/`respond()`
  flow only applies to responding to an in-flight slash-command
  interaction, which this is not.
- `slack_notify` reports `status="success"` on a successful post,
  `"dry_run"` under dry-run mode (no real Slack call made), or
  `"failure"` on any Slack API error — there is no `no_change` outcome
  for this action type, since a notification has no "already done" state
  to check against; "idempotent" here means "safe to resend."
- A `chat.postMessage` failure whose Slack error code is
  `missing_scope`, `not_in_channel`, or `channel_not_found` is logged with
  an added troubleshooting hint naming the actual channel used.
- `config/rules.example.yaml` gains `slack_notify` as a second action on
  the two existing Discourse-triggered rules (grant and revoke), with
  comments documenting the `channel:` and `${openmrs_id}` options.
  `openspec/specs/config-schema.md` is updated to match.

## Capabilities

### New Capabilities
- `slack-notifications`: posting a templated, rule-triggered message to a
  Slack channel as a rules-engine action, independent of any live
  slash-command interaction.

### Modified Capabilities
(none — `dry-run-mode`'s existing "No external system is mutated while
dry-run is active" requirement already generically covers any action
type, including this one, with no wording change needed; confirmed by
reading its current text)

## Impact

- New file: a `slack_notify` action module under `src/actions/`,
  registered alongside `keycloak_add_groups`/`keycloak_remove_groups`.
- New file: standalone Slack Web API client wiring (new module or an
  addition to `src/integrations/`), decoupled from
  `src/integrations/slack.py`'s `slack_bolt.App`.
- No changes to `src/engine/models.py`, `src/engine/evaluator.py`, or
  `src/engine/loader.py` — `Action` already allows arbitrary extra YAML
  fields and `Rule.actions` already supports more than one action per
  rule.
- `config/rules.example.yaml` and `openspec/specs/config-schema.md`
  updated with the new action type and its fields.
- No new secrets: reuses `SLACK_BOT_TOKEN`, now scoped with `chat:write`.
- No audit schema change: `audit_log`'s columns are already
  action-type-agnostic.
