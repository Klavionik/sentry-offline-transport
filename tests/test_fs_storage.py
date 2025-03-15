import shutil

import pytest
from sentry_sdk.envelope import Envelope

from sentry_offline.storage import FilesystemStorage, load_envelope


@pytest.fixture
def fs_storage(tmp_path):
    return FilesystemStorage(tmp_path)


def test_saves_envelope(fs_storage, fixture_envelope, fixture_name):
    fs_storage.save(fixture_envelope)

    assert (fs_storage.dir / fixture_name).exists()


def test_removes_envelope(fs_storage, fixture_envelope, fixture_name, fixture_envelope_path):
    shutil.copyfile(fixture_envelope_path, fs_storage.dir / fixture_name)

    fs_storage.remove(fixture_envelope)

    assert not (fs_storage.dir / fixture_name).exists()


def test_remove_not_raises_on_missing_envelope(fs_storage, fixture_envelope):
    fs_storage.remove(fixture_envelope)


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
