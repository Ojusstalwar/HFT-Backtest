from __future__ import annotations
from collections import deque

from engine.types import Side, BookSnapshot, TradeEvent
from strategies.base_strategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    """
    Short-term order flow momentum strategy.
    
    Tracks recent public trades to calculate net order flow (buy volume vs sell volume).
    Takes a directional position when order flow strongly favors one side.
    """
    def __init__(
        self,
        name: str,
        symbols: list[str],
        flow_window: int = 20,
        flow_threshold: float = 0.6,
        hold_ticks: int = 30,
        order_size: int = 10,
        max_position: int = 50,
        min_volume: int = 100
    ):
        super().__init__(name, symbols)
        self.flow_window = flow_window
        self.flow_threshold = flow_threshold
        self.hold_ticks = hold_ticks
        self.order_size = order_size
        self.max_position = max_position
        self.min_volume = min_volume
        
        # Track recent trades: tuple of (side, qty)
        self.recent_trades: dict[str, deque[tuple[Side, int]]] = {
            s: deque(maxlen=self.flow_window) for s in symbols
        }
        self.ticks_in_position: dict[str, int] = {s: 0 for s in symbols}

    def on_book_update(self, book: BookSnapshot, timestamp: int) -> None:
        symbol = book.symbol
        current_pos = self.positions.get(symbol, 0)
        
        # Handle time-based exit
        if current_pos != 0:
            self.ticks_in_position[symbol] += 1
            if self.ticks_in_position[symbol] >= self.hold_ticks:
                if current_pos > 0:
                    self.place_market_order(symbol, Side.SELL, abs(current_pos))
                else:
                    self.place_market_order(symbol, Side.BUY, abs(current_pos))
                self.ticks_in_position[symbol] = 0

    def on_trade(self, trade: TradeEvent) -> None:
        symbol = trade.symbol
        self.recent_trades[symbol].append((trade.side, trade.qty))
        
        trades = self.recent_trades[symbol]
        if len(trades) < self.flow_window:
            return
            
        buy_volume = sum(qty for side, qty in trades if side == Side.BUY)
        sell_volume = sum(qty for side, qty in trades if side == Side.SELL)
        total_volume = buy_volume + sell_volume
        
        if total_volume < self.min_volume:
            return
            
        net_flow = buy_volume - sell_volume
        flow_ratio = net_flow / total_volume
        
        current_pos = self.positions.get(symbol, 0)
        
        if current_pos == 0:
            if flow_ratio > self.flow_threshold:
                if current_pos + self.order_size <= self.max_position:
                    self.place_market_order(symbol, Side.BUY, self.order_size)
                    self.ticks_in_position[symbol] = 0
            elif flow_ratio < -self.flow_threshold:
                if current_pos - self.order_size >= -self.max_position:
                    self.place_market_order(symbol, Side.SELL, self.order_size)
                    self.ticks_in_position[symbol] = 0
