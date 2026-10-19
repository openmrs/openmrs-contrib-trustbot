"""End-to-end /trust-activity flow: Slack command -> read audit_log -> respond.

Like /trust-status, this never reaches the rules engine. Exercises
src.integrations.slack._handle_trust_activity() directly (bypassing
slack-bolt's HTTP/signature layer, out of scope here) against a real
temp audit DB seeded via record_event().
"""

import pytest

from src.audit.db import get_connection, record_event
from src.integrations.slack import SlackContext, _handle_trust_activity

TRUSTED_CHANNEL = "C0123456789"


@pytest.fixture
def context(tmp_path):
    conn = get_connection(str(tmp_path / "audit.db"))
    yield SlackContext(trusted_channel_id=TRUSTED_CHANNEL, audit_conn=conn, default_log_length=10)
    conn.close()


def make_command(text="", channel_id=TRUSTED_CHANNEL, user_name="alice"):
    return {"channel_id": channel_id, "text": text, "user_name": user_name}


def seed_rows(conn, count):
    for i in range(count):
        record_event(
            conn,
            openmrs_id=f"user{i}",
            trigger="slack_trust_command",
            trigger_src="alice",
            rule_name="Grant community edit access (manual /trust)",
            action="keycloak_add_groups",
            action_detail=None,
            status="success",
            detail=None,
        )


def capturing_respond():
    """Return (responses, respond): respond(text, **kwargs) records (text, kwargs).

    Stands in for slack-bolt's real respond(), which passes
    response_type as a keyword argument -- plain list.append can't
    accept that.
    """
    responses = []

    def respond(text, **kwargs):
        responses.append((text, kwargs))

    return responses, respond


def test_default_length_used_when_no_argument_given(context):
    seed_rows(context.audit_conn, 15)

    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text=""), context, respond)

    assert len(responses) == 1
    text, kwargs = responses[0]
    assert len(text.split("\n")) == 10  # context.default_log_length
    assert kwargs.get("response_type") == "in_channel"


def test_explicit_length_is_respected(context):
    seed_rows(context.audit_conn, 15)

    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text="3"), context, respond)

    text, _ = responses[0]
    assert len(text.split("\n")) == 3


def test_length_above_cap_is_capped_not_rejected(context):
    seed_rows(context.audit_conn, 60)

    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text="500"), context, respond)

    assert len(responses) == 1
    text, kwargs = responses[0]
    assert len(text.split("\n")) == 50  # MAX_ACTIVITY_LENGTH, not 500
    assert kwargs.get("response_type") == "in_channel"


def test_non_numeric_argument_is_rejected_ephemeral(context):
    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text="banana"), context, respond)

    assert len(responses) == 1
    text, kwargs = responses[0]
    assert "Usage" in text
    assert "response_type" not in kwargs


def test_non_positive_argument_is_rejected_ephemeral(context):
    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text="0"), context, respond)

    text, kwargs = responses[0]
    assert "Usage" in text
    assert "response_type" not in kwargs


def test_wrong_channel_produces_no_response(context):
    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(channel_id="C_UNAUTHORIZED"), context, respond)

    assert responses == []


def test_wrong_channel_logs_warning(context, caplog):
    with caplog.at_level("WARNING"):
        _handle_trust_activity(
            make_command(channel_id="C_UNAUTHORIZED"), context, lambda *_, **__: None
        )

    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_no_activity_yet_is_reported_clearly(context):
    responses, respond = capturing_respond()
    _handle_trust_activity(make_command(text=""), context, respond)

    text, kwargs = responses[0]
    assert "No recorded activity yet." in text
    assert kwargs.get("response_type") == "in_channel"
