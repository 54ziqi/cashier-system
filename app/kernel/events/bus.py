"""进程内事件总线"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        for h in self._handlers.get(type(event), []):
            try:
                h(event)
            except Exception:
                log.exception("事件处理器异常: %s", h)


bus = EventBus()
