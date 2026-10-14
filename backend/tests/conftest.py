import uuid

import pytest

from app.can.dbc_loader import load_database
from app.can.decoder import CanCodec


@pytest.fixture(scope="session")
def codec() -> CanCodec:
    return CanCodec(load_database())


@pytest.fixture
def channel() -> str:
    # Virtual buses are shared per channel name across the whole process;
    # a unique name keeps tests from seeing each other's frames.
    return f"test-{uuid.uuid4().hex[:8]}"
