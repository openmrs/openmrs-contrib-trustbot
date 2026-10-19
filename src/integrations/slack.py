"""Slack client/app setup (built on slack-bolt).

Registers the `/trust`, `/trust-revoke`, `/trust-status`, and
`/trust-activity` slash commands and relies on slack-bolt's own signature
verification (SLACK_SIGNING_SECRET, checked by the App/SlackRequestHandler
before any listener runs — see the add-slack-trust-grant design.md) and
posting responses back to Slack (SLACK_BOT_TOKEN). `/trust` and
`/trust-revoke`'s channel-restriction enforcement and TriggerEvent
construction live in src/triggers/slack.py; rule loading and dispatch
live in src/engine/loader.py and src/engine/evaluator.py.
`/trust-status` and `/trust-activity` are both read-only and never reach
the rules engine — see their handlers below and the
add-slack-trust-status-command design.md for why their channel checks are
inline here rather than routed through src/triggers/slack.py. This module
wires all four together behind their command listeners.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from slack_bolt import App

from src.audit.db import get_recent_activity, get_recent_events
from src.engine import evaluator
from src.engine.loader import load_rules
from src.engine.models import ActionResult
from src.integrations import discourse as discourse_integration
from src.integrations import keycloak as keycloak_integration
from src.integrations.keycloak import UserNotFoundError
from src.logging_setup import redact_headers, redact_slack_body
from src.ratelimit import RateLimiter
from src.triggers.slack import build_revoke_event, build_trust_event

logger = logging.getLogger(__name__)

RATE_LIMITED_MESSAGE = "You are sending commands too quickly. Please wait a moment and try again."
MAX_ACTIVITY_LENGTH = 50


@dataclass
class SlackContext:
    """Per-app-instance context the `/trust` handler needs beyond the Slack payload itself."""

    trusted_channel_id: str
    audit_conn: sqlite3.Connection
    dry_run: bool = False
    default_log_length: int = 10


def create_slack_app(
    bot_token: str,
    signing_secret: str,
    *,
    trusted_channel_id: str,
    audit_conn: sqlite3.Connection,
    rate_limiter: RateLimiter,
    dry_run: bool = False,
    default_log_length: int = 10,
) -> App:
    """Construct and return the configured slack_bolt App with the `/trust` command registered."""
    # token_verification_enabled=False: skip the eager `auth.test` network
    # call slack-bolt otherwise makes at construction time. Per-request
    # signature verification (the actual security control) still happens
    # via signing_secret on every incoming request. Disabling this means
    # the service can start without live Slack connectivity/credentials
    # (e.g. local dev, or Slack being briefly unreachable at boot).
    app = App(token=bot_token, signing_secret=signing_secret, token_verification_enabled=False)
    context = SlackContext(
        trusted_channel_id=trusted_channel_id,
        audit_conn=audit_conn,
        dry_run=dry_run,
        default_log_length=default_log_length,
    )

    @app.use
    def rate_limit_middleware(body, next, ack, request):
        logger.debug(
            "received command: headers=%s body=%s",
            redact_headers(dict(request.headers)),
            redact_slack_body(body),
        )

        user_id = body.get("user_id")
        if not rate_limiter.is_allowed(user_id):
            logger.warning("Slack command rate limit exceeded for user %s", user_id)
            return ack(text=RATE_LIMITED_MESSAGE)
        return next()

    @app.command("/trust")
    def handle_trust_command(ack, command, respond) -> None:
        # Ack immediately: Slack requires a response within 3 seconds, and
        # per the "silent rejection" design decision this ack (with no
        # text) is what satisfies that for an unauthorized-channel command
        # without showing the channel anything.
        ack()
        _handle_trust(command, context, respond)

    @app.command("/trust-revoke")
    def handle_revoke_command(ack, command, respond) -> None:
        ack()  # same silent-rejection rationale as /trust, see above
        _handle_revoke(command, context, respond)

    @app.command("/trust-status")
    def handle_trust_status_command(ack, command, respond) -> None:
        ack()  # same silent-rejection rationale as /trust, see above
        _handle_trust_status(command, context, respond)

    @app.command("/trust-activity")
    def handle_trust_activity_command(ack, command, respond) -> None:
        ack()  # same silent-rejection rationale as /trust, see above
        _handle_trust_activity(command, context, respond)

    return app


def _handle_trust(command: dict, context: SlackContext, respond) -> None:
    event = build_trust_event(command, trusted_channel_id=context.trusted_channel_id)
    if event is None:
        logger.warning(
            "/trust rejected: wrong channel (user %s, channel %s)",
            command.get("user_id"),
            command.get("channel_id"),
        )
        return  # wrong channel: silent rejection, no response (see build_trust_event)

    if not event.openmrs_id:
        respond("Usage: `/trust <openmrs-id>`")
        return

    rule_set = load_rules()
    matched_rules = evaluator.evaluate(rule_set, event)

    if not matched_rules:
        respond(
            f"No rule is configured to handle `/trust` for `{event.openmrs_id}`.",
            response_type="in_channel",
        )
        return

    outcomes: list[ActionResult] = []
    for rule in matched_rules:
        outcomes.extend(
            evaluator.execute_rule(rule, event, conn=context.audit_conn, dry_run=context.dry_run)
        )

    respond(_format_response(event.openmrs_id, outcomes), response_type="in_channel")


def _format_response(openmrs_id: str, outcomes: Sequence[ActionResult]) -> str:
    failures = [o for o in outcomes if o.status == "failure"]
    if failures:
        return f"Could not grant access to `{openmrs_id}`: {failures[0].detail}"

    if all(o.status == "dry_run" for o in outcomes):
        return f"[DRY RUN] `{openmrs_id}` would be granted community edit access. No change was made."

    if all(o.status == "no_change" for o in outcomes):
        return f"`{openmrs_id}` is already trusted."

    return f"`{openmrs_id}` has been granted community edit access."


def _handle_revoke(command: dict, context: SlackContext, respond) -> None:
    event = build_revoke_event(command, trusted_channel_id=context.trusted_channel_id)
    if event is None:
        logger.warning(
            "/trust-revoke rejected: wrong channel (user %s, channel %s)",
            command.get("user_id"),
            command.get("channel_id"),
        )
        return  # wrong channel: silent rejection, no response (see build_revoke_event)

    if not event.openmrs_id:
        respond("Usage: `/trust-revoke <openmrs-id>`")
        return

    rule_set = load_rules()
    matched_rules = evaluator.evaluate(rule_set, event)

    if not matched_rules:
        respond(
            f"No rule is configured to handle `/trust-revoke` for `{event.openmrs_id}`.",
            response_type="in_channel",
        )
        return

    outcomes: list[ActionResult] = []
    for rule in matched_rules:
        outcomes.extend(
            evaluator.execute_rule(rule, event, conn=context.audit_conn, dry_run=context.dry_run)
        )

    respond(_format_revoke_response(event.openmrs_id, outcomes), response_type="in_channel")


def _format_revoke_response(openmrs_id: str, outcomes: Sequence[ActionResult]) -> str:
    failures = [o for o in outcomes if o.status == "failure"]
    if failures:
        return f"Could not revoke access for `{openmrs_id}`: {failures[0].detail}"

    if all(o.status == "dry_run" for o in outcomes):
        return f"[DRY RUN] `{openmrs_id}` would have community edit access revoked. No change was made."

    if all(o.status == "no_change" for o in outcomes):
        return f"`{openmrs_id}` is already not trusted."

    return f"`{openmrs_id}` has had community edit access revoked."


def _handle_trust_status(command: dict, context: SlackContext, respond) -> None:
    # No TriggerEvent here (unlike /trust and /trust-revoke): this command never
    # reaches the rules engine, so the channel check is done inline rather
    # than through src/triggers/slack.py's build_*_event() — see design.md.
    if command.get("channel_id") != context.trusted_channel_id:
        logger.warning(
            "/trust-status rejected: wrong channel (user %s, channel %s)",
            command.get("user_id"),
            command.get("channel_id"),
        )
        return  # wrong channel: silent rejection, no response

    openmrs_id = (command.get("text") or "").strip()
    if not openmrs_id:
        respond("Usage: `/trust-status <openmrs-id>`")
        return

    groups: list[str] | None
    groups_error: str | None
    try:
        groups = keycloak_integration.get_client().get_user_groups(openmrs_id)
        groups_error = None
    except UserNotFoundError:
        respond(f"`{openmrs_id}` was not found in Keycloak.", response_type="in_channel")
        return
    except Exception as exc:  # noqa: BLE001 - degrade this section, see design.md
        groups = None
        groups_error = str(exc)

    trust_level: int | None
    trust_level_error: str | None
    try:
        trust_level = discourse_integration.get_client().get_trust_level(openmrs_id)
        trust_level_error = None
    except Exception as exc:  # noqa: BLE001 - degrade this section, see design.md
        trust_level = None
        trust_level_error = str(exc)

    recent_events: list[dict] | None
    events_error: str | None
    try:
        recent_events = get_recent_events(context.audit_conn, openmrs_id, limit=5)
        events_error = None
    except Exception as exc:  # noqa: BLE001 - degrade this section, see design.md
        recent_events = None
        events_error = str(exc)

    degraded = [
        section
        for section, error in (
            ("groups", groups_error),
            ("trust_level", trust_level_error),
            ("recent_events", events_error),
        )
        if error is not None
    ]
    logger.info(
        "trust-status checked: user=%s openmrs_id=%s degraded=%s",
        command.get("user_name"),
        openmrs_id,
        degraded or "none",
    )

    respond(
        _format_trust_status_response(
            openmrs_id,
            groups=groups,
            groups_error=groups_error,
            trust_level=trust_level,
            trust_level_error=trust_level_error,
            recent_events=recent_events,
            events_error=events_error,
        ),
        response_type="in_channel",
    )


def _format_trust_status_response(
    openmrs_id: str,
    *,
    groups: list[str] | None,
    groups_error: str | None,
    trust_level: int | None,
    trust_level_error: str | None,
    recent_events: list[dict] | None,
    events_error: str | None,
) -> str:
    lines = [f"*Trust status for* `{openmrs_id}`"]

    if groups_error is not None:
        lines.append(f"- Keycloak groups: unavailable ({groups_error})")
    else:
        lines.append(f"- Keycloak groups: {', '.join(groups) if groups else '(none)'}")

    if trust_level_error is not None:
        lines.append(f"- Discourse trust level: unavailable ({trust_level_error})")
    else:
        lines.append(f"- Discourse trust level: {trust_level}")

    if events_error is not None:
        lines.append(f"- Recent audit history: unavailable ({events_error})")
    elif not recent_events:
        lines.append("- Recent audit history: (none)")
    else:
        lines.append("- Recent audit history:")
        for event in recent_events:
            lines.append(
                f"   - {event['timestamp']}: {event['action']} via "
                f"{event['trigger']} -> {event['status']}"
            )

    return "\n".join(lines)


def _handle_trust_activity(command: dict, context: SlackContext, respond) -> None:
    # No TriggerEvent here (unlike /trust and /trust-revoke): this command
    # never reaches the rules engine, so the channel check is done inline --
    # same rationale as /trust-status, see its design.md.
    if command.get("channel_id") != context.trusted_channel_id:
        logger.warning(
            "/trust-activity rejected: wrong channel (user %s, channel %s)",
            command.get("user_id"),
            command.get("channel_id"),
        )
        return  # wrong channel: silent rejection, no response

    text = (command.get("text") or "").strip()
    if text:
        if not text.isdigit() or int(text) <= 0:
            respond("Usage: `/trust-activity [<n>]` (n must be a positive whole number)")
            return
        limit = int(text)
    else:
        limit = context.default_log_length

    limit = min(limit, MAX_ACTIVITY_LENGTH)

    rows = get_recent_activity(context.audit_conn, limit=limit)

    respond(_format_activity_response(rows), response_type="in_channel")


def _format_activity_response(rows: Sequence[dict]) -> str:
    if not rows:
        return "No recorded activity yet."
    return "\n".join(f"- {_format_activity_line(row)}" for row in rows)


def _format_activity_line(row: dict) -> str:
    timestamp = datetime.fromisoformat(row["timestamp"]).strftime("%y%m%d %H:%M:%S")
    return f"{timestamp} - {_format_activity_phrase(row)}"


def _format_activity_phrase(row: dict) -> str:
    """Render one audit_log row per the phrasing table in design.md.

    Falls back to a plain, generic phrase for any (trigger, action)
    combination not explicitly covered, so a row is never dropped just
    because a future trigger/action type hasn't been special-cased yet.
    """
    trigger = row["trigger"]
    action = row["action"]
    status = row["status"]
    openmrs_id = row["openmrs_id"]
    src = row["trigger_src"]
    detail = row["detail"]

    if trigger == "slack_trust_command" and action == "keycloak_add_groups":
        issued = f"{src} issued `/trust {openmrs_id}`"
        return {
            "success": issued,
            "no_change": f"{issued} (already trusted)",
            "dry_run": f"{issued} (dry run, no change)",
            "failure": f"{issued} (failed: {detail})",
        }.get(status, f"{issued} ({status})")

    if trigger == "slack_revoke_command" and action == "keycloak_remove_groups":
        issued = f"{src} issued `/trust-revoke {openmrs_id}`"
        return {
            "success": issued,
            "no_change": f"{issued} (already not trusted)",
            "dry_run": f"{issued} (dry run, no change)",
            "failure": f"{issued} (failed: {detail})",
        }.get(status, f"{issued} ({status})")

    if trigger in ("webhook", "workflow") and action == "keycloak_add_groups":
        return {
            "success": f"Discourse trusted {openmrs_id}",
            "no_change": f"Discourse found {openmrs_id} already trusted",
            "dry_run": f"Discourse would have trusted {openmrs_id} (dry run, no change)",
            "failure": f"Discourse failed to trust {openmrs_id}: {detail}",
        }.get(status, f"Discourse {action} for {openmrs_id}: {status}")

    if trigger in ("webhook", "workflow") and action == "keycloak_remove_groups":
        return {
            "success": f"Discourse revoked trust for {openmrs_id}",
            "no_change": f"Discourse found {openmrs_id} already not trusted",
            "dry_run": f"Discourse would have revoked trust for {openmrs_id} (dry run, no change)",
            "failure": f"Discourse failed to revoke trust for {openmrs_id}: {detail}",
        }.get(status, f"Discourse {action} for {openmrs_id}: {status}")

    # Generic fallback -- never drop a row for an unrecognized combination.
    return f"{trigger}/{action} for {openmrs_id}: {status}"
