import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sentry_sdk
from sentry_offline import make_offline_transport
from sentry_offline.transport import OfflineTransport, load_envelope
from sentry_sdk.client import get_options
from sentry_sdk.envelope import Envelope


@pytest.fixture(scope="session")
def fixture_name() -> str:
    return "6ea8a22ebf7346f15c845e09efe4f992"


@pytest.fixture(scope="session")
def fixture_envelope_path(fixture_name) -> Path:
    return Path(__file__).parent / "fixtures" / fixture_name


@pytest.fixture(scope="session")
def fixture_envelope(fixture_envelope_path) -> Envelope:
    with fixture_envelope_path.open(mode="rb") as fh:
        return Envelope.deserialize_from(fh)


@pytest.fixture
def offline_transport(fixture_envelope_path, tmp_path) -> OfflineTransport:
    transport = OfflineTransport(
        get_options(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234"),
        storage=tmp_path,
        resend_on_startup=False,
    )
    return transport


def test_saves_envelope(offline_transport, fixture_envelope, fixture_name):
    offline_transport.save_envelope(fixture_envelope)

    assert (offline_transport.storage / fixture_name).exists()


def test_removes_envelope(offline_transport, fixture_envelope, fixture_name, fixture_envelope_path):
    shutil.copyfile(fixture_envelope_path, offline_transport.storage / fixture_name)

    offline_transport.remove_envelope(fixture_envelope)

    assert not (offline_transport.storage / fixture_name).exists()


def test_remove_not_raises_on_missing_envelope(offline_transport, fixture_envelope):
    offline_transport.remove_envelope(fixture_envelope)


def test_load_envelope_from_disk(tmp_path, fixture_envelope_path, fixture_name):
    shutil.copyfile(fixture_envelope_path, tmp_path / fixture_name)
    envelope = load_envelope(tmp_path / fixture_name)

    assert isinstance(envelope, Envelope)
    assert envelope.headers.get("event_id") == "0f8ff792fc1c400bb8a0133a47257dbe"


def test_load_bad_envelope_from_disk_returns_none(tmp_path):
    with (tmp_path / "bad_envelope").open(mode="w") as fh:
        fh.write("nonsense")

    envelope = load_envelope(tmp_path / "bad_envelope")

    assert envelope is None
    assert not (tmp_path / "bad_envelope").exists()


def test_transport_retries_stored_envelopes(
    offline_transport, fixture_envelope, fixture_name, fixture_envelope_path
):
    shutil.copyfile(fixture_envelope_path, offline_transport.storage / fixture_name)
    shutil.copyfile(fixture_envelope_path, offline_transport.storage / (fixture_name + "_2"))

    offline_transport.capture_envelope = MagicMock(name="capture_envelope")
    offline_transport.read_storage()
    offline_transport.flush(timeout=3)

    assert offline_transport.capture_envelope.call_count == 2


def test_envelope_saved_if_no_network(
    socket_disabled, offline_transport, fixture_envelope, fixture_name
):
    offline_transport.capture_envelope(fixture_envelope)
    offline_transport.flush(timeout=3)

    assert (offline_transport.storage / fixture_name).exists()


def test_envelope_retried_and_removed(
    offline_transport, fixture_envelope, fixture_envelope_path, fixture_name
):
    shutil.copyfile(fixture_envelope_path, offline_transport.storage / fixture_name)

    # Simulate one envelope to be corrupted.
    with (offline_transport.storage / "bad_envelope").open(mode="w") as fh:
        fh.write("nonsense")

    offline_transport.read_storage()
    offline_transport.flush(timeout=3)

    assert not (offline_transport.storage / fixture_name).exists()


def test_sentry_sdk_integration(socket_disabled, tmp_path):
    sentry_sdk.init(
        dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234",
        transport=make_offline_transport(storage_path=tmp_path),
    )
    client = sentry_sdk.get_client()

    assert client.transport is not None
    assert isinstance(client.transport, OfflineTransport)
    assert client.transport.storage == tmp_path

    event_id = sentry_sdk.capture_message("a message")
    sentry_sdk.flush()

    tmp_files = list(tmp_path.iterdir())

    assert len(tmp_files)

    saved_event = tmp_files[0]

    with saved_event.open(mode="rb") as fh:
        envelope = Envelope.deserialize_from(fh)

    assert envelope.headers.get("event_id") == event_id
