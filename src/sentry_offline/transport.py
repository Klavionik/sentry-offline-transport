import functools
import logging
from os import PathLike
from pathlib import Path
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
        self._worker.start()

        http_transport = HttpTransport(options)

        original_send_request = http_transport._send_request

        def _send_request_wrapper(*args, **kwargs):
            try:
                original_send_request(*args, **kwargs)
            except Exception:
                envelope = kwargs.get("envelope")

                if envelope:
                    logger.debug("An envelope is picked up to be saved.")
                    submitted = self._worker.submit(functools.partial(self.save_envelope, envelope))

                    if not submitted:
                        logger.warning("The worker queue is full, drop envelope.")

                raise

        http_transport._send_request = _send_request_wrapper

        self._http_transport = http_transport
        self._worker.submit(self.retry_envelopes)

    def flush(
        self,
        timeout: float,
        callback: Optional[Any] = None,
    ) -> None:
        logger.debug("Flushing OfflineTransport...")
        self._worker.flush(timeout, callback)

    def kill(self) -> None:
        logger.debug("Killing OfflineTransport...")
        self._worker.kill()

    def capture_envelope(self, envelope: Envelope) -> None:
        self._http_transport.capture_envelope(envelope)

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

    def retry_envelopes(self):
        for file in self._storage.iterdir():
            logger.debug("Retry envelope %s", file)

            with file.open(mode="rb") as fh:
                try:
                    envelope = Envelope.deserialize_from(fh)
                except Exception as exc:
                    logger.warning("Cannot deserialize envelope from %s. Error: %s", file, exc)
                    file.unlink(missing_ok=True)
                    continue

            file.unlink(missing_ok=True)
            self.capture_envelope(envelope)
