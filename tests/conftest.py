from pathlib import Path

import pytest
from sentry_sdk.envelope import Envelope


@pytest.fixture(scope="session")
def fixture_name() -> str:
    return "6ea8a22ebf7346f15c845e09efe4f992"


@pytest.fixture(scope="session")
def fixture_envelope_path(fixture_name: str) -> Path:
    return Path(__file__).parent / "fixtures" / fixture_name


@pytest.fixture(scope="session")
def fixture_envelope(fixture_envelope_path: Path) -> Envelope:
    with fixture_envelope_path.open(mode="rb") as fh:
        return Envelope.deserialize_from(fh)
