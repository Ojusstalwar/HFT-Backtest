from __future__ import annotations
import logging
from datetime import date
from typing import Any
from engine.types import Position
from .contract_spec import ContractSpecDB

logger = logging.getLogger(__name__)

class RolloverManager:
    """Expiry rollover handling."""
    
    def __init__(self, spec_db: ContractSpecDB):
        self.spec_db = spec_db
        self._rollover_history = []
        
    def days_to_expiry(self, symbol: str, current_date: date) -> int:
        """Calculate days to expiry for a symbol."""
        next_expiry = self.spec_db.get_next_expiry(current_date)
        return (next_expiry - current_date).days

    def should_notify_expiry(self, symbol: str, current_date: date, threshold_days: int = 5) -> bool:
        """Check if expiry is within threshold days."""
        return self.days_to_expiry(symbol, current_date) <= threshold_days

    def generate_rollover_orders(self, symbol: str, position: Position, current_month_price: float, next_month_price: float) -> list[Any]:
        """Generate orders to roll position to next month."""
        close_order = {
            "symbol": symbol,
            "action": "SELL" if position.quantity > 0 else "BUY",
            "quantity": abs(position.quantity),
            "price": current_month_price
        }
        open_order = {
            "symbol": f"{symbol}_NEXT",
            "action": "BUY" if position.quantity > 0 else "SELL",
            "quantity": abs(position.quantity),
            "price": next_month_price
        }
        return [close_order, open_order]

    def calculate_rollover_cost(self, current_price: float, next_price: float, lot_size: int) -> float:
        """Calculate rollover spread cost."""
        return (next_price - current_price) * lot_size

    def get_rollover_cost_history(self) -> list[tuple[str, date, float]]:
        """Get history of rollover costs."""
        return self._rollover_history

    def auto_roll(self, symbol: str, position: Position, prices: dict[str, float]) -> list[Any]:
        """Convenience wrapper for rolling over."""
        curr_price = prices.get(symbol, 0.0)
        next_price = prices.get(f"{symbol}_NEXT", curr_price)
        return self.generate_rollover_orders(symbol, position, curr_price, next_price)
