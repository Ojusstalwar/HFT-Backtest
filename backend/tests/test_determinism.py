import pytest
import random
from engine.types import Event, EventType, Order, Side, OrderType, InstrumentType, TradeEvent
from engine.event_queue import EventQueue
from engine.matching_engine import MatchingEngine
from engine.config import FillModelConfig
from engine.price_bands import PriceBandManager
from engine.auction import AuctionManager

def run_simulation(seed: int):
    random.seed(seed)
    
    queue = EventQueue()
    me = MatchingEngine(FillModelConfig(fill_probability_discount=0.8, fill_discount_source="test"), PriceBandManager(), AuctionManager())
    
    # Generate 100 random market events
    for i in range(100):
        ts = 1000 + i * 10
        trade = TradeEvent(symbol="AAPL", timestamp_ns=ts, price=random.choice([150.0, 151.0, 152.0]), size=random.randint(10, 100), side=random.choice([Side.BUY, Side.SELL]))
        queue.push(Event(timestamp_ns=ts, sequence_number=i, type_priority=EventType.TRADE.value, event_type=EventType.TRADE, symbol="AAPL", data={"trade": trade}))
        
    # Strategy submits 10 orders at random times
    orders = []
    for i in range(10):
        ts = 1050 + i * 50
        order = Order(order_id=str(i), symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=150.0, size=50, instrument_type=InstrumentType.EQ, queue_ahead=random.randint(0, 20))
        queue.push(Event(timestamp_ns=ts, sequence_number=i+1000, type_priority=EventType.TIMER.value, event_type=EventType.TIMER, data={"submit_order": order}))
        orders.append(order)
        
    output_log = []
    
    while queue.has_events():
        event = queue.pop()
        
        if event.event_type == EventType.TRADE:
            fills = me.process_trade(event.data["trade"])
            for fill in fills:
                output_log.append(("FILL", fill.data["fill"].order_id, fill.data["fill"].size, fill.data["fill"].price))
        elif event.event_type == EventType.TIMER:
            order = event.data["submit_order"]
            acks = me.submit_order(order, event.timestamp_ns)
            for ack in acks:
                output_log.append(("ACK", ack.data.get("order", ack.data).get("order_id") if isinstance(ack.data.get("order", ack.data), dict) else ack.data["order"].order_id))

    return output_log

def test_deterministic_output():
    # Run twice with the exact same seed — must produce identical output
    log1 = run_simulation(42)
    log2 = run_simulation(42)
    
    assert log1 == log2, "Runs with identical seeds produced different outputs"
    assert len(log1) > 0, "Simulation should produce at least some events"

