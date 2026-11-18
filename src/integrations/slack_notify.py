"""Standalone Slack Web API client used by the `slack_notify` action (src/actions/slack_notify.py).

Decoupled from src/integrations/slack.py's slack_bolt.App, which only
ever runs inside a live slash-command request (ack()/respond() depend
on that request's context). slack_notify fires from rule evaluation,
which may be triggered by a Discourse webhook/workflow with no Slack
request in flight at all -- see add-slack-notify-action design.md.
"""

from __future__ import annotations

from slack_sdk import WebClient

_client: WebClient | None = None
_default_channel: str | None = None


def build_client(bot_token: str) -> WebClient:
    """Construct a new WebClient from the bot token."""
    return WebClient(token=bot_token)


def set_client(client: WebClient) -> None:
    """Install the module-level WebClient singleton used by src/actions/slack_notify.py.

    Called once at startup (see src/main.py) with a real client, or by
    tests to inject a fake/mock.
    """
    global _client
    _client = client


def get_client() -> WebClient:
    if _client is None:
        raise RuntimeError("Slack notify client not initialized; call set_client() at startup")
    return _client


def set_default_channel(channel_id: str) -> None:
    """Install the channel a `slack_notify` action posts to when it specifies no `channel`.

    Called once at startup (see src/main.py) with config.slack.trusted_channel_id.
    """
    global _default_channel
    _default_channel = channel_id


def get_default_channel() -> str:
    if _default_channel is None:
        raise RuntimeError(
            "Slack notify default channel not initialized; call set_default_channel() at startup"
        )
    return _default_channel
