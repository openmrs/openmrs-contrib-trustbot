"""The immediate acknowledgment's own response_type for all four Slack commands.

Slack only reveals the invoking command itself (the "username used
/command args" line) when the IMMEDIATE acknowledgment to the initial
POST carries response_type: "in_channel" -- not when only a later,
delayed response to response_url does (see the
add-slack-command-echo-visibility design.md). This exercises each
registered listener's ack_function directly (app._listeners[i].ack_function),
the same "reach into the registered object and call it with
manually-constructed kwargs" approach test_slack_rate_limiting.py already
uses for the middleware function -- bypassing slack-bolt's HTTP/signature
layer, out of scope here and already covered by test_slack.py.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audit.db import get_connection
from src.integrations import discourse as discourse_integration
from src.integrations import keycloak as keycloak_integration
from src.integrations.slack import create_slack_app
from src.ratelimit import RateLimiter

EXAMPLE_RULES = Path(__file__).parents[2] / "config" / "rules.example.yaml"
TRUSTED_CHANNEL = "C0123456789"
OTHER_CHANNEL = "C9999999999"


@pytest.fixture(autouse=True)
def rules_path_env(monkeypatch):
    monkeypatch.setenv("RULES_PATH", str(EXAMPLE_RULES))


@pytest.fixture(autouse=True)
def reset_clients():
    yield
    keycloak_integration._client = None
    discourse_integration._client = None


def make_app(tmp_path):
    conn = get_connection(str(tmp_path / "audit.db"))
    return create_slack_app(
        "xoxb-test-token",
        "test-signing-secret",
        trusted_channel_id=TRUSTED_CHANNEL,
        audit_conn=conn,
        rate_limiter=RateLimiter(max_requests=1000, window_seconds=60),
    )


def ack_function_for(app, command_name):
    for listener in app._listeners:
        if any(matcher.func({"command": command_name}) for matcher in listener.matchers):
            return listener.ack_function
    raise AssertionError(f"no listener registered for {command_name!r}")


def capturing_ack():
    """Return (calls, ack): ack(**kwargs) records each call's kwargs."""
    calls = []

    def ack(**kwargs):
        calls.append(kwargs)

    return calls, ack


def capturing_respond():
    """Return (responses, respond): respond(text, **kwargs) records (text, kwargs)."""
    responses = []

    def respond(text, **kwargs):
        responses.append((text, kwargs))

    return responses, respond


def make_command(text, *, channel_id=TRUSTED_CHANNEL, user_name="alice"):
    return {"channel_id": channel_id, "text": text, "user_name": user_name}


class TestTrustCommand:
    def test_valid_command_acks_in_channel(self, tmp_path):
        client = MagicMock()
        client.add_user_to_groups.return_value = ["jira-users"]
        keycloak_integration.set_client(client)

        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust")(ack=ack, command=make_command("jdoe"), respond=respond)

        assert ack_calls == [{"response_type": "in_channel"}]

    def test_wrong_channel_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust")(
            ack=ack, command=make_command("jdoe", channel_id=OTHER_CHANNEL), respond=respond
        )

        assert ack_calls == [{}]

    def test_missing_argument_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust")(ack=ack, command=make_command(""), respond=respond)

        assert ack_calls == [{}]


class TestRevokeCommand:
    def test_valid_command_acks_in_channel(self, tmp_path):
        client = MagicMock()
        client.remove_user_from_groups.return_value = ["jira-users"]
        keycloak_integration.set_client(client)

        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-revoke")(
            ack=ack, command=make_command("jdoe"), respond=respond
        )

        assert ack_calls == [{"response_type": "in_channel"}]

    def test_wrong_channel_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-revoke")(
            ack=ack, command=make_command("jdoe", channel_id=OTHER_CHANNEL), respond=respond
        )

        assert ack_calls == [{}]

    def test_missing_argument_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-revoke")(ack=ack, command=make_command(""), respond=respond)

        assert ack_calls == [{}]


class TestTrustStatusCommand:
    def test_valid_command_acks_in_channel(self, tmp_path):
        client = MagicMock()
        client.get_user_groups.return_value = ["jira-users"]
        keycloak_integration.set_client(client)
        discourse_client = MagicMock()
        discourse_client.get_trust_level.return_value = 2
        discourse_integration.set_client(discourse_client)

        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-status")(
            ack=ack, command=make_command("jdoe"), respond=respond
        )

        assert ack_calls == [{"response_type": "in_channel"}]

    def test_wrong_channel_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-status")(
            ack=ack, command=make_command("jdoe", channel_id=OTHER_CHANNEL), respond=respond
        )

        assert ack_calls == [{}]

    def test_missing_argument_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-status")(ack=ack, command=make_command(""), respond=respond)

        assert ack_calls == [{}]


class TestTrustActivityCommand:
    def test_valid_command_with_no_argument_acks_in_channel(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-activity")(ack=ack, command=make_command(""), respond=respond)

        assert ack_calls == [{"response_type": "in_channel"}]

    def test_valid_command_with_numeric_argument_acks_in_channel(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-activity")(
            ack=ack, command=make_command("5"), respond=respond
        )

        assert ack_calls == [{"response_type": "in_channel"}]

    def test_wrong_channel_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-activity")(
            ack=ack, command=make_command("5", channel_id=OTHER_CHANNEL), respond=respond
        )

        assert ack_calls == [{}]

    def test_non_numeric_argument_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-activity")(
            ack=ack, command=make_command("abc"), respond=respond
        )

        assert ack_calls == [{}]

    def test_non_positive_argument_acks_bare(self, tmp_path):
        app = make_app(tmp_path)
        ack_calls, ack = capturing_ack()
        _, respond = capturing_respond()

        ack_function_for(app, "/trust-activity")(
            ack=ack, command=make_command("0"), respond=respond
        )

        assert ack_calls == [{}]


def test_rate_limited_command_is_unaffected_by_this_change(tmp_path):
    """A rate-limited request never reaches a command listener at all --
    rate_limit_middleware (@app.use) short-circuits with its own ack()
    and never calls next(), so this change (inside the per-command
    listeners) cannot affect it. See design.md's Non-Goals."""
    from slack_bolt.middleware.custom_middleware import CustomMiddleware

    conn = get_connection(str(tmp_path / "audit.db"))
    app = create_slack_app(
        "xoxb-test-token",
        "test-signing-secret",
        trusted_channel_id=TRUSTED_CHANNEL,
        audit_conn=conn,
        rate_limiter=RateLimiter(max_requests=0, window_seconds=60),
    )
    middleware = next(m for m in app._middleware_list if isinstance(m, CustomMiddleware)).func

    ack_calls, ack = capturing_ack()
    next_called = {"value": False}

    class _FakeRequest:
        headers = {}

    middleware(
        body={"user_id": "U1", "command": "/trust"},
        next=lambda: next_called.__setitem__("value", True),
        ack=ack,
        request=_FakeRequest(),
    )

    assert next_called["value"] is False
    assert ack_calls == [{"text": "You are sending commands too quickly. Please wait a moment and try again."}]
