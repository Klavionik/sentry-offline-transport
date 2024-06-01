import abc
import hashlib
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Union

from sentry_sdk.envelope import Envelope

logger = logging.getLogger("sentry_offline")


class Storage(abc.ABC):
    @abc.abstractmethod
    def save(self, envelope: Envelope) -> None:
        pass

    @abc.abstractmethod
    def remove(self, envelope: Envelope) -> None:
        pass

    @abc.abstractmethod
    def list(self) -> Iterable[Envelope]:
        pass


class FilesystemStorage(Storage):
    def __init__(self, path: Union[Path, str]) -> None:
        self.dir = Path(path).expanduser().resolve()
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, envelope: Envelope) -> None:
        content = envelope.serialize()
        filename = hash_from_content(content)

        path = self.dir / filename

        with path.open(mode="wb") as fh:
            fh.write(content)

        logger.debug("Saved envelope to %s.", path)

    def remove(self, envelope: Envelope) -> None:
        filename = hash_from_content(envelope.serialize())
        (self.dir / filename).unlink(missing_ok=True)

    def list(self) -> Iterable[Envelope]:
        for file in self.dir.iterdir():
            envelope = load_envelope(file)

            if envelope is None:
                continue

            yield envelope


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
