from __future__ import annotations

import logging
import csv
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CorporateAction:
    date: str
    symbol: str
    action_type: str
    ratio: float
    new_symbol: Optional[str] = None

class CorporateActionManager:
    """
    Corporate action adjustments (Splits, Bonus, Name changes).
    """
    def __init__(self) -> None:
        self.actions_by_date: Dict[str, List[CorporateAction]] = {}
        self.symbol_changes: Dict[str, str] = {}

    def load_actions(self, csv_path: str) -> None:
        """
        Load corporate actions from CSV.
        Expected columns: date, symbol, action_type, ratio, [new_symbol]
        action_type: 'split', 'bonus', 'symbol_change'
        """
        try:
            with open(csv_path, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date = row['date']
                    symbol = row['symbol']
                    action_type = row['action_type']
                    ratio = float(row.get('ratio', 1.0))
                    new_symbol = row.get('new_symbol')
                    
                    action = CorporateAction(
                        date=date,
                        symbol=symbol,
                        action_type=action_type,
                        ratio=ratio,
                        new_symbol=new_symbol
                    )
                    
                    if date not in self.actions_by_date:
                        self.actions_by_date[date] = []
                    self.actions_by_date[date].append(action)
                    
                    if action_type == 'symbol_change' and new_symbol:
                        self.symbol_changes[symbol] = new_symbol
        except Exception as e:
            logger.error(f"Failed to load corporate actions from {csv_path}: {e}")

    def adjust_price(self, price: float, symbol: str, date: str) -> float:
        """Apply split/bonus ratio to historical prices."""
        actions = self.actions_by_date.get(date, [])
        adj_price = price
        for action in actions:
            if action.symbol == symbol:
                if action.action_type in ('split', 'bonus'):
                    adj_price /= action.ratio
        return adj_price

    def adjust_quantity(self, qty: int, symbol: str, date: str) -> int:
        """Apply split/bonus ratio to historical quantities."""
        actions = self.actions_by_date.get(date, [])
        adj_qty = float(qty)
        for action in actions:
            if action.symbol == symbol:
                if action.action_type in ('split', 'bonus'):
                    adj_qty *= action.ratio
        return int(adj_qty)

    def get_new_symbol(self, old_symbol: str, date: str) -> str:
        """Returns new symbol after rename, or old if no change."""
        actions = self.actions_by_date.get(date, [])
        for action in actions:
            if action.symbol == old_symbol and action.action_type == 'symbol_change' and action.new_symbol:
                return action.new_symbol
        # Fallback to general lookup if not specific to date
        return self.symbol_changes.get(old_symbol, old_symbol)

    def get_actions_for_date(self, date: str) -> List[CorporateAction]:
        """Get all corporate actions for a specific date."""
        return self.actions_by_date.get(date, [])
