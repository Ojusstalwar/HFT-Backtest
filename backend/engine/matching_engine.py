from __future__ import annotations

import random

from engine.types import (
    Order, Event, EventType, TradeEvent, Side, Fill, 
    OrderStatus, QueueCancellationModel, CircuitHaltError,
    OrderType, InstrumentType
)
from engine.config import FillModelConfig
from engine.price_bands import PriceBandManager
from engine.auction import AuctionManager


class MatchingEngine:
    """
    Simulated exchange with FIFO queue position tracking.
    """
    def __init__(self, config: FillModelConfig, price_band_manager: PriceBandManager, auction_manager: AuctionManager):
        self.config = config
        self.price_bands = price_band_manager
        self.auctions = auction_manager
        self.orders: dict[str, Order] = {}
        
        # We use standard library random for fill models to allow simple seeding via random.seed() if needed by backtest
        
    def submit_order(self, order: Order, timestamp_ns: int) -> list[Event]:
        """
        Submits an order to the matching engine.
        Returns a list of resulting events (ACK, FILL, etc.).
        """
        # Circuit breaker check
        if self.price_bands.is_halted(order.symbol, timestamp_ns):
            raise CircuitHaltError(f"{order.symbol} is halted at {timestamp_ns}")
            
        # Price band check for Equities
        if order.instrument_type == InstrumentType.EQ and order.price > 0:
            if not self.price_bands.is_within_band(order.symbol, order.price):
                order.status = OrderStatus.REJECTED
                return [Event(
                    timestamp_ns=timestamp_ns,
                    sequence_number=0,
                    type_priority=EventType.ORDER_ACK.value,
                    event_type=EventType.ORDER_ACK,
                    symbol=order.symbol,
                    data={"order_id": order.order_id, "status": "REJECTED", "reason": "PRICE_BAND"}
                )]
                
        self.orders[order.order_id] = order
        order.status = OrderStatus.NEW
        order.timestamp_ns = timestamp_ns
        
        # Queue position should be set by the caller based on L2 depth
        # For simulation, if it is aggressive, we would fill immediately. 
        # (Aggressive behavior walking the book should be implemented by an order router/OMS calling book directly, 
        # but here we focus on passive tracking)
        
        ack = Event(
            timestamp_ns=timestamp_ns,
            sequence_number=0,
            type_priority=EventType.ORDER_ACK.value,
            event_type=EventType.ORDER_ACK,
            symbol=order.symbol,
            data={"order": order}
        )
        return [ack]
        
    def cancel_order(self, order_id: str, timestamp_ns: int) -> Event:
        """
        Attempts to cancel an order.
        """
        if order_id not in self.orders:
            return Event(
                timestamp_ns=timestamp_ns,
                sequence_number=0,
                type_priority=EventType.CANCEL_ACK.value,
                event_type=EventType.CANCEL_ACK,
                symbol="",
                data={"order_id": order_id, "status": "REJECTED", "reason": "UNKNOWN_ORDER"}
            )
            
        order = self.orders[order_id]
        
        if order.status == OrderStatus.FILLED:
            # Race condition: already filled
            return Event(
                timestamp_ns=timestamp_ns,
                sequence_number=0,
                type_priority=EventType.CANCEL_ACK.value,
                event_type=EventType.CANCEL_ACK,
                symbol=order.symbol,
                data={"order_id": order_id, "status": "CANCEL_REJECTED", "reason": "TOO_LATE"}
            )
            
        order.status = OrderStatus.CANCELLED
        return Event(
            timestamp_ns=timestamp_ns,
            sequence_number=0,
            type_priority=EventType.CANCEL_ACK.value,
            event_type=EventType.CANCEL_ACK,
            symbol=order.symbol,
            data={"order": order}
        )
        
    def process_trade(self, trade_event: TradeEvent) -> list[Event]:
        """
        Depletes queue positions and generates fills based on market trades.
        """
        generated_events = []
        for order in list(self.orders.values()):
            if order.symbol != trade_event.symbol:
                continue
                
            if order.status not in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
                continue
                
            # Passive queue depletion
            if order.queue_ahead > 0:
                # Based on cancellation model, we might adjust queue differently, 
                # but standard depletion is by trade size
                order.queue_ahead = max(0, order.queue_ahead - trade_event.size)
            
            # Re-evaluate for fill
            if order.queue_ahead == 0:
                # It's at the front of the queue, subject to fill probability discount
                if random.random() <= self.config.fill_probability_discount:
                    fill_size = min(order.remaining_size, trade_event.size)
                    if fill_size <= 0:
                        continue
                        
                    order.remaining_size -= fill_size
                    order.filled_size += fill_size
                    
                    if order.remaining_size == 0:
                        order.status = OrderStatus.FILLED
                    else:
                        order.status = OrderStatus.PARTIALLY_FILLED
                        
                    fill = Fill(
                        order_id=order.order_id,
                        symbol=order.symbol,
                        side=order.side,
                        price=order.price if order.price > 0 else trade_event.price,
                        size=fill_size,
                        timestamp_ns=trade_event.timestamp_ns,
                        is_maker=True,
                        instrument_type=order.instrument_type
                    )
                    
                    fill_evt = Event(
                        timestamp_ns=trade_event.timestamp_ns,
                        sequence_number=0,
                        type_priority=EventType.FILL.value,
                        event_type=EventType.FILL,
                        symbol=order.symbol,
                        data={"fill": fill}
                    )
                    generated_events.append(fill_evt)
                    
        return generated_events
        
    def halt(self, symbol: str, timestamp_ns: int) -> None:
        """Explicitly halts a symbol (delegated to price_bands if specific time was known, else manual wrapper)."""
        pass # The logic primarily resides in price_bands, this can be extended if OMS needs explicit tracking
        
    def unhalt(self, symbol: str) -> None:
        """Explicitly unhalts a symbol."""
        if symbol in self.price_bands._halts:
            del self.price_bands._halts[symbol]
            
    def process_auction(self, auction_event: Event) -> list[Event]:
        """
        Processes uncrossing fills for orders participating in the call auction.
        """
        # In a complete implementation, this would iterate accumulated orders,
        # find the uncrossing price, generate fills, and return the events.
        return []
