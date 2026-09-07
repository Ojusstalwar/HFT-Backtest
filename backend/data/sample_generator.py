from __future__ import annotations

import math
from datetime import datetime
import numpy as np

from engine.types import Event, EventType, Side, PriceLevel, BookSnapshot

class SampleDataGenerator:
    """
    Synthetic market data generator for testing strategies and the backtester.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def _round_to_tick(self, price: float, tick_size: float) -> float:
        return round(price / tick_size) * tick_size

    def generate_tick_data(
        self, 
        symbol: str, 
        num_ticks: int, 
        start_price: float, 
        volatility: float, 
        tick_size: float = 0.05
    ) -> list[Event]:
        """
        Generates tick data using a Geometric Brownian Motion with mean reversion.
        """
        events = []
        current_time_ns = int(datetime.utcnow().timestamp() * 1e9)
        current_price = start_price
        
        # Mean reversion parameters
        kappa = 0.1
        theta = start_price
        dt = 1.0  # 1 second step logically for the drift
        
        for i in range(num_ticks):
            # Poisson arrival for time between ticks (lambda = 2 per sec)
            dt_ns = int(self.rng.exponential(1.0 / 2.0) * 1e9)
            current_time_ns += dt_ns
            
            # Ornstein-Uhlenbeck style mean reversion + GBM volatility
            dW = self.rng.normal(0, math.sqrt(dt))
            drift = kappa * (theta - current_price) * dt
            shock = volatility * current_price * dW
            
            current_price += drift + shock
            tick_price = self._round_to_tick(current_price, tick_size)
            
            # Random size and side
            size = int(self.rng.lognormal(mean=4.0, sigma=1.0))
            if size <= 0:
                size = 1
            side = Side.BUY if self.rng.random() > 0.5 else Side.SELL
            
            events.append(Event(
                timestamp_ns=current_time_ns,
                sequence_number=i,
                type_priority=EventType.TRADE.value,
                event_type=EventType.TRADE,
                symbol=symbol,
                data={
                    "price": tick_price,
                    "size": size,
                    "side": side
                }
            ))
            
        return events

    def generate_l2_data(
        self, 
        symbol: str, 
        num_snapshots: int, 
        start_price: float, 
        num_levels: int = 10,
        tick_size: float = 0.05
    ) -> list[Event]:
        """
        Generates order book snapshots with realistic Bid/Ask depth.
        """
        events = []
        current_time_ns = int(datetime.utcnow().timestamp() * 1e9)
        current_mid = start_price
        
        for i in range(num_snapshots):
            dt_ns = int(self.rng.exponential(0.1) * 1e9)
            current_time_ns += dt_ns
            
            # Random walk for mid price
            current_mid += self.rng.normal(0, 0.5) * tick_size
            current_mid = self._round_to_tick(current_mid, tick_size)
            
            # Generate spread (1 to 5 ticks)
            spread_ticks = self.rng.integers(1, 6)
            best_bid = current_mid - (spread_ticks * tick_size / 2.0)
            best_ask = current_mid + (spread_ticks * tick_size / 2.0)
            
            best_bid = self._round_to_tick(best_bid, tick_size)
            best_ask = self._round_to_tick(best_ask, tick_size)
            
            if best_bid >= best_ask:
                best_bid = best_ask - tick_size
                
            bids = []
            asks = []
            
            # Generate levels with decaying size
            base_size = self.rng.integers(100, 1000)
            
            for lvl in range(num_levels):
                bid_price = best_bid - (lvl * tick_size)
                ask_price = best_ask + (lvl * tick_size)
                
                # Size decays exponentially further from mid
                decay = math.exp(-0.2 * lvl)
                bid_size = int(base_size * decay * self.rng.uniform(0.8, 1.2))
                ask_size = int(base_size * decay * self.rng.uniform(0.8, 1.2))
                
                bids.append(PriceLevel(price=bid_price, size=max(1, bid_size), order_count=self.rng.integers(1, 5)))
                asks.append(PriceLevel(price=ask_price, size=max(1, ask_size), order_count=self.rng.integers(1, 5)))
                
            snapshot = BookSnapshot(
                symbol=symbol,
                timestamp_ns=current_time_ns,
                bids=bids,
                asks=asks
            )
            
            events.append(Event(
                timestamp_ns=current_time_ns,
                sequence_number=i,
                type_priority=EventType.BOOK_UPDATE.value,
                event_type=EventType.BOOK_UPDATE,
                symbol=symbol,
                data=snapshot
            ))
            
        return events

    def generate_correlated_pair(
        self, 
        sym_a: str, 
        sym_b: str, 
        num_ticks: int, 
        correlation: float = 0.95, 
        start_price_a: float = 1000.0, 
        start_price_b: float = 500.0,
        tick_size: float = 0.05
    ) -> list[Event]:
        """
        Generates two correlated price series for stat-arb testing.
        """
        events = []
        current_time_ns = int(datetime.utcnow().timestamp() * 1e9)
        
        price_a = start_price_a
        price_b = start_price_b
        
        for i in range(num_ticks):
            current_time_ns += int(self.rng.exponential(0.5) * 1e9)
            
            # Generate correlated normals
            z1 = self.rng.normal(0, 1)
            z2 = self.rng.normal(0, 1)
            z_a = z1
            z_b = correlation * z1 + math.sqrt(1 - correlation**2) * z2
            
            # Occasional divergence/cointegration shock
            if self.rng.random() < 0.05:
                # Random shock to break correlation briefly
                z_b += self.rng.normal(0, 3)
                
            # Mean revert the spread between the two back to original ratio
            target_ratio = start_price_a / start_price_b
            current_ratio = price_a / price_b
            ratio_diff = target_ratio - current_ratio
            
            price_a += z_a * 0.5 + (ratio_diff * 0.1 * price_b)
            price_b += z_b * 0.25
            
            tick_a = self._round_to_tick(price_a, tick_size)
            tick_b = self._round_to_tick(price_b, tick_size)
            
            # Add event A
            events.append(Event(
                timestamp_ns=current_time_ns,
                sequence_number=i * 2,
                type_priority=EventType.TRADE.value,
                event_type=EventType.TRADE,
                symbol=sym_a,
                data={"price": tick_a, "size": int(self.rng.lognormal(4, 1)), "side": Side.BUY}
            ))
            
            # Add event B
            events.append(Event(
                timestamp_ns=current_time_ns + 1000,  # Slight delay
                sequence_number=i * 2 + 1,
                type_priority=EventType.TRADE.value,
                event_type=EventType.TRADE,
                symbol=sym_b,
                data={"price": tick_b, "size": int(self.rng.lognormal(4, 1)), "side": Side.SELL}
            ))
            
        return events

    def generate_full_day(self, symbol: str, start_price: float, tick_size: float = 0.05) -> list[Event]:
        """
        Complete trading day: pre-open, continuous, post-close.
        Realistic volume profile: U-shaped (high at open/close, low mid-day).
        """
        events = []
        base_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        start_ns = int(base_date.timestamp() * 1e9)
        
        # 1. Pre-open Auction (9:00 - 9:08)
        # Generate AUCTION event at 9:08
        auction_ns = start_ns + (8 * 60 * int(1e9))
        events.append(Event(
            timestamp_ns=auction_ns,
            sequence_number=0,
            type_priority=EventType.AUCTION.value,
            event_type=EventType.AUCTION,
            symbol=symbol,
            data={"indicative_price": start_price, "indicative_volume": 10000}
        ))
        
        # 2. Continuous Session (9:15 - 15:30)
        continuous_start = start_ns + (15 * 60 * int(1e9))
        continuous_end = start_ns + ((6 * 60 + 30) * 60 * int(1e9))
        
        current_time_ns = continuous_start
        current_price = start_price
        seq = 1
        
        while current_time_ns < continuous_end:
            # U-shape volume/arrival rate
            time_ratio = (current_time_ns - continuous_start) / (continuous_end - continuous_start)
            # High at 0.0 and 1.0, low at 0.5
            intensity = 1.0 + 4.0 * (time_ratio - 0.5)**2
            
            dt_ns = int(self.rng.exponential(0.5 / intensity) * 1e9)
            current_time_ns += dt_ns
            
            if current_time_ns >= continuous_end:
                break
                
            current_price += self.rng.normal(0, 0.2) * tick_size
            current_price = self._round_to_tick(current_price, tick_size)
            
            events.append(Event(
                timestamp_ns=current_time_ns,
                sequence_number=seq,
                type_priority=EventType.TRADE.value,
                event_type=EventType.TRADE,
                symbol=symbol,
                data={"price": current_price, "size": int(100 * intensity), "side": Side.BUY if self.rng.random() > 0.5 else Side.SELL}
            ))
            seq += 1
            
        return events
