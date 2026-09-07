from __future__ import annotations
import math
from collections import deque

from engine.types import Side, BookSnapshot, TradeEvent, OrderStatus, Fill
from strategies.base_strategy import BaseStrategy

class MarketMakerStrategy(BaseStrategy):
    """
    Avellaneda-Stoikov market making strategy.
    
    Dynamically adjusts quotes around a reservation price based on current
    inventory and recent volatility.
    """
    def __init__(
        self,
        name: str,
        symbols: list[str],
        spread_bps: float = 10.0,
        inventory_risk_aversion: float = 0.1,
        max_position: int = 100,
        order_size: int = 10,
        volatility_window: int = 100,
        skew_factor: float = 1.0
    ):
        super().__init__(name, symbols)
        self.spread_bps = spread_bps
        self.inventory_risk_aversion = inventory_risk_aversion
        self.max_position = max_position
        self.order_size = order_size
        self.volatility_window = volatility_window
        self.skew_factor = skew_factor
        
        # Internal state tracking
        self.mid_prices: dict[str, deque[float]] = {s: deque(maxlen=self.volatility_window) for s in symbols}
        self.realized_pnl: dict[str, float] = {s: 0.0 for s in symbols}
        self.unrealized_pnl: dict[str, float] = {s: 0.0 for s in symbols}
        self.avg_entry_price: dict[str, float] = {s: 0.0 for s in symbols}
        
    def on_book_update(self, book: BookSnapshot, timestamp: int) -> None:
        symbol = book.symbol
        if not book.bids or not book.asks:
            return
            
        best_bid = book.bids[0].price
        best_ask = book.asks[0].price
        mid_price = (best_bid + best_ask) / 2.0
        
        self.mid_prices[symbol].append(mid_price)
        
        # Calculate PnL
        pos = self.positions.get(symbol, 0)
        if pos != 0:
            self.unrealized_pnl[symbol] = pos * (mid_price - self.avg_entry_price[symbol])
            
        # Need enough data for volatility
        if len(self.mid_prices[symbol]) < 2:
            return
            
        # Calculate rolling volatility (variance)
        prices = list(self.mid_prices[symbol])
        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / (len(prices) - 1)
        
        # 1. Reservation price: R = mid - q * gamma * sigma^2 * tau
        # Assume tau (time remaining) is 1.0 for simplicity as it's continuous
        q = pos
        gamma = self.inventory_risk_aversion
        tau = 1.0
        
        reservation_price = mid_price - (q * gamma * variance * tau) * self.skew_factor
        
        # 2. Optimal spread simplified: delta = spread_bps / 10000 * mid_price
        # Can incorporate full AS formula if desired, but simplified is robust
        spread = (self.spread_bps / 10000.0) * mid_price
        
        # 3. Calculate Bid and Ask
        bid_price = reservation_price - spread / 2.0
        ask_price = reservation_price + spread / 2.0
        
        # Adjust to tick size if necessary (omitted for simplicity, but good practice)
        bid_price = round(bid_price, 2)
        ask_price = round(ask_price, 2)
        
        # 4 & 5. Cancel existing and place new orders if within limits
        self.cancel_all(symbol)
        
        if q + self.order_size <= self.max_position:
            self.place_limit_order(symbol, Side.BUY, bid_price, self.order_size)
            
        if q - self.order_size >= -self.max_position:
            self.place_limit_order(symbol, Side.SELL, ask_price, self.order_size)

    def on_trade(self, trade: TradeEvent) -> None:
        pass

    def on_fill(self, fill: Fill) -> None:
        symbol = fill.symbol
        pos = self.positions.get(symbol, 0)
        avg_px = self.avg_entry_price.get(symbol, 0.0)
        
        qty = getattr(fill, 'size', getattr(fill, 'qty', 0))
        price = fill.price
        
        if fill.side == Side.BUY:
            if pos < 0:
                # Covering short
                cover_qty = min(abs(pos), qty)
                self.realized_pnl[symbol] += cover_qty * (avg_px - price)
                
                remaining = qty - cover_qty
                if remaining > 0:
                    self.avg_entry_price[symbol] = price
            else:
                # Adding to long
                self.avg_entry_price[symbol] = (pos * avg_px + qty * price) / (pos + qty)
        else:
            if pos > 0:
                # Selling long
                cover_qty = min(pos, qty)
                self.realized_pnl[symbol] += cover_qty * (price - avg_px)
                
                remaining = qty - cover_qty
                if remaining > 0:
                    self.avg_entry_price[symbol] = price
            else:
                # Adding to short
                self.avg_entry_price[symbol] = (abs(pos) * avg_px + qty * price) / (abs(pos) + qty)
                
        super().on_fill(fill)
