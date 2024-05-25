import logging
from os import PathLike
from pathlib import Path
from time import sleep
from typing import Any, ClassVar, Optional

from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport, Transport
from sentry_sdk.worker import BackgroundWorker

logger = logging.getLogger("sentry_offline")
logging.basicConfig(level=logging.INFO)


def offline_transport(
    *, storage_dir: PathLike | str, debug: bool = False
) -> type["OfflineTransport"]:
    if debug:
        logger.setLevel(logging.DEBUG)

    storage_path = Path(storage_dir).expanduser().resolve()
    storage_path.mkdir(parents=True, exist_ok=True)
    OfflineTransport.set_storage(storage_path)

    return OfflineTransport


class OfflineTransport(Transport):
    _storage: ClassVar[Optional[Path]] = None

    def __init__(self, options: dict[str, Any]):
        super().__init__(options)
        logger.debug("Initialize OfflineTransport.")

        self._worker = BackgroundWorker()

        http_transport = HttpTransport(options)
        original_send_envelope = http_transport._send_envelope

        def _send_envelope_wrapper(envelope: Envelope) -> None:
            try:
                original_send_envelope(envelope)
            except Exception:
                logger.debug("An envelope is picked up to be saved and retried.")
                self.save_envelope(envelope)
                raise
            else:
                logger.debug("Try to remove envelope in case it was read from the disk.")
                self.remove_envelope(envelope)

        http_transport._send_envelope = _send_envelope_wrapper
        self._http_transport = http_transport

        self.read_storage()

    @classmethod
    def set_storage(cls, storage: Path) -> None:
        cls._storage = storage

    def save_envelope(self, envelope: Envelope) -> None:
        if self._storage is None:
            logger.warning("Storage not set, skip saving.")
            return

        filename = envelope.headers.get("event_id")
        path = self._storage / filename

        with path.open(mode="wb") as fh:
            envelope.serialize_into(fh)

        logger.debug("Saved envelope to %s.", path)

    def remove_envelope(self, envelope: Envelope) -> None:
        event_id = envelope.headers.get("event_id")
        (self._storage / event_id).unlink(missing_ok=True)

    def retry_envelope(self, envelope: Envelope) -> None:
        self._http_transport.capture_envelope(envelope)

    def read_storage(self):
        for file in self._storage.iterdir():
            envelope = load_envelope(file)
            sleep(0.1)  # Try not to overflood the queue.
            self.retry_envelope(envelope)

    def capture_envelope(self, envelope: Envelope) -> None:
        self._http_transport.capture_envelope(envelope)

    def flush(self, timeout: float, callback: Optional[Any] = None) -> None:
        logger.debug("Flushing OfflineTransport...")
        self._worker.flush(timeout, callback)
        self._http_transport.flush(timeout, callback)

    def kill(self) -> None:
        logger.debug("Killing OfflineTransport...")
        OfflineTransport._storage = None
        self._worker.kill()
        self._http_transport.kill()


def load_envelope(file: Path) -> Envelope:
    with file.open(mode="rb") as fh:
        try:
            return Envelope.deserialize_from(fh)
        except Exception as exc:
            logger.warning("Cannot deserialize envelope from %s. Error: %s", file, exc)
            file.unlink(missing_ok=True)
