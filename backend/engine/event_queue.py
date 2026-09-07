from __future__ import annotations

import heapq
from typing import Optional

from engine.types import Event

class EventQueue:
    """
    Min-heap priority event queue.
    Uses Python's heapq with (timestamp_ns, sequence_number, type_priority, event)
    Event ordering is already handled by Event.__lt__ since it is a dataclass with order=True.
    """
    def __init__(self) -> None:
        self._queue: list[Event] = []
        
    def push(self, event: Event) -> None:
        """Pushes an event onto the min-heap."""
        heapq.heappush(self._queue, event)
        
    def pop(self) -> Event:
        """Pops and returns the highest priority event."""
        if not self._queue:
            raise IndexError("pop from empty EventQueue")
        return heapq.heappop(self._queue)
        
    def peek(self) -> Event | None:
        """Returns the highest priority event without removing it."""
        if not self._queue:
            return None
        return self._queue[0]
        
    def has_events(self) -> bool:
        """Returns True if the queue is not empty."""
        return len(self._queue) > 0
        
    def __len__(self) -> int:
        """Returns the number of events in the queue."""
        return len(self._queue)
