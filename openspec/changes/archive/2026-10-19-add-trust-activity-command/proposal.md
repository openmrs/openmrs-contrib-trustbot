# Proposal

## Why

Operators have no quick way to see what trustbot has recently done.
`/trust-status` reports one user's history; there's nothing that shows
the last several actions across everyone. Raw log access was
considered and ruled out: the running process cannot read back its own
past stdout output (Docker captures it outside the container, with
nothing mounted in), and adding a new table just to also surface
"no rule matched"/"`/trust-status` looked up" events was judged not
worth the complexity for this feature. The existing `audit_log` table
already has everything needed to answer "what has trustbot actually
changed lately" — Keycloak-group-mutating rule outcomes from both
Slack and Discourse triggers — just not in a form anyone has queried
globally or rendered for humans yet.

## What Changes

- New Slack slash command `/trust-activity [<n>]`: posts, in-channel, a
  bulleted list of the last `n` `audit_log` rows across all users,
  newest first, each rendered as a short human-readable line instead
  of raw data.
- `n` defaults to a new `slack.default_log_length` config field
  (default `10`), overridable per-invocation by the command's
  argument, capped at a hard safety maximum of 50 (a larger request
  silently returns 50 rather than erroring).
- A non-numeric or non-positive argument is an invalid-usage error,
  ephemeral — mirroring `/trust`, `/trust-revoke`, and
  `/trust-status`'s existing "Usage: ..." pattern.
- Each line is prefixed with the compact UTC timestamp
  (`YYMMDD HH:MM:SS`, matching the rest of the service's logs) and
  phrased according to the row's trigger and action — see design.md
  for the full phrasing table, confirmed with the user.
- Like `/trust-status`, this command never reaches the rules engine
  and performs no mutation of any kind — purely a read of existing
  audit data.

## Capabilities

### New Capabilities

- `slack-trust-activity-command`: the `/trust-activity` command's
  authorization, argument handling, and human-readable rendering of
  recent `audit_log` activity.

### Modified Capabilities

- `slack-command-rate-limiting`: the shared per-user command rate
  limit now explicitly lists `/trust-activity` alongside the other
  three commands (no code change — the rate-limit middleware is
  already registered once at the `App` level, not per-command, so
  this is a documentation-accuracy update, not a behavior change).
- `slack-response-visibility`: "Result messages are posted in-channel"
  gains a scenario for `/trust-activity`'s main response. The normative
  text of "usage hints remain ephemeral" already covers
  `/trust-activity`'s invalid-usage error without any change, since
  it's written generically (not naming specific commands) — but its
  illustrative scenario does name the other three commands, so that
  scenario's command list is updated to include `/trust-activity` too,
  rather than quietly going stale.

## Impact

- **Code**: `src/audit/db.py` (new `get_recent_activity(conn, limit)`
  query, global across all OpenMRS IDs — the existing
  `get_recent_events()` is per-user and stays unchanged),
  `src/config.py` (`SlackConfig` gains `default_log_length: int = 10`),
  `src/integrations/slack.py` (new command registration, handler, and
  formatter, following the same shape as `/trust-status`'s).
- **Tests**: unit tests for the new formatter covering every
  trigger/action/status combination in the phrasing table plus the
  generic fallback for anything not covered; integration tests for the
  handler (default length, explicit length, over-cap length, invalid
  argument, wrong channel) mirroring the existing `/trust-status`
  integration tests.
- **Docs, as plain tasks (not spec deltas)**:
  `openspec/specs/config-schema.md` and `config/config.example.yaml`
  document `slack.default_log_length`; `openspec/specs/overview.md`
  §5.3 adds `/trust-activity` to the registered-commands list;
  `README.md` and `CLAUDE.md` mention the new command.
- **Out of scope**: no new database table, no raw log/stdout access,
  no capture of which specific Discourse workflow/webhook fired
  (Discourse-originated lines stay generic, e.g. "Discourse trusted
  `foobar`" — deliberately deferred, see design.md).
