from __future__ import annotations
import logging
from engine.types import Position, InstrumentType

logger = logging.getLogger(__name__)

class MarginEngine:
    """Simplified SPAN + exposure margin computation."""
    
    def __init__(self):
        self._utilization_history = []
        
    def calculate_span_margin(self, position: Position, underlying_price: float, volatility: float) -> float:
        """Calculate simplified SPAN margin based on 16-scenario scanning."""
        if position.instrument_type == InstrumentType.EQ:
            return 0.0
            
        price_scan_range = 0.1 # 10%
        vol_range = 0.05 # 5%
        
        scenarios = []
        for price_mult in [-3, -2, -1, -0.33, 0.33, 1, 2, 3]:
            for vol_mult in [-1, 1]:
                price_move = price_mult / 3.0 * price_scan_range * volatility
                scenarios.append(abs(price_move) * position.size * underlying_price)
                
        return max(scenarios) if scenarios else 0.0

    def calculate_exposure_margin(self, position: Position, underlying_price: float) -> float:
        """Calculate exposure margin."""
        if position.instrument_type == InstrumentType.FUT:
            contract_value = abs(position.size) * underlying_price
            return contract_value * 0.05 # Simplified 5%
        elif position.instrument_type in [InstrumentType.CE, InstrumentType.PE]:
            contract_value = abs(position.size) * underlying_price
            return contract_value * 0.02 # Simplified
        return 0.0

    def calculate_total_margin(self, position: Position, underlying_price: float, volatility: float) -> float:
        """Calculate SPAN + exposure margin."""
        span = self.calculate_span_margin(position, underlying_price, volatility)
        exposure = self.calculate_exposure_margin(position, underlying_price)
        return span + exposure

    def check_margin_requirement(self, portfolio_positions: list[Position], available_capital: float, prices: dict[str, float], vols: dict[str, float]) -> tuple[bool, float]:
        """Check if portfolio meets margin requirements."""
        total_margin = 0.0
        for pos in portfolio_positions:
            symbol = pos.symbol
            price = prices.get(symbol, 0.0)
            vol = vols.get(symbol, 0.2)
            total_margin += self.calculate_total_margin(pos, price, vol)
            
        ratio = total_margin / available_capital if available_capital > 0 else float('inf')
        return (total_margin <= available_capital, ratio)

    def get_margin_utilization_history(self) -> list[tuple[int, float]]:
        """Get history of margin utilization ratios."""
        return self._utilization_history

    def update_margin(self, portfolio: list[Position], prices: dict[str, float], vols: dict[str, float], timestamp_ns: int):
        """Recalculate and record margin utilization."""
        total_margin = sum(self.calculate_total_margin(pos, prices.get(pos.symbol, 0.0), vols.get(pos.symbol, 0.2)) for pos in portfolio)
        self._utilization_history.append((timestamp_ns, total_margin))
