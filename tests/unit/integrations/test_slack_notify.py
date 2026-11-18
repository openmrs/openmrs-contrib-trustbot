import pytest

from src.integrations import slack_notify


@pytest.fixture(autouse=True)
def reset_module_state():
    yield
    slack_notify._client = None
    slack_notify._default_channel = None


def test_get_client_before_set_raises():
    with pytest.raises(RuntimeError, match="not initialized"):
        slack_notify.get_client()


def test_set_client_then_get_client_returns_it():
    client = slack_notify.build_client("xoxb-test-token")
    slack_notify.set_client(client)
    assert slack_notify.get_client() is client


def test_get_default_channel_before_set_raises():
    with pytest.raises(RuntimeError, match="not initialized"):
        slack_notify.get_default_channel()


def test_set_default_channel_then_get_default_channel_returns_it():
    slack_notify.set_default_channel("C0123456789")
    assert slack_notify.get_default_channel() == "C0123456789"
