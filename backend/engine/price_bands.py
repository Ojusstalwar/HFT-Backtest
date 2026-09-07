from __future__ import annotations

import datetime

from engine.types import PriceBand

class PriceBandManager:
    """
    NSE price band and circuit breaker logic.
    """
    def __init__(self):
        self._bands: dict[str, PriceBand] = {}
        self._halts: dict[str, int] = {}  # symbol -> halt_expiry_timestamp_ns
        
    def set_band(self, symbol: str, reference_price: float, band_pct: float) -> None:
        """Sets the daily price band for a symbol."""
        lower = reference_price * (1.0 - band_pct)
        upper = reference_price * (1.0 + band_pct)
        self._bands[symbol] = PriceBand(
            symbol=symbol,
            lower=lower,
            upper=upper,
            band_pct=band_pct,
            reference_price=reference_price
        )
        
    def get_band(self, symbol: str, timestamp_ns: int) -> PriceBand | None:
        """Gets the currently active price band for a symbol."""
        return self._bands.get(symbol)
        
    def is_within_band(self, symbol: str, price: float) -> bool:
        """Checks if a given price is strictly within the band (inclusive)."""
        band = self._bands.get(symbol)
        if not band:
            return True  # If no band is explicitly set, we allow the order.
        return band.lower <= price <= band.upper
        
    def trigger_circuit_breaker(self, index_symbol: str, move_pct: float, timestamp_ns: int) -> int:
        """
        Calculates and applies market-wide circuit breakers.
        Returns the halt duration in nanoseconds.
        """
        # Parse timestamp to IST hour and minute
        dt = datetime.datetime.fromtimestamp(
            timestamp_ns / 1_000_000_000.0, 
            tz=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        )
        time_hm = dt.hour * 100 + dt.minute
        
        abs_move = abs(move_pct)
        halt_duration_minutes = 0
        
        if abs_move >= 0.20:
            # 20% move: halted for remainder of day
            halt_duration_minutes = max(0, 16 * 60 - (dt.hour * 60 + dt.minute))
        elif abs_move >= 0.15:
            # 15% move
            if time_hm < 1300:
                halt_duration_minutes = 105  # 1h 45m
            elif time_hm < 1430:
                halt_duration_minutes = 45
            else:
                halt_duration_minutes = max(0, 16 * 60 - (dt.hour * 60 + dt.minute))
        elif abs_move >= 0.10:
            # 10% move
            if time_hm < 1300:
                halt_duration_minutes = 45
            elif time_hm < 1430:
                halt_duration_minutes = 15
            else:
                halt_duration_minutes = 0
                
        halt_duration_ns = halt_duration_minutes * 60 * 1_000_000_000
        
        if halt_duration_ns > 0:
            # Apply market-wide halt
            self._halts["MARKET"] = timestamp_ns + halt_duration_ns
            
        return halt_duration_ns

    def is_halted(self, symbol: str, timestamp_ns: int) -> bool:
        """Checks if a symbol (or the entire market) is currently halted."""
        halt_expiry = self._halts.get(symbol, 0)
        market_halt_expiry = self._halts.get("MARKET", 0)
        
        return timestamp_ns < halt_expiry or timestamp_ns < market_halt_expiry
