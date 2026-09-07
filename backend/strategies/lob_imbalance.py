from __future__ import annotations

from engine.types import Side, BookSnapshot, TradeEvent
from strategies.base_strategy import BaseStrategy

class LOBImbalanceStrategy(BaseStrategy):
    """
    Limit Order Book Imbalance strategy.
    
    Trades based on the microstructural order book imbalance (OBI) signal, smoothed
    via an Exponential Moving Average (EMA). Trades aggressively (market orders) when
    imbalance crosses a threshold.
    """
    def __init__(
        self,
        name: str,
        symbols: list[str],
        imbalance_threshold: float = 0.3,
        hold_ticks: int = 50,
        order_size: int = 10,
        max_position: int = 50,
        levels_to_consider: int = 5,
        ema_alpha: float = 0.1
    ):
        super().__init__(name, symbols)
        self.imbalance_threshold = imbalance_threshold
        self.hold_ticks = hold_ticks
        self.order_size = order_size
        self.max_position = max_position
        self.levels_to_consider = levels_to_consider
        self.ema_alpha = ema_alpha
        
        self.smoothed_obi: dict[str, float] = {s: 0.0 for s in symbols}
        self.ticks_in_position: dict[str, int] = {s: 0 for s in symbols}

    def on_book_update(self, book: BookSnapshot, timestamp: int) -> None:
        symbol = book.symbol
        
        bid_vol = sum(level.qty for level in book.bids[:self.levels_to_consider])
        ask_vol = sum(level.qty for level in book.asks[:self.levels_to_consider])
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return
            
        # 1. Calculate multi-level OBI
        raw_obi = (bid_vol - ask_vol) / total_vol
        
        # 2. Apply EMA smoothing
        self.smoothed_obi[symbol] = (
            self.ema_alpha * raw_obi + 
            (1.0 - self.ema_alpha) * self.smoothed_obi[symbol]
        )
        
        current_obi = self.smoothed_obi[symbol]
        current_pos = self.positions.get(symbol, 0)
        
        # Time-based exit and signal reversal exit
        if current_pos != 0:
            self.ticks_in_position[symbol] += 1
            should_exit = False
            
            if self.ticks_in_position[symbol] >= self.hold_ticks:
                should_exit = True
            elif current_pos > 0 and current_obi < -self.imbalance_threshold:
                should_exit = True
            elif current_pos < 0 and current_obi > self.imbalance_threshold:
                should_exit = True
                
            if should_exit:
                if current_pos > 0:
                    self.place_market_order(symbol, Side.SELL, abs(current_pos))
                else:
                    self.place_market_order(symbol, Side.BUY, abs(current_pos))
                self.ticks_in_position[symbol] = 0
                return

        # Entry logic
        if current_pos == 0:
            if current_obi > self.imbalance_threshold:
                if current_pos + self.order_size <= self.max_position:
                    self.place_market_order(symbol, Side.BUY, self.order_size)
                    self.ticks_in_position[symbol] = 0
            elif current_obi < -self.imbalance_threshold:
                if current_pos - self.order_size >= -self.max_position:
                    self.place_market_order(symbol, Side.SELL, self.order_size)
                    self.ticks_in_position[symbol] = 0

    def on_trade(self, trade: TradeEvent) -> None:
        pass
