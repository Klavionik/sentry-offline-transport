from __future__ import annotations

from collections.abc import Callable
from typing import Dict, Iterable, Optional
from unittest.mock import MagicMock

import pytest
from sentry_sdk.client import get_options
from sentry_sdk.envelope import Envelope

from sentry_offline.storage import Storage, hash_from_content
from sentry_offline.transport import OfflineTransport


class InMemoryStorage(Storage):
    def __init__(self, envelopes: Optional[Iterable[Envelope]] = None) -> None:
        self._storage: Dict[str, Envelope] = {}

        if envelopes:
            for e in envelopes:
                self.save(e)

    def save(self, envelope: Envelope) -> None:
        self._storage[hash_from_content(envelope.serialize())] = envelope

    def remove(self, envelope: Envelope) -> None:
        self._storage.pop(hash_from_content(envelope.serialize()), None)

    def list(self) -> Iterable[Envelope]:
        return list(self._storage.values())


@pytest.fixture
def offline_transport_factory() -> Callable[[Optional[Storage]], OfflineTransport]:
    def factory(storage: Optional[Storage] = None) -> OfflineTransport:
        transport = OfflineTransport(
            get_options(dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234"),
            storage=storage or InMemoryStorage(),
            reupload_on_startup=False,
        )
        return transport

    return factory


def test_transport_retries_stored_envelopes(
    offline_transport_factory: Callable[[Optional[Storage]], OfflineTransport],
    fixture_envelope: Envelope,
) -> None:
    transport = offline_transport_factory(InMemoryStorage([fixture_envelope]))

    transport.capture_envelope = MagicMock(name="capture_envelope")  # type: ignore[method-assign]
    transport.flush_storage()
    transport.flush(timeout=3)

    assert transport.capture_envelope.call_count == 1


def test_transport_removes_resent_events_from_disk(
    offline_transport_factory: Callable[[Optional[Storage]], OfflineTransport],
    fixture_envelope: Envelope,
) -> None:
    storage = InMemoryStorage([fixture_envelope])
    transport = offline_transport_factory(storage)

    transport.flush_storage()
    transport.flush(timeout=3)

    assert not len(list(storage.list()))


@pytest.mark.usefixtures("socket_disabled")
def test_envelope_saved_if_no_network(
    offline_transport_factory: Callable[[Optional[Storage]], OfflineTransport],
    fixture_envelope: Envelope,
) -> None:
    storage = InMemoryStorage()
    transport = offline_transport_factory(storage)
    transport.capture_envelope(fixture_envelope)
    transport.flush(timeout=3)

    assert len(list(storage.list())) == 1
