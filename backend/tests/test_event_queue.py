import pytest
from engine.types import Event, EventType
from engine.event_queue import EventQueue

def test_basic_push_pop():
    queue = EventQueue()
    e1 = Event(timestamp_ns=2000, sequence_number=1, type_priority=EventType.TRADE.value, event_type=EventType.TRADE)
    e2 = Event(timestamp_ns=1000, sequence_number=2, type_priority=EventType.TRADE.value, event_type=EventType.TRADE)
    
    queue.push(e1)
    queue.push(e2)
    
    # Should pop e2 first because of lower timestamp
    assert queue.pop() == e2
    assert queue.pop() == e1

def test_tie_breaking_by_sequence():
    queue = EventQueue()
    e1 = Event(timestamp_ns=1000, sequence_number=2, type_priority=EventType.TRADE.value, event_type=EventType.TRADE)
    e2 = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.TRADE.value, event_type=EventType.TRADE)
    
    queue.push(e1)
    queue.push(e2)
    
    # Should pop e2 first because of lower sequence_number
    assert queue.pop() == e2
    assert queue.pop() == e1

def test_tie_breaking_by_priority():
    queue = EventQueue()
    e1 = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.TRADE.value, event_type=EventType.TRADE)
    e2 = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.BOOK_UPDATE.value, event_type=EventType.BOOK_UPDATE)
    
    queue.push(e1)
    queue.push(e2)
    
    # BOOK_UPDATE is 1, TRADE is 2. Should pop e2 (BOOK_UPDATE) first.
    assert queue.pop() == e2
    assert queue.pop() == e1

def test_empty_queue():
    queue = EventQueue()
    assert queue.peek() is None
    with pytest.raises(IndexError):
        queue.pop()

def test_has_events():
    queue = EventQueue()
    assert not queue.has_events()
    queue.push(Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.TRADE.value, event_type=EventType.TRADE))
    assert queue.has_events()
    queue.pop()
    assert not queue.has_events()

def test_len():
    queue = EventQueue()
    assert len(queue) == 0
    queue.push(Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.TRADE.value, event_type=EventType.TRADE))
    assert len(queue) == 1
    queue.push(Event(timestamp_ns=2000, sequence_number=2, type_priority=EventType.TRADE.value, event_type=EventType.TRADE))
    assert len(queue) == 2
    queue.pop()
    assert len(queue) == 1
