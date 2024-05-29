import functools
import logging
from os import PathLike
from pathlib import Path
from time import sleep
from typing import Any, Optional, Type

from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport

logger = logging.getLogger("sentry_offline")
logging.basicConfig(level=logging.INFO)


def offline_transport(
    storage_path: "PathLike[str]",
    resend_on_startup: bool = True,
    debug: bool = False,
) -> Type["OfflineTransport"]:
    if debug:
        logger.setLevel(logging.DEBUG)

    storage = Path(storage_path).expanduser().resolve()
    storage.mkdir(parents=True, exist_ok=True)

    class _OfflineTransport(OfflineTransport):
        __init__ = functools.partialmethod(
            OfflineTransport.__init__, storage=storage, resend_on_startup=resend_on_startup
        )  # type: ignore[assignment]

    return _OfflineTransport  # type: ignore[no-any-return]


class OfflineTransport(HttpTransport):
    def __init__(self, options: Any, storage: Path, resend_on_startup: bool = True):
        logger.debug("Initialize OfflineTransport.")
        super().__init__(options)
        self.storage = storage

        if resend_on_startup:
            self._worker.submit(self.read_storage)

    def save_envelope(self, envelope: Envelope) -> None:
        event_id = envelope.headers.get("event_id")
        assert event_id, "Envelope with no event_id"

        path = self.storage / event_id

        with path.open(mode="wb") as fh:
            envelope.serialize_into(fh)

        logger.debug("Saved envelope to %s.", path)

    def remove_envelope(self, envelope: Envelope) -> None:
        event_id = envelope.headers.get("event_id")
        assert event_id, "Envelope with no event_id"

        (self.storage / event_id).unlink(missing_ok=True)

    def read_storage(self) -> None:
        for file in self.storage.iterdir():
            envelope = load_envelope(file)

            if envelope is None:
                continue

            sleep(0.1)  # Try not to overflood the queue.
            self.capture_envelope(envelope)

    def _send_envelope(self, envelope: Envelope) -> None:
        try:
            super()._send_envelope(envelope)
        except Exception:
            logger.debug("An envelope is picked up to be saved and retried.")
            self.save_envelope(envelope)
            raise
        else:
            logger.debug("Try to remove envelope in case it was read from the disk.")
            self.remove_envelope(envelope)


def load_envelope(file: Path) -> Optional[Envelope]:
    with file.open(mode="rb") as fh:
        try:
            return Envelope.deserialize_from(fh)
        except Exception as exc:
            logger.warning("Cannot deserialize envelope from %s. Error: %s", file, exc)
            file.unlink(missing_ok=True)
