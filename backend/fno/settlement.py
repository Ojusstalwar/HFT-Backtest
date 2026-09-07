from __future__ import annotations
import logging
from datetime import date
from typing import Any
from engine.types import Position, InstrumentType

logger = logging.getLogger(__name__)

class SettlementManager:
    """Physical settlement logic for F&O."""
    
    def check_physical_delivery(self, position: Position, expiry_date: date, current_date: date) -> bool:
        """Check if ITM stock option at expiry requires physical delivery."""
        if current_date != expiry_date:
            return False
        # Simplified check: Requires true underlying price to evaluate ITM
        return True

    def calculate_delivery_margin(self, position: Position, underlying_price: float, days_to_expiry: int) -> float:
        """Calculate delivery margin leading up to expiry."""
        if position.instrument.instrument_type not in (InstrumentType.CALL, InstrumentType.PUT):
            return 0.0
            
        delivery_value = abs(position.quantity) * underlying_price
        
        if days_to_expiry == 4:
            return delivery_value * 0.10
        elif days_to_expiry == 3:
            return delivery_value * 0.25
        elif days_to_expiry == 2:
            return delivery_value * 0.45
        elif days_to_expiry == 1:
            return delivery_value * 0.70
        elif days_to_expiry == 0:
            return delivery_value * 1.00
        return 0.0

    def calculate_exercise_stt(self, settlement_price: float, lot_size: int) -> float:
        """Calculate STT on option exercise. 0.125% of full notional."""
        return 0.00125 * settlement_price * lot_size

    def process_expiry(self, positions: list[Position], settlement_prices: dict[str, float], current_date: date) -> list[Any]:
        """Process positions on expiry."""
        events = []
        for pos in positions:
            symbol = pos.instrument.symbol
            price = settlement_prices.get(symbol, 0.0)
            if pos.instrument.instrument_type in (InstrumentType.CALL, InstrumentType.PUT):
                # ITM options -> physical delivery events
                events.append({"type": "physical_delivery", "position": pos})
            elif pos.instrument.instrument_type == InstrumentType.FUTURES:
                # Futures -> final MTM settlement
                events.append({"type": "mtm_settlement", "position": pos})
        return events
