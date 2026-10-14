import uuid
from collections.abc import Iterator

import pytest

from app.can.bus import BusFactory
from app.can.dbc_loader import load_database
from app.can.decoder import CanCodec
from app.config import CanMode
from app.simulation.simulator import Simulator


@pytest.fixture(scope="session")
def codec() -> CanCodec:
    return CanCodec(load_database())


@pytest.fixture
def channel() -> str:
    # Virtual buses are shared per channel name across the whole process;
    # a unique name keeps tests from seeing each other's frames.
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def factory(channel: str) -> BusFactory:
    return BusFactory(CanMode.VIRTUAL, channel)


@pytest.fixture
def sim(factory: BusFactory, codec: CanCodec) -> Iterator[Simulator]:
    with Simulator(factory, codec, seed=1) as s:
        yield s
