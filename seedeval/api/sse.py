from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, AsyncIterator

_event_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)


async def publish_event(run_id: str, event: dict[str, Any]) -> None:
    _event_history[run_id].append(event)
    for queue in list(_subscribers.get(run_id, set())):
        await queue.put(event)


def clear_run_events(run_id: str) -> None:
    _event_history.pop(run_id, None)


async def event_stream(run_id: str) -> AsyncIterator[dict[str, str]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[run_id].add(queue)
    try:
        for event in _event_history.get(run_id, []):
            yield {"data": json.dumps(event)}
            if event.get("stage") == "done":
                return

        while True:
            event = await queue.get()
            yield {"data": json.dumps(event)}
            if event.get("stage") == "done":
                return
    finally:
        _subscribers[run_id].discard(queue)
        if not _subscribers[run_id]:
            _subscribers.pop(run_id, None)
