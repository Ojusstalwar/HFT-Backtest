from __future__ import annotations
from abc import ABC, abstractmethod
import time

from engine.types import (
    Side, OrderType, Order, Fill, BookSnapshot, TradeEvent, 
    Greeks, ContractSpec, InstrumentType, OrderStatus, 
    PairDiscoveryViolationError, Event, EventType
)

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies in the HFT backtester.
    
    Provides the core lifecycle callbacks and helper methods for order submission
    and state management.
    """
    def __init__(self, name: str, symbols: list[str]):
        self.name = name
        self.symbols = symbols
        self._order_callback = None  # Set by backtester
        self._cancel_callback = None
        self._cancel_all_callback = None
        self._greeks_callback = None
        self._contract_spec_callback = None
        self._margin_callback = None
        self._next_order_id = 1
        
        self.active_orders: dict[str, Order] = {}
        self.positions: dict[str, int] = {symbol: 0 for symbol in symbols}

    # --- Market data callbacks ---
    @abstractmethod
    def on_book_update(self, book: BookSnapshot, timestamp: int) -> None:
        """Called when a new order book snapshot is received."""
        pass

    @abstractmethod
    def on_trade(self, trade: TradeEvent) -> None:
        """Called when a public trade occurs."""
        pass

    # --- Order lifecycle callbacks ---
    def on_fill(self, fill: Fill) -> None:
        """Called when an order is partially or fully filled."""
        fill_size = getattr(fill, 'size', getattr(fill, 'qty', 0))
        if fill.side == Side.BUY:
            self.positions[fill.symbol] += fill_size
        else:
            self.positions[fill.symbol] -= fill_size

    def on_order_update(self, order: Order) -> None:
        """Called when an order status changes (e.g., accepted, canceled)."""
        if order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FILLED):
            self.active_orders.pop(order.order_id, None)
        else:
            self.active_orders[order.order_id] = order

    # --- Session callbacks ---
    def on_auction(self, event: Event) -> None:
        pass  # Default no-op

    def on_halt(self, event: Event) -> None:
        pass  # Default no-op

    def on_session_start(self, timestamp: int) -> None:
        pass  # Default no-op

    def on_session_end(self, timestamp: int) -> None:
        pass  # Default no-op

    # --- F&O callbacks (default no-op) ---
    def on_expiry_approaching(self, symbol: str, days: int) -> None:
        pass

    def on_margin_warning(self, utilization: float) -> None:
        pass

    # --- Timer ---
    def on_timer(self, timestamp: int) -> None:
        pass

    # --- Order submission helpers ---
    def place_limit_order(self, symbol: str, side: Side, price: float, size: int) -> str:
        """Places a limit order and returns the generated order ID."""
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            size=size,
            remaining_size=size,
            status=OrderStatus.NEW,
            timestamp_ns=int(time.time() * 1e9)
        )
        self.active_orders[order_id] = order
        if self._order_callback:
            self._order_callback(order)
        return order_id

    def place_market_order(self, symbol: str, side: Side, size: int) -> str:
        """Places a market order and returns the generated order ID."""
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            price=0.0,
            size=size,
            remaining_size=size,
            status=OrderStatus.NEW,
            timestamp_ns=int(time.time() * 1e9)
        )
        self.active_orders[order_id] = order
        if self._order_callback:
            self._order_callback(order)
        return order_id

    def cancel_order(self, order_id: str) -> None:
        """Cancels an existing order by its ID."""
        if self._cancel_callback:
            self._cancel_callback(order_id)

    def cancel_all(self, symbol: str | None = None) -> None:
        """Cancels all active orders, optionally filtered by symbol."""
        if self._cancel_all_callback:
            self._cancel_all_callback(symbol)
        else:
            # Fallback to canceling one by one
            for order_id, order in list(self.active_orders.items()):
                if symbol is None or order.symbol == symbol:
                    self.cancel_order(order_id)

    # --- F&O helpers ---
    def get_greeks(self, symbol: str) -> Greeks | None:
        if self._greeks_callback:
            return self._greeks_callback(symbol)
        return None

    def get_contract_spec(self, symbol: str) -> ContractSpec | None:
        if self._contract_spec_callback:
            return self._contract_spec_callback(symbol)
        return None

    def get_margin_available(self) -> float:
        if self._margin_callback:
            return self._margin_callback()
        return float('inf')

    # --- Internal ---
    def _generate_order_id(self) -> str:
        order_id = f"{self.name}_{self._next_order_id}"
        self._next_order_id += 1
        return order_id
