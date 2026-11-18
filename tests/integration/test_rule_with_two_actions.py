"""A matched rule with two actions (keycloak_add_groups, slack_notify): both
run and both are recorded, and a slack_notify failure doesn't prevent the
keycloak_add_groups result from being recorded -- execute_rule() isolates
each action's exceptions independently (see src/engine/evaluator.py).
"""

from unittest.mock import MagicMock

import pytest

from src.audit.db import get_connection
from src.engine import evaluator
from src.engine.models import Action, Rule, TriggerEvent
from src.integrations import keycloak as keycloak_integration
from src.integrations import slack_notify as slack_notify_integration


@pytest.fixture(autouse=True)
def reset_clients():
    yield
    keycloak_integration._client = None
    slack_notify_integration._client = None
    slack_notify_integration._default_channel = None


def make_rule():
    return Rule(
        name="Grant community edit access (Discourse TL2)",
        triggers=[],
        actions=[
            Action(type="keycloak_add_groups", groups=["jira-users"]),
            Action(type="slack_notify", message="${openmrs_id} trusted by OpenMRS Talk"),
        ],
    )


def make_event(openmrs_id="jdoe"):
    return TriggerEvent(type="workflow", name="trusted", openmrs_id=openmrs_id, source="talk.openmrs.org")


def test_both_actions_run_and_are_recorded(tmp_path):
    conn = get_connection(str(tmp_path / "audit.db"))

    keycloak_client = MagicMock()
    keycloak_client.add_user_to_groups.return_value = ["jira-users"]
    keycloak_integration.set_client(keycloak_client)

    slack_client = MagicMock()
    slack_notify_integration.set_client(slack_client)
    slack_notify_integration.set_default_channel("C0123456789")

    results = evaluator.execute_rule(make_rule(), make_event(), conn=conn)

    assert [r.status for r in results] == ["success", "success"]
    slack_client.chat_postMessage.assert_called_once_with(
        channel="C0123456789", text="jdoe trusted by OpenMRS Talk"
    )

    rows = conn.execute("SELECT action, status FROM audit_log ORDER BY id").fetchall()
    assert rows == [("keycloak_add_groups", "success"), ("slack_notify", "success")]


def test_slack_notify_failure_does_not_block_keycloak_action_recording(tmp_path):
    conn = get_connection(str(tmp_path / "audit.db"))

    keycloak_client = MagicMock()
    keycloak_client.add_user_to_groups.return_value = ["jira-users"]
    keycloak_integration.set_client(keycloak_client)
    # Deliberately leave slack_notify's client uninitialized to force a failure.

    results = evaluator.execute_rule(make_rule(), make_event(), conn=conn)

    assert results[0].status == "success"
    assert results[1].status == "failure"

    rows = conn.execute("SELECT action, status FROM audit_log ORDER BY id").fetchall()
    assert rows == [("keycloak_add_groups", "success"), ("slack_notify", "failure")]
