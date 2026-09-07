import pytest
from engine.types import Event, EventType, PriceLevel, BookSnapshot
from engine.order_book import OrderBook

def test_update_from_snapshot():
    book = OrderBook("AAPL")
    bids = [PriceLevel(150.0, 100), PriceLevel(149.0, 200)]
    asks = [PriceLevel(151.0, 150), PriceLevel(152.0, 250)]
    
    event = Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={"bids": bids, "asks": asks}
    )
    
    book.update(event)
    
    snapshot = book.get_snapshot()
    assert len(snapshot.bids) == 2
    assert snapshot.best_bid.price == 150.0
    assert snapshot.best_ask.price == 151.0

def test_mid_price():
    book = OrderBook("AAPL")
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={
            "bids": [PriceLevel(100.0, 10)],
            "asks": [PriceLevel(102.0, 10)]
        }
    ))
    assert book.mid_price == 101.0

def test_micro_price():
    book = OrderBook("AAPL")
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={
            "bids": [PriceLevel(100.0, 30)],  # Heavy bid
            "asks": [PriceLevel(102.0, 10)]   # Light ask
        }
    ))
    # Volume weighted mid price: (ask_price*vb + bid_price*va) / (vb+va)
    # (102.0*30 + 100.0*10) / 40 = (3060 + 1000)/40 = 4060/40 = 101.5
    assert book.micro_price == 101.5

def test_order_book_imbalance():
    book = OrderBook("AAPL")
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={
            "bids": [PriceLevel(100.0, 30)],
            "asks": [PriceLevel(102.0, 10)]
        }
    ))
    # OBI = (V_bid - V_ask) / (V_bid + V_ask) = (30 - 10) / 40 = 0.5
    assert book.order_book_imbalance == 0.5

def test_spread():
    book = OrderBook("AAPL")
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={
            "bids": [PriceLevel(100.0, 10)],
            "asks": [PriceLevel(102.5, 10)]
        }
    ))
    assert book.spread == 2.5

def test_get_depth_at_price():
    book = OrderBook("AAPL")
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={
            "bids": [PriceLevel(100.0, 30), PriceLevel(99.0, 50)],
            "asks": [PriceLevel(102.0, 10)]
        }
    ))
    assert book.get_depth_at_price(100.0) == 30
    assert book.get_depth_at_price(99.0) == 50
    assert book.get_depth_at_price(102.0) == 10
    assert book.get_depth_at_price(101.0) == 0

def test_empty_book():
    book = OrderBook("AAPL")
    assert book.mid_price is None
    assert book.micro_price is None
    assert book.order_book_imbalance is None
    assert book.spread is None

def test_max_levels():
    book = OrderBook("AAPL", max_levels=2)
    bids = [PriceLevel(100.0-i, 10) for i in range(5)]
    book.update(Event(
        timestamp_ns=1000,
        sequence_number=1,
        type_priority=EventType.BOOK_UPDATE.value,
        event_type=EventType.BOOK_UPDATE,
        symbol="AAPL",
        data={"bids": bids, "asks": []}
    ))
    assert len(book.bids) == 2
    assert book.bids[0].price == 100.0
    assert book.bids[1].price == 99.0
