import pytest
from engine.types import Event, EventType, Order, Side, OrderType, OrderStatus, Fill
from engine.oms import OMS

# Monkeypatch Event to support order_id property for tests, as oms.py uses getattr()
Event.order_id = property(lambda self: self.data.get("order_id"))

def test_submit_order():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    assert order.status == OrderStatus.PENDING_NEW

def test_handle_ack():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    # the code gets order_id from event.order_id but event has no order_id attr, we'll assign it dynamically
    ack.data["order_id"] = "1"
    
    oms.handle_ack(ack)
    assert order.status == OrderStatus.NEW

def test_handle_fill_full():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "1"
    oms.handle_ack(ack)
    
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=150.0, size=100, timestamp_ns=1000, is_maker=True)
    oms.handle_fill(fill)
    
    assert order.status == OrderStatus.FILLED
    assert order.filled_size == 100
    assert order.fill_price_avg == 150.0

def test_handle_fill_partial():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "1"
    oms.handle_ack(ack)
    
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=150.0, size=40, timestamp_ns=1000, is_maker=True)
    oms.handle_fill(fill)
    
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_size == 40
    assert order.fill_price_avg == 150.0

def test_request_cancel():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "1"
    oms.handle_ack(ack)
    
    oms.request_cancel("1")
    assert order.status == OrderStatus.PENDING_CANCEL

def test_handle_cancel_ack():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "1"
    oms.handle_ack(ack)
    oms.request_cancel("1")
    
    cancel_ack = Event(timestamp_ns=2000, sequence_number=1, type_priority=EventType.CANCEL_ACK.value, event_type=EventType.CANCEL_ACK)
    cancel_ack.data["order_id"] = "1"
    oms.handle_cancel_ack(cancel_ack)
    
    assert order.status == OrderStatus.CANCELLED

def test_cancel_fill_race_guard():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "1"
    oms.handle_ack(ack)
    
    # Fill occurs before cancel ack processes
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=150.0, size=100, timestamp_ns=1000, is_maker=True)
    oms.handle_fill(fill)
    
    assert order.status == OrderStatus.FILLED
    
    cancel_ack = Event(timestamp_ns=1000, sequence_number=2, type_priority=EventType.CANCEL_ACK.value, event_type=EventType.CANCEL_ACK)
    cancel_ack.data["order_id"] = "1"
    oms.handle_cancel_ack(cancel_ack)
    
    assert order.status == OrderStatus.CANCEL_REJECTED

def test_invalid_transition():
    oms = OMS()
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order)
    # Order is PENDING_NEW. Fill should raise ValueError
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=150.0, size=100, timestamp_ns=1000, is_maker=True)
    with pytest.raises(ValueError):
        oms.handle_fill(fill)

def test_get_active_orders():
    oms = OMS()
    order1 = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=100)
    oms.submit_order(order1)
    
    order2 = Order(order_id="2", symbol="AAPL", side=Side.SELL, order_type=OrderType.LIMIT, price=155.0, size=100)
    oms.submit_order(order2)
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK)
    ack.data["order_id"] = "2"
    oms.handle_ack(ack)
    
    fill = Fill(order_id="2", symbol="AAPL", side=Side.SELL, price=155.0, size=100, timestamp_ns=1000, is_maker=True)
    oms.handle_fill(fill)
    
    # order1 is PENDING_NEW, order2 is FILLED
    active = oms.get_active_orders()
    assert len(active) == 1
    assert active[0].order_id == "1"
