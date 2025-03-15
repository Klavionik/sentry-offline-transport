import sentry_sdk
from sentry_sdk.envelope import Envelope

from sentry_offline import make_offline_transport
from sentry_offline.transport import OfflineTransport


def test_sentry_sdk_integration(socket_disabled, tmp_path):
    sentry_sdk.init(
        dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234",
        transport=make_offline_transport(storage_path=tmp_path, debug=True),
    )
    client = sentry_sdk.get_client()

    assert client.transport is not None
    assert isinstance(client.transport, OfflineTransport)

    event_id = sentry_sdk.capture_message("a message")
    sentry_sdk.flush()

    tmp_files = list(tmp_path.iterdir())

    assert len(tmp_files)

    [saved_event] = tmp_files

    with saved_event.open(mode="rb") as fh:
        envelope = Envelope.deserialize_from(fh)

    assert envelope.headers.get("event_id") == event_id
