from __future__ import annotations

import datetime

from engine.types import SessionType, Order, Side

class AuctionManager:
    """
    Pre-open and post-close call-auction session modeling.
    """
    def __init__(self):
        self._orders: list[Order] = []
        
    def get_session(self, timestamp_ns: int) -> SessionType:
        """Returns the current trading session based on the timestamp (IST)."""
        dt = datetime.datetime.fromtimestamp(
            timestamp_ns / 1_000_000_000.0, 
            tz=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        )
        hm = dt.hour * 100 + dt.minute
        
        if 900 <= hm < 908:
            return SessionType.PRE_OPEN_ORDER_ENTRY
        elif 908 <= hm < 912:
            return SessionType.PRE_OPEN_MATCHING
        elif 912 <= hm < 915:
            return SessionType.PRE_OPEN_BUFFER
        elif 915 <= hm < 1530:
            return SessionType.CONTINUOUS
        elif 1540 <= hm < 1600:
            return SessionType.POST_CLOSE_AUCTION
        else:
            return SessionType.CLOSED
            
    def accumulate_order(self, order: Order) -> None:
        """Stores an order placed during the call-auction phase."""
        self._orders.append(order)
        
    def compute_uncrossing_price(self, previous_close: float = 0.0) -> tuple[float, int]:
        """
        Computes the uncrossing price P* and matched volume.
        Logic: maximize volume, tie-break minimum surplus, then proximity to previous_close.
        Returns (price, volume).
        """
        if not self._orders:
            return 0.0, 0
            
        prices = set()
        for o in self._orders:
            if o.price > 0:
                prices.add(o.price)
                
        # If all were market orders, default to previous close (simplified)
        if not prices:
            prices.add(previous_close)
            
        best_price = 0.0
        max_volume = 0
        min_surplus = float('inf')
        
        for p in sorted(prices):
            # For a given uncrossing price p:
            # Eligible buy size: limit price >= p, or market order (price == 0)
            buy_vol = sum(o.size for o in self._orders if o.side == Side.BUY and (o.price >= p or o.price == 0))
            # Eligible sell size: limit price <= p, or market order (price == 0)
            sell_vol = sum(o.size for o in self._orders if o.side == Side.SELL and (o.price <= p or o.price == 0))
            
            match_vol = min(buy_vol, sell_vol)
            surplus = abs(buy_vol - sell_vol)
            
            if match_vol > max_volume:
                max_volume = match_vol
                min_surplus = surplus
                best_price = p
            elif match_vol == max_volume:
                if surplus < min_surplus:
                    min_surplus = surplus
                    best_price = p
                elif surplus == min_surplus:
                    # proximity to prev close
                    if abs(p - previous_close) < abs(best_price - previous_close):
                        best_price = p
                        
        return best_price, max_volume
        
    def is_continuous_session(self, timestamp_ns: int) -> bool:
        """Helper to quickly check if the market is in the continuous trading session."""
        return self.get_session(timestamp_ns) == SessionType.CONTINUOUS
