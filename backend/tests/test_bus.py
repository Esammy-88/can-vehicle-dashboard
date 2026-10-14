import pytest

from app.can import bus as bus_module
from app.can.bus import BusFactory, CanBackend, CanInterfaceUnavailable
from app.can.decoder import CanCodec
from app.config import CanMode


@pytest.fixture
def no_socketcan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bus_module, "_probe_socketcan", lambda channel: "not available")


def test_virtual_mode_uses_software_bus(channel: str) -> None:
    assert BusFactory(CanMode.VIRTUAL, channel).backend is CanBackend.VIRTUAL


def test_auto_mode_falls_back_without_socketcan(no_socketcan: None, channel: str) -> None:
    assert BusFactory(CanMode.AUTO, channel).backend is CanBackend.VIRTUAL


def test_auto_mode_prefers_socketcan(monkeypatch: pytest.MonkeyPatch, channel: str) -> None:
    monkeypatch.setattr(bus_module, "_probe_socketcan", lambda channel: None)

    assert BusFactory(CanMode.AUTO, channel).backend is CanBackend.SOCKETCAN


def test_socketcan_mode_fails_loudly_without_socketcan(no_socketcan: None, channel: str) -> None:
    with pytest.raises(CanInterfaceUnavailable, match="not available"):
        BusFactory(CanMode.SOCKETCAN, channel)


def test_frames_travel_between_nodes(codec: CanCodec, channel: str) -> None:
    factory = BusFactory(CanMode.VIRTUAL, channel)
    ecm, ipc, bcm = factory.open(), factory.open(), factory.open()
    try:
        ecm.send(codec.encode("ENGINE_TEMPERATURE", {"CoolantTemp": 90, "OilTemp": 100}))

        for receiver in (ipc, bcm):
            frame = receiver.recv(timeout=1.0)
            assert frame is not None
            decoded = codec.decode(frame)
            assert decoded.ok
            assert decoded.sender == "ECM"
            assert decoded.signals["CoolantTemp"] == 90

        assert ecm.recv(timeout=0.05) is None  # a node does not hear its own frames
    finally:
        for b in (ecm, ipc, bcm):
            b.shutdown()
