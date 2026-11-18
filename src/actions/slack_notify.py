"""The `slack_notify` action.

Posts a templated message to Slack when a rule fires. Unlike
keycloak_add_groups/keycloak_remove_groups, this action has no "already
done" state to check against -- a notification can't be no-op'd, only
sent, simulated (dry-run), or failed to send. "Idempotent" here means
"safe to resend," not "no duplicate posts" (see
add-slack-notify-action design.md).
"""

from __future__ import annotations

import logging
from string import Template

from slack_sdk.errors import SlackApiError

from src.engine.models import Action, ActionResult, TriggerEvent
from src.integrations import slack_notify as slack_notify_integration

logger = logging.getLogger(__name__)

# Slack error codes indicating a permission/membership problem, where the
# troubleshooting hint actually applies -- see proposal.md.
_PERMISSION_ERROR_CODES = {"missing_scope", "not_in_channel", "channel_not_found"}


def notify(action: Action, event: TriggerEvent, dry_run: bool = False) -> ActionResult:
    """Post action.message (with ${openmrs_id} interpolated) to action.channel or the default channel.

    Raises no exception that would reach the engine's generic handler
    for an unrecognized template placeholder -- that's caught here and
    turned into a clear failure detail instead (see design.md's
    "Template interpolation" decision).
    """
    channel = getattr(action, "channel", None) or slack_notify_integration.get_default_channel()

    try:
        rendered = Template(action.message).substitute(openmrs_id=event.openmrs_id)
    except KeyError as exc:
        return ActionResult(status="failure", detail=f"Unknown template placeholder: {exc}")

    if dry_run:
        return ActionResult(status="dry_run", detail=f"Would post to {channel}: {rendered}")

    try:
        slack_notify_integration.get_client().chat_postMessage(channel=channel, text=rendered)
    except SlackApiError as exc:
        error_code = exc.response.get("error") if exc.response is not None else None
        if error_code in _PERMISSION_ERROR_CODES:
            logger.error(
                "Failed to post Slack notification to %s: %s. Be sure trustbot's API "
                "token is authorized for chat:write and trustbot is a member of the "
                "%s channel.",
                channel,
                error_code,
                channel,
            )
        else:
            logger.error("Failed to post Slack notification to %s: %s", channel, exc)
        return ActionResult(status="failure", detail=f"Slack API error: {error_code or exc}")

    return ActionResult(status="success", detail=f"Posted to {channel}: {rendered}")
