from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Optional

from engine.types import Fill, Position, Order, OrderType, Side, InstrumentType, ContractSpec
from engine.fees import FeeCalculator

logger = logging.getLogger(__name__)

class Portfolio:
    """
    Position tracking and PnL computation.
    """
    def __init__(self, initial_capital: float = 0.0) -> None:
        self.initial_capital = initial_capital
        self._positions: Dict[str, Position] = {}
        self._fees: float = 0.0
        self._realized_pnl: float = 0.0
        self._equity_curve: List[Tuple[int, float]] = []
        self._trade_log: List[Fill] = []
        self._contract_specs: Dict[str, ContractSpec] = {}

    def add_contract_spec(self, symbol: str, spec: ContractSpec) -> None:
        """Add contract specification for F&O lot sizes etc."""
        self._contract_specs[symbol] = spec

    def process_fill(self, fill: Fill, fee_calculator: FeeCalculator) -> None:
        """
        Updates position, PnL, and fees.
        Handles both opening and closing trades.
        """
        self._trade_log.append(fill)
        
        symbol = fill.symbol
        inst_type = InstrumentType.EQ
        if symbol in self._contract_specs:
            inst_type = self._contract_specs[symbol].instrument_type
            
        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol, 
                instrument_type=inst_type,
                size=0, 
                avg_entry_price=0.0
            )
            
        position = self._positions[symbol]
        
        # Calculate fees before changing position
        fee = fee_calculator.calculate_trade_fees(fill, instrument_type=inst_type, position_before=position)
        self._fees += fee
        
        fill_qty = fill.size if fill.side == Side.BUY else -fill.size
        new_qty = position.size + fill_qty
        
        # Closing a position
        if (position.size > 0 and fill_qty < 0) or (position.size < 0 and fill_qty > 0):
            closed_qty = min(abs(position.size), abs(fill_qty))
            pnl = 0.0
            if position.size > 0:  # Long, closing with a sell
                pnl = (fill.price - position.avg_entry_price) * closed_qty
            else:  # Short, closing with a buy
                pnl = (position.avg_entry_price - fill.price) * closed_qty
                
            # Contract spec multiplier
            multiplier = self._contract_specs[symbol].lot_size if symbol in self._contract_specs else 1
            self._realized_pnl += pnl * multiplier
            position.realized_pnl += pnl * multiplier
            
            # If reversing position, update average price for remaining
            if (position.size > 0 and new_qty < 0) or (position.size < 0 and new_qty > 0):
                position.avg_entry_price = fill.price
        # Opening/adding to position
        else:
            total_value = (position.avg_entry_price * abs(position.size)) + (fill.price * abs(fill_qty))
            position.avg_entry_price = total_value / abs(new_qty) if new_qty != 0 else 0.0

        position.size = new_qty

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        return self._positions

    def get_total_pnl(self) -> float:
        """Get realized + unrealized PnL."""
        unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())
        return self._realized_pnl + unrealized

    def mark_to_market(self, symbol: str, current_price: float) -> None:
        """Update unrealized PnL for a symbol."""
        position = self._positions.get(symbol)
        if position and position.size != 0:
            multiplier = self._contract_specs[symbol].lot_size if symbol in self._contract_specs else 1
            if position.size > 0:
                position.unrealized_pnl = (current_price - position.avg_entry_price) * position.size * multiplier
            else:
                position.unrealized_pnl = (position.avg_entry_price - current_price) * abs(position.size) * multiplier

    def mark_to_market_all(self, price_map: Dict[str, float]) -> None:
        """Update unrealized PnL for all symbols."""
        for symbol, price in price_map.items():
            self.mark_to_market(symbol, price)

    def get_equity(self) -> float:
        """Get total equity (initial + pnl - fees)."""
        return self.initial_capital + self.get_total_pnl() - self._fees

    def get_equity_curve(self) -> List[Tuple[int, float]]:
        """Get equity curve."""
        return self._equity_curve

    def record_equity_snapshot(self, timestamp_ns: int) -> None:
        """Record current equity to curve."""
        self._equity_curve.append((timestamp_ns, self.get_equity()))

    def flatten_position(self, symbol: str) -> Optional[Order]:
        """Generate a market order to close position."""
        position = self._positions.get(symbol)
        if not position or position.size == 0:
            return None
            
        side = Side.SELL if position.size > 0 else Side.BUY
        return Order(
            order_id=f"flatten_{symbol}",
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            price=0.0,
            size=abs(position.size),
            remaining_size=abs(position.size)
        )
