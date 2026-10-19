"""Unit tests for /trust-activity's row -> human-readable line formatting.

Covers every (trigger, action, status) combination in
openspec/changes/archive/*-add-trust-activity-command/design.md's
phrasing table, plus the generic fallback and the empty-list case.
"""

from src.integrations.slack import _format_activity_line, _format_activity_response


def make_row(
    *,
    timestamp="2026-10-20T14:32:07+00:00",
    openmrs_id="foobar",
    trigger,
    trigger_src=None,
    action,
    status,
    detail=None,
):
    return {
        "timestamp": timestamp,
        "openmrs_id": openmrs_id,
        "trigger": trigger,
        "trigger_src": trigger_src,
        "action": action,
        "status": status,
        "detail": detail,
    }


def test_timestamp_is_rendered_compact_utc():
    row = make_row(
        trigger="slack_trust_command",
        trigger_src="Bob",
        action="keycloak_add_groups",
        status="success",
    )

    line = _format_activity_line(row)

    assert line.startswith("261020 14:32:07 - ")


def test_slack_trust_success():
    row = make_row(
        trigger="slack_trust_command",
        trigger_src="Bob",
        action="keycloak_add_groups",
        status="success",
    )
    assert "Bob issued `/trust foobar`" in _format_activity_line(row)


def test_slack_trust_no_change():
    row = make_row(
        trigger="slack_trust_command",
        trigger_src="Bob",
        action="keycloak_add_groups",
        status="no_change",
    )
    assert "Bob issued `/trust foobar` (already trusted)" in _format_activity_line(row)


def test_slack_trust_dry_run():
    row = make_row(
        trigger="slack_trust_command",
        trigger_src="Bob",
        action="keycloak_add_groups",
        status="dry_run",
    )
    assert "Bob issued `/trust foobar` (dry run, no change)" in _format_activity_line(row)


def test_slack_trust_failure():
    row = make_row(
        trigger="slack_trust_command",
        trigger_src="Bob",
        action="keycloak_add_groups",
        status="failure",
        detail="user not found",
    )
    assert "Bob issued `/trust foobar` (failed: user not found)" in _format_activity_line(row)


def test_slack_revoke_success():
    row = make_row(
        trigger="slack_revoke_command",
        trigger_src="Bob",
        action="keycloak_remove_groups",
        status="success",
    )
    assert "Bob issued `/trust-revoke foobar`" in _format_activity_line(row)


def test_slack_revoke_no_change():
    row = make_row(
        trigger="slack_revoke_command",
        trigger_src="Bob",
        action="keycloak_remove_groups",
        status="no_change",
    )
    assert "Bob issued `/trust-revoke foobar` (already not trusted)" in _format_activity_line(row)


def test_slack_revoke_dry_run():
    row = make_row(
        trigger="slack_revoke_command",
        trigger_src="Bob",
        action="keycloak_remove_groups",
        status="dry_run",
    )
    assert "Bob issued `/trust-revoke foobar` (dry run, no change)" in _format_activity_line(row)


def test_slack_revoke_failure():
    row = make_row(
        trigger="slack_revoke_command",
        trigger_src="Bob",
        action="keycloak_remove_groups",
        status="failure",
        detail="connection refused",
    )
    assert (
        "Bob issued `/trust-revoke foobar` (failed: connection refused)"
        in _format_activity_line(row)
    )


def test_discourse_workflow_grant_success():
    row = make_row(
        trigger="workflow",
        trigger_src="https://talk.openmrs.org",
        action="keycloak_add_groups",
        status="success",
    )
    assert "Discourse trusted foobar" in _format_activity_line(row)


def test_discourse_webhook_grant_success():
    row = make_row(
        trigger="webhook",
        trigger_src="https://talk.openmrs.org",
        action="keycloak_add_groups",
        status="success",
    )
    assert "Discourse trusted foobar" in _format_activity_line(row)


def test_discourse_grant_no_change():
    row = make_row(trigger="workflow", action="keycloak_add_groups", status="no_change")
    assert "Discourse found foobar already trusted" in _format_activity_line(row)


def test_discourse_grant_dry_run():
    row = make_row(trigger="workflow", action="keycloak_add_groups", status="dry_run")
    assert "Discourse would have trusted foobar (dry run, no change)" in _format_activity_line(row)


def test_discourse_grant_failure():
    row = make_row(
        trigger="workflow", action="keycloak_add_groups", status="failure", detail="boom"
    )
    assert "Discourse failed to trust foobar: boom" in _format_activity_line(row)


def test_discourse_revoke_success():
    row = make_row(trigger="webhook", action="keycloak_remove_groups", status="success")
    assert "Discourse revoked trust for foobar" in _format_activity_line(row)


def test_discourse_revoke_no_change():
    row = make_row(trigger="workflow", action="keycloak_remove_groups", status="no_change")
    assert "Discourse found foobar already not trusted" in _format_activity_line(row)


def test_discourse_revoke_dry_run():
    row = make_row(trigger="webhook", action="keycloak_remove_groups", status="dry_run")
    assert (
        "Discourse would have revoked trust for foobar (dry run, no change)"
        in _format_activity_line(row)
    )


def test_discourse_revoke_failure():
    row = make_row(
        trigger="webhook", action="keycloak_remove_groups", status="failure", detail="boom"
    )
    assert "Discourse failed to revoke trust for foobar: boom" in _format_activity_line(row)


def test_unrecognized_combination_falls_back_rather_than_dropping():
    row = make_row(trigger="github_contribution", action="some_future_action", status="success")

    line = _format_activity_line(row)

    assert "github_contribution" in line
    assert "some_future_action" in line
    assert "success" in line


def test_empty_response_states_no_activity():
    assert _format_activity_response([]) == "No recorded activity yet."


def test_response_renders_one_bullet_per_row():
    rows = [
        make_row(trigger="slack_trust_command", trigger_src="Bob", action="keycloak_add_groups", status="success"),
        make_row(trigger="workflow", action="keycloak_remove_groups", status="success"),
    ]

    response = _format_activity_response(rows)

    lines = response.split("\n")
    assert len(lines) == 2
    assert all(line.startswith("- ") for line in lines)
