import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # The context manager runs the lifespan, which starts the simulation loop.
    with TestClient(app) as c:
        yield c


def wait_for(client: TestClient, predicate, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = client.get("/api/state").json()
        if predicate(state) or time.monotonic() > deadline:
            return state
        time.sleep(0.05)


def test_health_reports_ok_and_resolved_backend(client: TestClient) -> None:
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["can_mode"] in {"auto", "socketcan", "virtual"}
    assert body["can_backend"] in {"socketcan", "virtual"}


def test_state_has_cluster_controls_and_simulation(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["simulation"]["running"] is True
    assert body["controls"]["ignition"] is False
    assert "speed_kmh" in body["cluster"]


def test_ignition_over_rest_starts_the_engine(client: TestClient) -> None:
    client.post("/api/controls", json={"ignition": True})

    state = wait_for(client, lambda s: s["cluster"]["engine_state"] == "IDLE")

    assert state["cluster"]["engine_state"] == "IDLE"
    assert state["cluster"]["rpm"] > 600


def test_controls_partial_update(client: TestClient) -> None:
    body = client.post(
        "/api/controls",
        json={"headlights": "HIGH", "doors_open": {"rear_left": True}, "throttle": 25},
    ).json()

    assert body["headlights"] == "HIGH"
    assert body["throttle"] == 25
    assert body["doors_open"] == {
        "front_left": False,
        "front_right": False,
        "rear_left": True,
        "rear_right": False,
    }
    assert body["seatbelt_fastened"] is True  # untouched


@pytest.mark.parametrize(
    "payload",
    [
        {"throttle": 150},
        {"brake": -1},
        {"gear_selector": "X"},
        {"headlights": "FOG"},
        {"doors_open": {"boot": True}},
    ],
)
def test_controls_reject_invalid_values(client: TestClient, payload: dict) -> None:
    assert client.post("/api/controls", json=payload).status_code == 422


def test_pause_freezes_simulated_time(client: TestClient) -> None:
    assert client.post("/api/simulation/pause").json()["running"] is False
    before = client.get("/api/state").json()["simulation"]["time_s"]
    time.sleep(0.3)
    after = client.get("/api/state").json()["simulation"]["time_s"]

    assert after == before
    assert client.post("/api/simulation/start").json()["running"] is True


def test_reset_restarts_simulation(client: TestClient) -> None:
    client.post("/api/controls", json={"ignition": True})
    time.sleep(0.5)

    client.post("/api/simulation/reset")
    state = client.get("/api/state").json()

    assert state["simulation"]["time_s"] < 0.3
    assert state["controls"]["ignition"] is False


def test_speed_factor(client: TestClient) -> None:
    assert client.put("/api/simulation/speed", json={"factor": 5}).json()["speed"] == 5
    assert client.put("/api/simulation/speed", json={"factor": 3}).status_code == 422


def test_unknown_simulation_action(client: TestClient) -> None:
    assert client.post("/api/simulation/explode").status_code == 422


def test_websocket_streams_snapshots(client: TestClient) -> None:
    with client.websocket_connect("/ws/telemetry") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert set(first) == {"simulation", "can_backend", "can_mode", "cluster", "controls"}
    assert second["simulation"]["time_s"] >= first["simulation"]["time_s"]
