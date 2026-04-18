"""EventBus tests."""

import asyncio

import pytest

from anxbrowser.events import EventBus


@pytest.mark.asyncio
async def test_publish_and_subscribe_delivers():
    bus = EventBus()
    q = await bus.subscribe()
    ev = await bus.publish("navigated", {"url": "https://x"})
    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got.seq == ev.seq
    assert got.kind == "navigated"
    assert got.payload["url"] == "https://x"


@pytest.mark.asyncio
async def test_history_is_replayed_to_late_subscribers():
    bus = EventBus(history=16)
    await bus.publish("a", {})
    await bus.publish("b", {})
    q = await bus.subscribe()
    first = await asyncio.wait_for(q.get(), timeout=1.0)
    second = await asyncio.wait_for(q.get(), timeout=1.0)
    assert first.kind == "a"
    assert second.kind == "b"


@pytest.mark.asyncio
async def test_unsubscribe_stops_deliveries():
    bus = EventBus()
    q = await bus.subscribe()
    await bus.unsubscribe(q)
    await bus.publish("x", {})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.1)


@pytest.mark.asyncio
async def test_sequence_monotonic():
    bus = EventBus()
    e1 = await bus.publish("x", {})
    e2 = await bus.publish("y", {})
    e3 = await bus.publish("z", {})
    assert e2.seq == e1.seq + 1
    assert e3.seq == e2.seq + 1
