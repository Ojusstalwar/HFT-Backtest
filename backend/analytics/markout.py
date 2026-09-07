from __future__ import annotations

import bisect
from typing import Any

from engine.types import Fill, Side

class MarkoutAnalyzer:
    """
    Post-trade markout curve and realized spread analysis.
    """
    HORIZONS = [
        10_000_000,      # 10ms
        100_000_000,     # 100ms
        1_000_000_000,   # 1s
        5_000_000_000,   # 5s
        30_000_000_000,  # 30s
        60_000_000_000   # 60s
    ]

    @staticmethod
    def _get_price_at_time(mid_price_series: list[tuple[int, float]], target_ts: int) -> float | None:
        """
        Binary search for the most recent mid price at or before target_ts.
        mid_price_series is a list of (timestamp_ns, mid_price) sorted by time.
        """
        if not mid_price_series:
            return None
            
        # Extract just timestamps for bisect
        timestamps = [ts for ts, _ in mid_price_series]
        idx = bisect.bisect_right(timestamps, target_ts)
        
        if idx == 0:
            # target_ts is before the first recorded mid price
            return mid_price_series[0][1]
            
        return mid_price_series[idx - 1][1]

    @classmethod
    def compute_markout(cls, fills: list[Fill], mid_price_series: list[tuple[int, float]]) -> dict[int, float]:
        """
        Computes average markout across all fills for each horizon in basis points (bps).
        markout_bps(h) = Side * ((mid_price(t+h) - exec_price) / exec_price) * 10,000
        """
        if not fills or not mid_price_series:
            return {h: 0.0 for h in cls.HORIZONS}
            
        markouts_sum = {h: 0.0 for h in cls.HORIZONS}
        counts = {h: 0 for h in cls.HORIZONS}
        
        for fill in fills:
            if fill.price <= 0:
                continue
            side_multiplier = 1.0 if fill.side == Side.BUY else -1.0
            
            for h in cls.HORIZONS:
                target_ts = fill.timestamp_ns + h
                future_price = cls._get_price_at_time(mid_price_series, target_ts)
                
                if future_price is not None:
                    # Basis points: (delta / entry_price) * 10,000
                    pnl_bps = (side_multiplier * (future_price - fill.price) / fill.price) * 10000.0
                    markouts_sum[h] += pnl_bps
                    counts[h] += 1
                    
        return {h: (markouts_sum[h] / counts[h] if counts[h] > 0 else 0.0) for h in cls.HORIZONS}

    @classmethod
    def compute_realized_spread(cls, fills: list[Fill], mid_price_series: list[tuple[int, float]]) -> dict[int, float]:
        """
        Computes realized spread across all fills for each horizon in basis points (bps).
        realized_spread_bps(h) = 2 * Side * ((exec_price - mid_price(t+h)) / exec_price) * 10,000
        """
        if not fills or not mid_price_series:
            return {h: 0.0 for h in cls.HORIZONS}
            
        spreads_sum = {h: 0.0 for h in cls.HORIZONS}
        counts = {h: 0 for h in cls.HORIZONS}
        
        for fill in fills:
            if fill.price <= 0:
                continue
            side_multiplier = 1.0 if fill.side == Side.BUY else -1.0
            
            for h in cls.HORIZONS:
                target_ts = fill.timestamp_ns + h
                future_price = cls._get_price_at_time(mid_price_series, target_ts)
                
                if future_price is not None:
                    spread_bps = 2.0 * (side_multiplier * (fill.price - future_price) / fill.price) * 10000.0
                    spreads_sum[h] += spread_bps
                    counts[h] += 1
                    
        return {h: (spreads_sum[h] / counts[h] if counts[h] > 0 else 0.0) for h in cls.HORIZONS}

    @classmethod
    def get_markout_by_side(cls, fills: list[Fill], mid_price_series: list[tuple[int, float]]) -> dict[str, dict[int, float]]:
        """
        Computes markout separated by side ('buy' and 'sell').
        """
        buy_fills = [f for f in fills if f.side == Side.BUY]
        sell_fills = [f for f in fills if f.side == Side.SELL]
        
        return {
            'buy': cls.compute_markout(buy_fills, mid_price_series),
            'sell': cls.compute_markout(sell_fills, mid_price_series)
        }
