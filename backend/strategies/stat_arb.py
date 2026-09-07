from __future__ import annotations
import math
import numpy as np
import pandas as pd
from collections import deque

from engine.types import Side, BookSnapshot, TradeEvent, PairDiscoveryViolationError
from strategies.base_strategy import BaseStrategy

class StatArbStrategy(BaseStrategy):
    """
    Statistical arbitrage (pairs trading) strategy.
    
    Identifies cointegrated pairs during a walk-forward training phase, and 
    trades their spread based on z-score mean reversion during the out-of-sample phase.
    """
    def __init__(
        self,
        name: str,
        symbols: list[str],
        z_entry: float = 2.0,
        z_exit: float = 0.5,
        z_stop: float = 4.0,
        lookback_window: int = 100,
        order_size: int = 10,
        max_position: int = 50
    ):
        super().__init__(name, symbols)
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.z_stop = z_stop
        self.lookback_window = lookback_window
        self.order_size = order_size
        self.max_position = max_position
        
        self.pairs: list[tuple[str, str]] = []
        self.hedge_ratios: dict[tuple[str, str], float] = {}
        
        self._is_oos_phase: bool = False
        
        # State tracking for each pair
        self.spread_history: dict[tuple[str, str], deque[float]] = {}
        self.pair_positions: dict[tuple[str, str], int] = {}
        
        # Latest prices for calculating current spread
        self.latest_prices: dict[str, float] = {}

    def discover_pairs(self, data: pd.DataFrame) -> list[tuple[str, str]]:
        """
        Discovers cointegrated pairs using Engle-Granger test.
        Raises PairDiscoveryViolationError if called in OOS phase.
        
        data: pd.DataFrame where index is time and columns are symbols with their prices.
        """
        if self._is_oos_phase:
            raise PairDiscoveryViolationError(
                "discover_pairs() called during out-of-sample test phase. "
                "Pair selection must be restricted to the training window "
                "to prevent data snooping. This is a strategy logic error."
            )
            
        import statsmodels.tsa.stattools as ts
        
        discovered = []
        symbols = list(data.columns)
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1 = symbols[i]
                s2 = symbols[j]
                
                # Simple OLS to find hedge ratio
                y = data[s1].values
                x = data[s2].values
                
                # Check for valid data
                if len(y) < 2 or len(x) < 2 or np.isnan(y).any() or np.isnan(x).any():
                    continue
                    
                x_with_const = np.column_stack((np.ones(len(x)), x))
                try:
                    beta = np.linalg.lstsq(x_with_const, y, rcond=None)[0]
                    hedge_ratio = beta[1]
                except np.linalg.LinAlgError:
                    continue
                
                spread = y - hedge_ratio * x
                
                # Cointegration test (Engle-Granger)
                try:
                    coint_result = ts.adfuller(spread)
                    p_value = coint_result[1]
                except Exception:
                    continue
                
                if p_value < 0.05:
                    pair = (s1, s2)
                    discovered.append(pair)
                    self.hedge_ratios[pair] = hedge_ratio
                    self.spread_history[pair] = deque(maxlen=self.lookback_window)
                    self.pair_positions[pair] = 0
                    
        self.pairs = discovered
        return discovered

    def freeze_pairs(self) -> None:
        """Locks discovered pairs and prevents further discovery."""
        self._is_oos_phase = True

    def on_book_update(self, book: BookSnapshot, timestamp: int) -> None:
        symbol = book.symbol
        if not book.bids or not book.asks:
            return
            
        mid_price = (book.bids[0].price + book.asks[0].price) / 2.0
        self.latest_prices[symbol] = mid_price
        
        # Evaluate all pairs involving this symbol
        for pair in self.pairs:
            sA, sB = pair
            if symbol not in (sA, sB):
                continue
                
            if sA not in self.latest_prices or sB not in self.latest_prices:
                continue
                
            price_A = self.latest_prices[sA]
            price_B = self.latest_prices[sB]
            hedge_ratio = self.hedge_ratios[pair]
            
            spread = price_A - hedge_ratio * price_B
            history = self.spread_history[pair]
            history.append(spread)
            
            if len(history) < self.lookback_window:
                continue
                
            mean_spread = sum(history) / len(history)
            variance = sum((x - mean_spread) ** 2 for x in history) / (len(history) - 1)
            std_spread = math.sqrt(variance) if variance > 0 else 1e-6
            
            z_score = (spread - mean_spread) / std_spread
            current_pos = self.pair_positions[pair]
            
            # Logic: |z| > z_entry -> enter, |z| < z_exit -> exit, |z| > z_stop -> stop
            if current_pos == 0:
                if z_score < -self.z_entry and abs(z_score) < self.z_stop:
                    # Buy spread: Buy A, Sell B
                    if self.positions.get(sA, 0) + self.order_size <= self.max_position:
                        self.place_market_order(sA, Side.BUY, self.order_size)
                        # Size for B adjusted by hedge ratio roughly, or just fixed ratio
                        qty_B = max(1, int(self.order_size * hedge_ratio))
                        self.place_market_order(sB, Side.SELL, qty_B)
                        self.pair_positions[pair] = 1
                elif z_score > self.z_entry and abs(z_score) < self.z_stop:
                    # Sell spread: Sell A, Buy B
                    if self.positions.get(sA, 0) - self.order_size >= -self.max_position:
                        self.place_market_order(sA, Side.SELL, self.order_size)
                        qty_B = max(1, int(self.order_size * hedge_ratio))
                        self.place_market_order(sB, Side.BUY, qty_B)
                        self.pair_positions[pair] = -1
            else:
                # Exit logic
                if abs(z_score) < self.z_exit or abs(z_score) > self.z_stop:
                    if current_pos == 1:
                        # Close long spread
                        self.place_market_order(sA, Side.SELL, self.order_size)
                        qty_B = max(1, int(self.order_size * hedge_ratio))
                        self.place_market_order(sB, Side.BUY, qty_B)
                    elif current_pos == -1:
                        # Close short spread
                        self.place_market_order(sA, Side.BUY, self.order_size)
                        qty_B = max(1, int(self.order_size * hedge_ratio))
                        self.place_market_order(sB, Side.SELL, qty_B)
                    self.pair_positions[pair] = 0

    def on_trade(self, trade: TradeEvent) -> None:
        pass
