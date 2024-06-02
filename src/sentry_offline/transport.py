import logging
from time import sleep
from typing import Any, Dict, Optional

from sentry_sdk.consts import EndpointType
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport

from sentry_offline.storage import Storage

logger = logging.getLogger("sentry_offline")


class OfflineTransport(HttpTransport):
    def __init__(self, options: Any, storage: Storage, reupload_on_startup: bool = True):
        logger.debug("Initialize OfflineTransport.")
        super().__init__(options)
        self.storage = storage

        if reupload_on_startup:
            self._worker.submit(self.flush_storage)

    def flush_storage(self) -> None:
        for envelope in self.storage.list():
            self.storage.remove(envelope)
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
            self.storage.save(envelope)
            raise


def is_client_report(envelope: Envelope) -> bool:
    for item in envelope.items:
        if item.type == "client_report":
            return True

    return False
