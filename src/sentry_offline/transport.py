import functools
import hashlib
import logging
import sys
from pathlib import Path
from time import sleep
from typing import Any, Dict, Optional, Type, Union

from sentry_sdk.consts import EndpointType
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport

logger = logging.getLogger("sentry_offline")
logger.addHandler(logging.NullHandler())


def make_offline_transport(
    storage_path: Union[Path, str],
    resend_on_startup: bool = True,
    debug: bool = False,
) -> Type["OfflineTransport"]:
    if debug:
        logger.addHandler(logging.StreamHandler(sys.stderr))
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
        content = envelope.serialize()
        filename = hash_from_content(content)

        path = self.storage / filename

        with path.open(mode="wb") as fh:
            fh.write(content)

        logger.debug("Saved envelope to %s.", path)

    def remove_envelope(self, envelope: Envelope) -> None:
        filename = hash_from_content(envelope.serialize())
        (self.storage / filename).unlink(missing_ok=True)

    def read_storage(self) -> None:
        for file in self.storage.iterdir():
            envelope = load_envelope(file)

            if envelope is None:
                continue

            sleep(0.1)  # Try not to overflood the queue.
            self.capture_envelope(envelope)

    def _send_request(
        self,
        body: bytes,
        headers: Dict[str, str],
        endpoint_type: EndpointType = EndpointType.ENVELOPE,
        envelope: Optional[Envelope] = None,
    ) -> None:
        # Don't try to wrap _send_request if there's no envelope to save (though it seems like
        # the envelope is always present...).
        if envelope is None:
            super()._send_request(body, headers, endpoint_type, envelope)
            return

        try:
            super()._send_request(body, headers, endpoint_type, envelope)
        except Exception:
            # Don't save client reports, they can be generated due to a network error.
            if is_client_report(envelope):
                raise

            logger.debug("Save failed-to-send envelope on disk.")
            self.save_envelope(envelope)
            raise
        else:
            if not is_client_report(envelope):
                logger.debug("Try to remove envelope in case it was read from the disk.")
                self.remove_envelope(envelope)


def load_envelope(file: Path) -> Optional[Envelope]:
    with file.open(mode="rb") as fh:
        try:
            return Envelope.deserialize_from(fh)
        except Exception as exc:
            logger.warning("Cannot deserialize envelope from %s. Error: %s", file, exc)
            file.unlink(missing_ok=True)


def hash_from_content(content: bytes) -> str:
    hasher = hashlib.md5()
    hasher.update(content)
    return hasher.hexdigest()


def is_client_report(envelope: Envelope) -> bool:
    for item in envelope.items:
        if item.type == "client_report":
            return True

    return False
