import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sentry_sdk
from sentry_offline import offline_transport


@pytest.fixture
def fixture_envelope_path() -> Path:
    fixture_event_id = "0f8ff792fc1c400bb8a0133a47257dbe"
    return Path(__file__).parent / "fixtures" / fixture_event_id


def test_transport_saves_envelope(tmp_path):
    """
    No network, save envelope on disk.
    """
    transport_class = offline_transport(storage_dir=tmp_path)
    sentry_sdk.init(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234", transport=transport_class)

    event_id = sentry_sdk.capture_message("message")
    sentry_sdk.flush()
    time.sleep(0.1)

    assert (tmp_path / event_id).exists()


def test_transport_doesnt_save_envelope(tmp_path, socket_enabled):
    """
    Network is fine, do not save envelope on disk.
    """
    transport_class = offline_transport(storage_dir=tmp_path)
    sentry_sdk.init(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234", transport=transport_class)

    event_id = sentry_sdk.capture_message("message")
    sentry_sdk.flush()
    time.sleep(0.1)

    assert not (tmp_path / event_id).exists()


def test_transport_saves_multiple_envelopes(tmp_path):
    """
    No network, save multiple envelope on disk.
    """
    transport_class = offline_transport(storage_dir=tmp_path)
    sentry_sdk.init(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234", transport=transport_class)

    event_ids = [
        sentry_sdk.capture_message("message"),
        sentry_sdk.capture_message("message 2"),
        sentry_sdk.capture_message("message 3"),
    ]
    sentry_sdk.flush()
    time.sleep(0.1)
    saved_events = [(tmp_path / event_id).exists() for event_id in event_ids]

    assert all(saved_events)


def test_transport_retries_envelope_success(
    socket_enabled, monkeypatch, tmp_path, fixture_envelope_path
):
    """
    Network is on, successfully upload earlier saved events and delete them from the disk.
    """
    shutil.copyfile(fixture_envelope_path, tmp_path / fixture_envelope_path.name)
    transport_class = offline_transport(storage_dir=tmp_path)

    capture_envelope_mock = MagicMock()
    monkeypatch.setattr(transport_class, "capture_envelope", capture_envelope_mock)

    sentry_sdk.init(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234", transport=transport_class)
    sentry_sdk.flush()
    time.sleep(0.1)

    assert capture_envelope_mock.call_count == 1
    assert not (tmp_path / fixture_envelope_path.name).exists()


def test_transport_retries_envelope_failure(monkeypatch, tmp_path, fixture_envelope_path):
    """
    No network, cannot upload earlier saved events, resave them on disk.
    """
    shutil.copyfile(fixture_envelope_path, tmp_path / fixture_envelope_path.name)
    transport_class = offline_transport(storage_dir=tmp_path)
    original_save_envelope = transport_class.save_envelope

    def save_envelope(envelope):
        client = sentry_sdk.get_client()
        original_save_envelope(client.transport, envelope)  # type: ignore

    save_envelope_mock = MagicMock(side_effect=save_envelope)
    monkeypatch.setattr(transport_class, "save_envelope", save_envelope_mock)

    sentry_sdk.init(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234", transport=transport_class)
    sentry_sdk.flush()
    time.sleep(0.1)

    assert save_envelope_mock.call_count == 1
    assert (tmp_path / fixture_envelope_path.name).exists()
