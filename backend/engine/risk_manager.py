from __future__ import annotations

import logging
from collections import deque
from typing import Tuple, Dict, Any

from engine.types import Order, Event
from engine.config import BacktestConfig
from engine.portfolio import Portfolio

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Pre-trade and real-time risk checks.
    """
    def __init__(self, config: BacktestConfig, oms: Any = None) -> None:
        self.config = config
        self.oms = oms
        self.halted_symbols: set[str] = set()
        
        # Rate limiting: Sliding window counter (timestamp_ns)
        self.order_history: deque[int] = deque()
        self.rate_limit_window_ns = 1_000_000_000 # 1 second window
        self.max_orders_per_sec = config.max_orders_per_sec if hasattr(config, 'max_orders_per_sec') else 100

    def check_pre_trade(self, order: Order, portfolio: Portfolio, timestamp_ns: int) -> Tuple[bool, str]:
        """
        Pre-trade risk checks.
        Returns (allowed, reason)
        """
        # 1. Halted symbol
        if self.is_symbol_halted(order.symbol):
            return False, f"Symbol {order.symbol} is halted."

        # 2. Max single order size
        if hasattr(self.config, 'max_order_size') and order.size > self.config.max_order_size:
            return False, f"Order size {order.size} exceeds max limit {self.config.max_order_size}."

        # 3. Rate limiting
        self._cleanup_order_history(timestamp_ns)
        if len(self.order_history) >= self.max_orders_per_sec:
            return False, f"Rate limit exceeded: > {self.max_orders_per_sec} orders/sec."
            
        # 4. Max position limit per instrument
        current_pos = portfolio.get_position(order.symbol)
        pos_size = current_pos.size if current_pos else 0
        new_size = pos_size + order.size if order.side.name == 'BUY' else pos_size - order.size
        if hasattr(self.config, 'max_position_size') and abs(new_size) > self.config.max_position_size:
            return False, f"Order would exceed max position size {self.config.max_position_size}."
            
        # 5. Price band check placeholder
        # In a real system, you'd check PriceBandManager here.

        self.order_history.append(timestamp_ns)
        return True, ""

    def _cleanup_order_history(self, current_timestamp_ns: int) -> None:
        """Remove orders older than the sliding window."""
        cutoff = current_timestamp_ns - self.rate_limit_window_ns
        while self.order_history and self.order_history[0] < cutoff:
            self.order_history.popleft()

    def check_drawdown(self, portfolio: Portfolio, timestamp_ns: int) -> bool:
        """
        Check if daily drawdown exceeds threshold (kill-switch).
        Returns True if threshold exceeded.
        """
        if not hasattr(self.config, 'max_drawdown_pct'):
            return False
            
        max_drawdown_pct = self.config.max_drawdown_pct
        current_equity = portfolio.get_equity()
        
        # Assuming initial capital is tracked in portfolio or config
        initial_capital = portfolio.initial_capital
        if initial_capital > 0:
            drawdown_pct = (initial_capital - current_equity) / initial_capital
            if drawdown_pct > max_drawdown_pct:
                logger.error(f"Kill switch activated: Drawdown {drawdown_pct:.2%} exceeds max {max_drawdown_pct:.2%}")
                return True
                
        return False

    def on_circuit_halt(self, event: Event) -> None:
        """
        Mark symbol as halted, cancel all pending orders via OMS.
        """
        symbol = getattr(event, 'symbol', None)
        if symbol:
            self.halted_symbols.add(symbol)
            logger.warning(f"Circuit halt detected for {symbol}. Canceling active orders.")
            if self.oms:
                active_orders = self.oms.get_active_orders(symbol)
                for order in active_orders:
                    try:
                        self.oms.request_cancel(order.order_id)
                    except ValueError as e:
                        logger.error(f"Failed to cancel order {order.order_id} on halt: {e}")

    def on_circuit_resume(self, symbol: str) -> None:
        """Unmark symbol as halted."""
        if symbol in self.halted_symbols:
            self.halted_symbols.remove(symbol)
            logger.info(f"Circuit resumed for {symbol}.")

    def is_symbol_halted(self, symbol: str) -> bool:
        """Check if symbol is halted."""
        return symbol in self.halted_symbols

    def get_daily_pnl(self, portfolio: Portfolio) -> float:
        """Get daily PnL from portfolio."""
        return portfolio.get_total_pnl()
