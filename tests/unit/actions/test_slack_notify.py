import logging
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from src.actions.slack_notify import notify
from src.engine.models import Action, TriggerEvent
from src.integrations import slack_notify as slack_notify_integration


@pytest.fixture(autouse=True)
def reset_module_state():
    slack_notify_integration.set_default_channel("C_DEFAULT")
    yield
    slack_notify_integration._client = None
    slack_notify_integration._default_channel = None


def make_event(openmrs_id="jdoe"):
    return TriggerEvent(type="workflow", name="trusted", openmrs_id=openmrs_id)


def make_action(message="${openmrs_id} trusted by OpenMRS Talk", channel=None):
    kwargs = {"type": "slack_notify", "message": message}
    if channel is not None:
        kwargs["channel"] = channel
    return Action(**kwargs)


def test_renders_openmrs_id_and_posts_to_default_channel():
    client = MagicMock()
    slack_notify_integration.set_client(client)

    result = notify(make_action(), make_event("jdoe"))

    client.chat_postMessage.assert_called_once_with(
        channel="C_DEFAULT", text="jdoe trusted by OpenMRS Talk"
    )
    assert result.status == "success"


def test_explicit_channel_overrides_default():
    client = MagicMock()
    slack_notify_integration.set_client(client)

    notify(make_action(channel="#community"), make_event("jdoe"))

    client.chat_postMessage.assert_called_once_with(
        channel="#community", text="jdoe trusted by OpenMRS Talk"
    )


def test_unknown_placeholder_fails_without_calling_slack():
    client = MagicMock()
    slack_notify_integration.set_client(client)

    result = notify(make_action(message="${bogus} trusted"), make_event("jdoe"))

    assert result.status == "failure"
    assert "bogus" in result.detail
    client.chat_postMessage.assert_not_called()


def test_dry_run_does_not_call_slack():
    client = MagicMock()
    slack_notify_integration.set_client(client)

    result = notify(make_action(), make_event("jdoe"), dry_run=True)

    client.chat_postMessage.assert_not_called()
    assert result.status == "dry_run"
    assert "jdoe trusted by OpenMRS Talk" in result.detail


def test_permission_error_logs_troubleshooting_hint(caplog):
    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "not_in_channel", {"error": "not_in_channel"}
    )
    slack_notify_integration.set_client(client)

    with caplog.at_level(logging.ERROR):
        result = notify(make_action(channel="#community"), make_event("jdoe"))

    assert result.status == "failure"
    assert any(
        "chat:write" in r.message and "#community" in r.message for r in caplog.records
    )


def test_unrelated_error_does_not_log_hint(caplog):
    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "rate_limited", {"error": "rate_limited"}
    )
    slack_notify_integration.set_client(client)

    with caplog.at_level(logging.ERROR):
        result = notify(make_action(), make_event("jdoe"))

    assert result.status == "failure"
    assert not any("chat:write" in r.message for r in caplog.records)


def test_registered_in_action_executors():
    from src.actions import register_all
    from src.engine.evaluator import ACTION_EXECUTORS

    register_all()

    assert ACTION_EXECUTORS["slack_notify"] is notify
