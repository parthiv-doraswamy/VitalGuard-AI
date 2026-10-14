import asyncio

import pytest

from app.live_events import LiveEventHub


class FakeSocket:
    def __init__(self, delay=0):
        self.delay = delay
        self.events = []

    async def send_json(self, event):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.events.append(event)


def test_hub_requires_finite_positive_send_timeout():
    for value in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="finite positive"):
            LiveEventHub(send_timeout_seconds=value)


@pytest.mark.parametrize("value", ["", "invalid", "nan", "inf", "0", "-0.5"])
def test_invalid_environment_timeout_fails_fast(monkeypatch, value):
    monkeypatch.setenv("VITALGUARD_WEBSOCKET_SEND_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="finite positive"):
        LiveEventHub()


def test_slow_client_is_removed_without_blocking_healthy_client():
    async def scenario():
        hub = LiveEventHub(send_timeout_seconds=0.01)
        slow = FakeSocket(delay=0.1)
        healthy = FakeSocket()
        hub._clients.update({slow, healthy})

        await asyncio.wait_for(hub.broadcast({"type": "observation.created"}), timeout=0.2)

        assert healthy.events == [{"type": "observation.created"}]
        assert slow not in hub._clients
        assert healthy in hub._clients
        assert hub.dropped_clients == 1

    asyncio.run(scenario())


def test_failed_client_is_removed_and_other_clients_receive_event():
    class BrokenSocket:
        async def send_json(self, event):
            raise RuntimeError("disconnected")

    async def scenario():
        hub = LiveEventHub()
        broken = BrokenSocket()
        healthy = FakeSocket()
        hub._clients.update({broken, healthy})

        await hub.broadcast({"type": "alert.created"})

        assert broken not in hub._clients
        assert healthy.events == [{"type": "alert.created"}]
        assert hub.dropped_clients == 1

    asyncio.run(scenario())


def test_broadcast_with_no_clients_is_safe():
    asyncio.run(LiveEventHub().broadcast({"type": "observation.created"}))
