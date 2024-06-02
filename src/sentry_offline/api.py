import functools
import logging
import sys
from pathlib import Path
from typing import Optional, Type, Union, overload

from sentry_offline.storage import FilesystemStorage, Storage
from sentry_offline.transport import OfflineTransport

logger = logging.getLogger("sentry_offline")


@overload
def make_offline_transport(
    *, storage_path: Union[Path, str], reupload_on_startup: bool = True, debug: bool = False
) -> Type[OfflineTransport]: ...


@overload
def make_offline_transport(
    *, storage: Storage, reupload_on_startup: bool = True, debug: bool = False
) -> Type[OfflineTransport]: ...


def make_offline_transport(
    *,
    storage_path: Optional[Union[Path, str]] = None,
    reupload_on_startup: bool = True,
    storage: Optional[Storage] = None,
    debug: bool = False,
) -> Type[OfflineTransport]:
    if debug:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[sentry_offline] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    if storage is None:
        if storage_path is None:
            raise ValueError("Specify storage_path to use the default filesystem storage.")

        storage = FilesystemStorage(storage_path)

    class _OfflineTransport(OfflineTransport):
        __init__ = functools.partialmethod(
            OfflineTransport.__init__, storage=storage, reupload_on_startup=reupload_on_startup
        )  # type: ignore[assignment]

    return _OfflineTransport  # type: ignore[no-any-return]
