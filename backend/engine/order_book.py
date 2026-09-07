from __future__ import annotations

from typing import Optional

from engine.types import Event, EventType, TradeEvent, BookSnapshot, PriceLevel

class OrderBook:
    """
    L2 order book state engine.
    Maintains bids and asks for a symbol and supports depth fetching.
    """
    def __init__(self, symbol: str, max_levels: int = 20):
        self.symbol = symbol
        self.max_levels = max_levels
        self.bids: list[PriceLevel] = []
        self.asks: list[PriceLevel] = []
        self.last_traded_price: float | None = None
        self.last_traded_size: int | None = None
        self.last_update_time: int = 0
        
    def update(self, event: Event) -> None:
        """Processes a BOOK_UPDATE event."""
        if event.event_type != EventType.BOOK_UPDATE or event.symbol != self.symbol:
            return
            
        self.last_update_time = event.timestamp_ns
        
        if isinstance(event.data, BookSnapshot):
            self.bids = sorted(event.data.bids, key=lambda x: x.price, reverse=True)[:self.max_levels]
            self.asks = sorted(event.data.asks, key=lambda x: x.price)[:self.max_levels]
        elif isinstance(event.data, dict):
            if "bids" in event.data:
                # Bids should be sorted descending
                self.bids = sorted(event.data["bids"], key=lambda x: x.price, reverse=True)[:self.max_levels]
            if "asks" in event.data:
                # Asks should be sorted ascending
                self.asks = sorted(event.data["asks"], key=lambda x: x.price)[:self.max_levels]
            
    def process_trade(self, trade_event: TradeEvent) -> None:
        """Updates last traded price and size."""
        if trade_event.symbol != self.symbol:
            return
            
        self.last_traded_price = trade_event.price
        self.last_traded_size = trade_event.size
        self.last_update_time = max(self.last_update_time, trade_event.timestamp_ns)
        
    def get_snapshot(self) -> BookSnapshot:
        """Returns a deepish copy of the current order book state."""
        return BookSnapshot(
            symbol=self.symbol,
            timestamp_ns=self.last_update_time,
            bids=[PriceLevel(p.price, p.size, p.order_count) for p in self.bids],
            asks=[PriceLevel(p.price, p.size, p.order_count) for p in self.asks]
        )
        
    def get_depth_at_price(self, price: float) -> int:
        """Returns the size available at a specific price level."""
        # Due to float comparison, use a small epsilon for tick size matching
        epsilon = 1e-6
        for level in self.bids:
            if abs(level.price - price) < epsilon:
                return level.size
        for level in self.asks:
            if abs(level.price - price) < epsilon:
                return level.size
        return 0

    @property
    def mid_price(self) -> float | None:
        return self.get_snapshot().mid_price

    @property
    def spread(self) -> float | None:
        return self.get_snapshot().spread

    @property
    def micro_price(self) -> float | None:
        return self.get_snapshot().micro_price

    @property
    def order_book_imbalance(self) -> float | None:
        return self.get_snapshot().order_book_imbalance
