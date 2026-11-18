# Design

## Context

Confirmed by reading the current code: `Action` (`src/engine/models.py`)
already has `model_config = ConfigDict(extra="allow")` with only `type:
str` declared, so any new YAML keys on an action block (e.g. `message:`,
`channel:`) are preserved on the `Action` instance with zero model
changes. `Rule.actions` is already `list[Action]`, and
`evaluator.execute_rule()` already iterates it in order, calling each
registered executor with the full `TriggerEvent` and catching any
exception as a generic `failure` — see proposal.md's Impact section.
`src/integrations/keycloak.py`'s `build_client()`/`set_client()`/
`get_client()` module-level-singleton pattern, and
`src/actions/keycloak.py`'s executor functions, are the concrete
templates this follows.

The existing Slack wiring (`src/integrations/slack.py`'s
`slack_bolt.App`) only ever runs inside a live slash-command request —
`ack()`/`respond()` depend on that request's context (a `response_url`,
a 3-second ack window). A `slack_notify` action fires from
`execute_rule()`, which runs for *any* matched rule regardless of
trigger — including a Discourse webhook/workflow POST, where there is no
Slack request in flight at all. This action needs its own Slack Web API
client, independent of `slack_bolt`.

## Goals / Non-Goals

**Goals:**
- A new `slack_notify` action type, registered the same way
  `keycloak_add_groups`/`keycloak_remove_groups` are.
- Reuse the existing `SLACK_BOT_TOKEN` — no new secret.
- Keep the engine core (`models.py`, `evaluator.py`, `loader.py`)
  untouched, per the project's stated extensibility goal.

**Non-Goals:**
- No changes to the slash-command flow (`src/integrations/slack.py`'s
  `App`, `ack()`/`respond()`) — this is a separate, independent client.
- No new config field for the destination channel's default — it
  reuses `config.yaml`'s existing `slack.trusted_channel_id`.
- No attempt at true idempotency (detecting and suppressing a duplicate
  notification) — out of scope; see the "safe to resend" framing in
  proposal.md.

## Decisions

### A standalone `src/integrations/slack_notify.py` client, not `app.client`
Two options: (a) reuse the existing `slack_bolt.App`'s underlying
`WebClient` via `app.client.chat_postMessage(...)`, or (b) a bare
`slack_sdk.WebClient(token=...)` in a new module, mirroring
`src/integrations/keycloak.py`'s `build_client()`/`set_client()`/
`get_client()` pattern.

Chose (b). The `App` instance is constructed and owned by
`create_slack_app()` inside `src/main.py`'s request-handling wiring;
reaching into it from an action module (which runs during rule
evaluation, possibly triggered by a Discourse webhook with no Slack
`App` request anywhere nearby) would couple an unrelated module to
slash-command internals for no benefit. A bare `WebClient` is the same
underlying HTTP client Slack Bolt uses internally, with none of the
request-scoped machinery, and matches this project's existing
multi-client pattern (Keycloak and Discourse already each get their own
`build_client()`/`set_client()`/`get_client()` module). `slack-sdk` is
already an installed transitive dependency of `slack-bolt` (confirmed:
`pip show slack-sdk` reports `3.44.1` already present) — it becomes a
direct dependency, pinned explicitly in `requirements.txt`.

### Template interpolation: `string.Template.substitute()`, not `safe_substitute()`
`action.message` is rendered via `string.Template(action.message)
.substitute(openmrs_id=event.openmrs_id)`. Chose strict `substitute()`
(raises `KeyError` on an unrecognized `${...}` placeholder) over
`safe_substitute()` (silently leaves an unrecognized placeholder as
literal text). A `rules.yaml` typo like `${usernme}` under
`safe_substitute()` would silently post a visibly broken message to the
whole channel with no failure recorded anywhere; under `substitute()`,
the action module catches the `KeyError` itself and returns
`ActionResult(status="failure", detail="Unknown template placeholder:
...")`, which fails loudly and shows up in the audit log, consistent
with this project's existing "fail loudly rather than silently do
nothing" convention (see CLAUDE.md's Discourse badge-event handling for
the precedent). Only `openmrs_id` is exposed as a placeholder for this
change — `TriggerEvent.source`/`.type`/`.name` are not, since nothing in
this proposal's two target rules (Discourse grant/revoke) needs them;
exposing more fields later is a backward-compatible addition.

### Destination channel resolution happens in the action, not the engine
`action.channel` (optional) is read directly off the `Action` instance;
when absent, the executor falls back to a module-level default read
from `src/integrations/slack_notify.py`. `register_action()` only ever
takes a plain function reference (`register_action("keycloak_add_groups",
keycloak.add_groups)` — no partial application, no extra args), so the
default channel can't be bound into the executor as a parameter at
registration time the way `create_slack_app()` takes
`trusted_channel_id` as an explicit argument (that's a one-time
constructor call in `src/main.py`, not a registry entry). Instead,
`src/integrations/slack_notify.py` gets a second module-level singleton
alongside the client — `set_default_channel(channel_id)` /
`get_default_channel()` — set once at startup in `src/main.py`
(`slack_notify_integration.set_default_channel(config.slack
.trusted_channel_id)`), mirroring `set_client()`/`get_client()`'s
existing pattern exactly. `src/actions/slack_notify.py`'s executor then
reads `action.channel or slack_notify_integration.get_default_channel()`
and never touches `config.yaml` directly, consistent with
`src/actions/keycloak.py` (which also never reads `config.yaml` — its
base URL/realm are baked into the client at `build_client()` time).

### Error classification for the troubleshooting hint
`slack_sdk.errors.SlackApiError`'s `.response["error"]` string is
checked against a fixed set (`{"missing_scope", "not_in_channel",
"channel_not_found"}`). A match logs the hint named in proposal.md; any
other code (`rate_limited`, `invalid_auth`, etc.) logs
`str(exc)` plus the destination channel, without the hint, since the
hint's specific remediation (check `chat:write` scope, check channel
membership) wouldn't apply and would be misleading.

### Dry-run: no Slack API call at all, not a "would post" simulation via a test endpoint
Mirrors `src/actions/keycloak.py`'s existing dry-run shape exactly: when
`dry_run=True`, the executor renders the message (so the audit log's
`detail` shows exactly what would have been sent) but returns before
calling `chat_postMessage`, returning `ActionResult(status="dry_run",
detail=f"Would post to {channel}: {rendered}")`. No real Slack call of
any kind is made, consistent with `dry-run-mode`'s existing "No external
system is mutated while dry-run is active" requirement, which already
covers this generically.

## Risks / Trade-offs

- **A broken `rules.yaml` template or missing channel membership could
  spam failures into the audit log on every Discourse trust-level
  change** → Each failure is still just one more `audit_log` row
  (`action="slack_notify", status="failure"`) and does not block the
  rule's other actions (`execute_rule()` already isolates each action's
  exceptions) — the Keycloak grant/revoke still happens even if the
  notification fails.
- **`string.Template.substitute()`'s strict behavior means a rules.yaml
  edit with a typo'd placeholder fails at runtime, not at `rules.yaml`
  load time** → Acceptable: `rules.yaml` has no schema-level validation
  of action-specific fields today (by design — `Action` is
  `extra="allow"`), and failing per-event (with a clear audit detail) is
  still much better than the alternative of a silently wrong message.
- **A second Slack client (separate token lifecycle from `slack_bolt`'s
  `App`) could drift out of sync if the bot token is rotated in only one
  place** → Both read the same `SLACK_BOT_TOKEN` environment variable at
  startup in `src/main.py`, so a rotation naturally applies to both; no
  separate secret to track.

## Migration Plan

No data migration. Deploy is additive: existing rules are unaffected
until `slack_notify` is added to `rules.yaml` (hot-reloaded, no restart
needed — `rules.yaml` is already re-read on every trigger event). The
new `src/integrations/slack_notify.py` client is wired up in
`src/main.py` at startup unconditionally (mirroring Keycloak/Discourse),
but is simply never invoked until a rule's `actions:` references
`slack_notify`. Rollback is reverting `rules.yaml` to drop the new
action — no code rollback required for that; a full code rollback (e.g.
reverting the release) is otherwise a normal deploy of a prior image.
