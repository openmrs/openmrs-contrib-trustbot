"""Verifies the access-log middleware: one line per request, level-controlled.

Mirrors tests/unit/test_main.py's app_client fixture.
"""

import importlib
import logging
import sys

import pytest
from fastapi.testclient import TestClient

CONFIG_YAML = """
discourse:
  base_url: "https://talk.openmrs.org"
keycloak:
  base_url: "https://id-new.openmrs.org"
  realm: "OpenMRS"
slack:
  trusted_channel_id: "C0123456789"
rate_limiting:
  discourse_webhook:
    max_requests: 60
    window_seconds: 60
  slack_commands:
    max_requests: 10
    window_seconds: 60
database:
  path: "{db_path}"
"""


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(CONFIG_YAML.format(db_path=tmp_path / "audit.db"))

    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dummy-client-id")
    monkeypatch.setenv("KEYCLOAK_CLIENT_SECRET", "dummy-client-secret")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-dummy-token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "dummy-signing-secret")
    monkeypatch.setenv("DISCOURSE_API_KEY", "dummy-discourse-api-key")
    monkeypatch.setenv("DISCOURSE_API_USERNAME", "dummy-discourse-api-username")
    monkeypatch.setenv("DISCOURSE_WORKFLOW_SECRET", "dummy-workflow-secret")
    monkeypatch.setenv("DISCOURSE_WEBHOOK_SECRET", "dummy-webhook-secret")
    monkeypatch.setenv("ADMIN_API_TOKEN", "dummy-admin-token")

    sys.modules.pop("src.main", None)
    main = importlib.import_module("src.main")

    with TestClient(main.app) as client:
        yield client

    sys.modules.pop("src.main", None)


def _access_log_records(caplog):
    return [r for r in caplog.records if r.name == "src.access_log"]


def test_health_check_at_default_info_level_produces_no_log_entry(app_client, caplog):
    with caplog.at_level("INFO"):
        response = app_client.get("/health")

    assert response.status_code == 200
    assert _access_log_records(caplog) == []


def test_health_check_at_debug_level_produces_a_log_entry(app_client, caplog):
    with caplog.at_level("DEBUG"):
        app_client.get("/health")

    records = _access_log_records(caplog)
    assert len(records) == 1
    assert records[0].levelname == "DEBUG"
    assert "/health" in records[0].message


def test_undefined_route_is_logged_at_info_and_returns_404(app_client, caplog):
    with caplog.at_level("INFO"):
        response = app_client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    records = _access_log_records(caplog)
    assert len(records) == 1
    assert records[0].levelname == "INFO"
    assert "/this-route-does-not-exist" in records[0].message


def test_runtime_level_change_via_admin_endpoint_takes_effect_on_next_request(
    app_client, caplog
):
    # Lower only the capture handler's own threshold, not any logger's level
    # via caplog.at_level()/set_level() -- the level under test here is the
    # application's real root-logger level (INFO by config default, changed
    # to DEBUG via the actual admin endpoint below), not a level caplog
    # itself imposes.
    caplog.handler.setLevel(logging.DEBUG)

    app_client.get("/health")  # suppressed: app's root logger level is still INFO

    admin_response = app_client.post(
        "/admin/log-level?level=DEBUG",
        headers={"Authorization": "Bearer dummy-admin-token"},
    )
    assert admin_response.status_code == 200

    app_client.get("/health")  # visible: admin endpoint changed the level to DEBUG

    health_debug_records = [
        r
        for r in _access_log_records(caplog)
        if r.levelname == "DEBUG" and "/health" in r.message
    ]
    assert len(health_debug_records) == 1
