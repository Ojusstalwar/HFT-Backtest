import pytest
from engine.types import Order, Event, EventType, Side, OrderType, Position, InstrumentType
from engine.risk_manager import RiskManager
from engine.oms import OMS
from engine.portfolio import Portfolio
from dataclasses import dataclass

@dataclass
class MockConfig:
    max_orders_per_sec: int = 10
    max_order_size: int = 1000
    max_position_size: int = 5000
    max_drawdown_pct: float = 0.05

def test_max_position_check():
    config = MockConfig()
    rm = RiskManager(config)
    portfolio = Portfolio(initial_capital=100000)
    # simulate position
    portfolio._positions["AAPL"] = Position(symbol="AAPL", instrument_type=InstrumentType.EQ, size=4500)
    
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, size=600)
    allowed, reason = rm.check_pre_trade(order, portfolio, 1000)
    assert not allowed
    assert "exceed max position size" in reason
    
    # sell order should pass
    order_sell = Order(order_id="2", symbol="AAPL", side=Side.SELL, order_type=OrderType.LIMIT, price=100.0, size=600)
    allowed, _ = rm.check_pre_trade(order_sell, portfolio, 2000)
    assert allowed

def test_max_order_size():
    config = MockConfig()
    rm = RiskManager(config)
    portfolio = Portfolio(initial_capital=100000)
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, size=1500)
    allowed, reason = rm.check_pre_trade(order, portfolio, 1000)
    assert not allowed
    assert "exceeds max limit" in reason

def test_drawdown_kill_switch():
    config = MockConfig()
    rm = RiskManager(config)
    portfolio = Portfolio(initial_capital=100000)
    # create a 6% drawdown
    portfolio._realized_pnl = -6000
    
    assert rm.check_drawdown(portfolio, 1000)
    
    # 4% drawdown
    portfolio._realized_pnl = -4000
    assert not rm.check_drawdown(portfolio, 2000)

def test_rate_limiting():
    config = MockConfig(max_orders_per_sec=2)
    rm = RiskManager(config)
    portfolio = Portfolio(initial_capital=100000)
    
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, size=10)
    
    assert rm.check_pre_trade(order, portfolio, 1000)[0]
    assert rm.check_pre_trade(order, portfolio, 2000)[0]
    
    # 3rd order in same second (<= 1_000_000_000)
    allowed, reason = rm.check_pre_trade(order, portfolio, 3000)
    assert not allowed
    assert "Rate limit exceeded" in reason
    
    # order after 1 sec
    allowed, _ = rm.check_pre_trade(order, portfolio, 1_000_003_000)
    assert allowed

def test_circuit_halt_cancels_orders():
    config = MockConfig()
    oms = OMS()
    rm = RiskManager(config, oms)
    
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, size=10)
    oms.submit_order(order)
    Event.order_id = property(lambda self: self.data.get("order_id", getattr(self, "symbol", None)))
    ack = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.ORDER_ACK.value, event_type=EventType.ORDER_ACK, data={"order_id": "1"})
    oms.handle_ack(ack)
    
    halt_event = Event(timestamp_ns=1000, sequence_number=1, type_priority=EventType.CIRCUIT_HALT.value, event_type=EventType.CIRCUIT_HALT, symbol="AAPL")
    rm.on_circuit_halt(halt_event)
    
    assert rm.is_symbol_halted("AAPL")
    # Order should be PENDING_CANCEL
    assert order.status.name == "PENDING_CANCEL"

def test_within_limits():
    config = MockConfig()
    rm = RiskManager(config)
    portfolio = Portfolio(initial_capital=100000)
    order = Order(order_id="1", symbol="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, price=100.0, size=100)
    allowed, _ = rm.check_pre_trade(order, portfolio, 1000)
    assert allowed
