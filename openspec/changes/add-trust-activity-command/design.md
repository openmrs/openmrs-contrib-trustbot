# Design

## Context

Two architectural options were considered and ruled out before this
design, in conversation with the user:

1. **Reading back the service's own stdout/log output.** Not
   possible: Docker captures container stdout outside the container
   (its own log storage on the host), and nothing is mounted in that
   would let the running process read it back. `docker-compose.yml`
   only mounts `/config` (read-only) and `/data`.
2. **A new database table capturing every action-outcome INFO line**
   (including "no rule matched" and "`/trust-status` checked" events,
   which `audit_log` deliberately does not record). Judged not worth
   the added complexity for this feature.

The existing `audit_log` table (already used by `/trust-status`'s
per-user history via `get_recent_events()`) is the only, and
sufficient, data source: `/trust-activity` reports only
Keycloak-group-mutating rule outcomes, which is exactly what
`audit_log` already records. See proposal.md for the full motivation.

## Goals / Non-Goals

**Goals:**
- `/trust-activity [<n>]`, mirroring `/trust-status`'s existing shape
  (inline channel check, no rules-engine involvement, in-channel
  response).
- Render each `audit_log` row as one short, human-readable line, not
  raw data.

**Non-Goals:**
- No new table, no stdout/log-file access, no capture of which
  specific Discourse webhook/workflow fired (Discourse rows stay
  generic — "Discourse trusted `foobar`" either way).
- No per-user filtering (that's `/trust-status`'s job) — this is the
  service-wide activity feed.

## Decisions

### Phrasing table (confirmed with the user)
Each line is `{timestamp} - {phrase}`, where `{timestamp}` is the
row's `audit_log.timestamp` (stored ISO 8601 UTC) reformatted to the
compact `YYMMDD HH:MM:SS` form used elsewhere in the service's logs,
and `{phrase}` is chosen by `(trigger, action, status)`:

| trigger | action | status | phrase |
|---|---|---|---|
| `slack_trust_command` | `keycloak_add_groups` | `success` | `` {src} issued `/trust {id}` `` |
| `slack_trust_command` | `keycloak_add_groups` | `no_change` | `` {src} issued `/trust {id}` (already trusted) `` |
| `slack_trust_command` | `keycloak_add_groups` | `dry_run` | `` {src} issued `/trust {id}` (dry run, no change) `` |
| `slack_trust_command` | `keycloak_add_groups` | `failure` | `` {src} issued `/trust {id}` (failed: {detail}) `` |
| `slack_revoke_command` | `keycloak_remove_groups` | `success` | `` {src} issued `/trust-revoke {id}` `` |
| `slack_revoke_command` | `keycloak_remove_groups` | `no_change` | `` {src} issued `/trust-revoke {id}` (already not trusted) `` |
| `slack_revoke_command` | `keycloak_remove_groups` | `dry_run` | `` {src} issued `/trust-revoke {id}` (dry run, no change) `` |
| `slack_revoke_command` | `keycloak_remove_groups` | `failure` | `` {src} issued `/trust-revoke {id}` (failed: {detail}) `` |
| `webhook` or `workflow` | `keycloak_add_groups` | `success` | `Discourse trusted {id}` |
| `webhook` or `workflow` | `keycloak_add_groups` | `no_change` | `Discourse found {id} already trusted` |
| `webhook` or `workflow` | `keycloak_add_groups` | `dry_run` | `Discourse would have trusted {id} (dry run, no change)` |
| `webhook` or `workflow` | `keycloak_add_groups` | `failure` | `Discourse failed to trust {id}: {detail}` |
| `webhook` or `workflow` | `keycloak_remove_groups` | `success` | `Discourse revoked trust for {id}` |
| `webhook` or `workflow` | `keycloak_remove_groups` | `no_change` | `Discourse found {id} already not trusted` |
| `webhook` or `workflow` | `keycloak_remove_groups` | `dry_run` | `Discourse would have revoked trust for {id} (dry run, no change)` |
| `webhook` or `workflow` | `keycloak_remove_groups` | `failure` | `Discourse failed to revoke trust for {id}: {detail}` |
| anything else | anything else | anything | `{trigger}/{action} for {id}: {status}` (generic fallback — never drop a row) |

`{src}` is `trigger_src` (the Slack username); `{id}` is `openmrs_id`;
`{detail}` is the row's `detail` column.

### Cap over-large requests rather than rejecting them
A request for more than 50 rows silently returns 50. It's still a
valid, meaningful response (just smaller than asked), so there's no
reason to make it an error — consistent with how action executors
already treat "already in the desired state" as success rather than
failure.

### New query function, not a reused one
`get_recent_events(conn, openmrs_id, limit)` is per-user and stays
exactly as it is (`/trust-status` depends on it). `/trust-activity`
needs a global, unfiltered query, so it gets its own function,
`get_recent_activity(conn, limit)`, which also selects `openmrs_id`
(the per-user query doesn't need to, since the caller already knows
which user it asked about).

## Risks / Trade-offs

- **Generic Discourse phrasing loses which specific workflow/webhook
  fired** → Accepted, deliberately: capturing that would need a schema
  change, and the generic phrasing is still informative (grant vs.
  revoke, which user, when).
- **The fallback phrasing for an unrecognized trigger/action is
  intentionally plain, not pretty** → Acceptable: it only fires for
  combinations that don't exist yet (e.g. a future action type), and
  "never drop a row" matters more than polish for a case that's not
  supposed to be common.
