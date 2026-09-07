from __future__ import annotations

import logging
from typing import Dict, List, Optional

from engine.types import Order, Event, Fill, OrderStatus, OrderType, Side

logger = logging.getLogger(__name__)

class OMS:
    """
    Order Management System.
    Tracks the full lifecycle of orders in the HFT backtester.
    """
    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._next_order_id: int = 1

    def _generate_order_id(self) -> str:
        order_id = str(self._next_order_id)
        self._next_order_id += 1
        return order_id

    def submit_order(self, order: Order) -> Order:
        """
        Submit a new order.
        Sets status to PENDING_NEW and assigns order_id if not present.
        """
        if not order.order_id:
            order.order_id = self._generate_order_id()
        
        if order.order_id in self._orders:
            raise ValueError(f"Order ID {order.order_id} already exists.")
            
        order.status = OrderStatus.PENDING_NEW
        self._orders[order.order_id] = order
        return order

    def handle_ack(self, event: Event) -> None:
        """
        Handle an order acknowledgement from the venue.
        Transitions PENDING_NEW to NEW.
        """
        order_id = getattr(event, 'order_id', None)
        if not order_id and hasattr(event, 'data') and isinstance(event.data, dict):
            order_id = event.data.get('order_id')
            if not order_id and 'order' in event.data:
                order_id = getattr(event.data['order'], 'order_id', None)
                
        if not order_id or order_id not in self._orders:
            logger.warning(f"Ack for unknown order: {order_id}")
            return
            
        order = self._orders[order_id]
        if order.status not in (OrderStatus.PENDING_NEW, OrderStatus.NEW):
            raise ValueError(f"Invalid state transition for Ack: {order.status} -> NEW")
            
        order.status = OrderStatus.NEW

    def handle_fill(self, fill: Fill) -> None:
        """
        Handle an order fill.
        Transitions NEW/PARTIALLY_FILLED to PARTIALLY_FILLED/FILLED.
        """
        order_id = fill.order_id
        if order_id not in self._orders:
            logger.warning(f"Fill for unknown order: {order_id}")
            return
            
        order = self._orders[order_id]
        
        if order.status not in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED):
            raise ValueError(f"Invalid state transition for Fill: {order.status}")
            
        # Update filled size
        order.filled_size += fill.size
        # Update fill_price_avg
        if order.filled_size > 0:
            total_value = (order.fill_price_avg * (order.filled_size - fill.size)) + (fill.price * fill.size)
            order.fill_price_avg = total_value / order.filled_size
            
        if order.filled_size >= order.size:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

    def handle_cancel_ack(self, event: Event) -> None:
        """
        Handle an order cancel acknowledgement.
        Transitions PENDING_CANCEL to CANCELLED.
        Guards against cancel/fill races.
        """
        order_id = getattr(event, 'order_id', None)
        if not order_id and hasattr(event, 'data') and isinstance(event.data, dict):
            order_id = event.data.get('order_id')
            if not order_id and 'order' in event.data:
                order_id = getattr(event.data['order'], 'order_id', None)
                
        if not order_id or order_id not in self._orders:
            logger.warning(f"Cancel ack for unknown order: {order_id}")
            return
            
        order = self._orders[order_id]
        
        if order.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            # Race condition detected: filled at same timestamp
            logger.warning(f"Cancel/fill race detected for order {order_id}. Converting to CANCEL_REJECTED.")
            order.status = OrderStatus.CANCEL_REJECTED
            return
            
        if order.status not in (OrderStatus.PENDING_CANCEL, OrderStatus.CANCELLED):
            raise ValueError(f"Invalid state transition for Cancel Ack: {order.status} -> CANCELLED")
            
        order.status = OrderStatus.CANCELLED

    def request_cancel(self, order_id: str) -> Order:
        """
        Request cancellation of an active order.
        Transitions NEW/PARTIALLY_FILLED to PENDING_CANCEL.
        """
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found.")
            
        order = self._orders[order_id]
        
        if order.status not in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
            raise ValueError(f"Cannot cancel order in state {order.status}")
            
        order.status = OrderStatus.PENDING_CANCEL
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all active orders, optionally filtered by symbol."""
        active_statuses = (OrderStatus.PENDING_NEW, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING_CANCEL)
        return [
            order for order in self._orders.values()
            if order.status in active_statuses and (symbol is None or order.symbol == symbol)
        ]

    def get_all_orders(self) -> List[Order]:
        """Get all tracked orders."""
        return list(self._orders.values())
