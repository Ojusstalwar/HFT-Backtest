from __future__ import annotations

import math
import numpy as np
from typing import Any

from engine.types import Fill, Side

class MetricsCalculator:
    """
    Standard performance metrics for HFT strategies.
    Computes session and multi-day risk-adjusted metrics, drawdown, and round-trip trade statistics.
    """

    @staticmethod
    def _newey_west_variance(returns: np.ndarray, lag: int) -> float:
        n = len(returns)
        if n < 2:
            return 0.0
        
        mean_ret = np.mean(returns)
        demeaned = returns - mean_ret
        
        var = np.sum(demeaned**2) / n
        
        for j in range(1, lag + 1):
            if n > j:
                gamma_j = np.sum(demeaned[j:] * demeaned[:-j]) / n
                weight = 1.0 - (j / (lag + 1.0))
                var += 2.0 * weight * gamma_j
                
        return float(var)

    @classmethod
    def session_sharpe(cls, returns: list[float] | np.ndarray) -> float:
        """
        Calculates the observed Sharpe ratio across the current simulation session.
        Session Sharpe = (mean / nw_std) * sqrt(N_bars)
        """
        rets = np.array(returns)
        if len(rets) < 2:
            return 0.0
            
        mean_ret = float(np.mean(rets))
        lag = min(len(rets) // 4, int(4 * ((len(rets) / 100.0) ** (2.0 / 9.0))))
        nw_var = cls._newey_west_variance(rets, lag)
        
        if nw_var <= 1e-12:
            return 0.0
            
        nw_std = math.sqrt(nw_var)
        return float((mean_ret / nw_std) * math.sqrt(len(rets)))

    @classmethod
    def daily_sharpe(cls, returns: list[float] | np.ndarray, sampling_freq_hz: float) -> float:
        """
        Calculates the daily (per 6.5-hour trading day) Sharpe ratio.
        """
        rets = np.array(returns)
        if len(rets) < 2:
            return 0.0
            
        mean_ret = float(np.mean(rets))
        lag = min(len(rets) // 4, int(4 * ((len(rets) / 100.0) ** (2.0 / 9.0))))
        nw_var = cls._newey_west_variance(rets, lag)
        
        if nw_var <= 1e-12:
            return 0.0
            
        nw_std = math.sqrt(nw_var)
        samples_per_day = sampling_freq_hz * 6.5 * 3600
        return float((mean_ret / nw_std) * math.sqrt(samples_per_day))

    @classmethod
    def annualized_sharpe(cls, returns: list[float] | np.ndarray, sampling_freq_hz: float) -> float:
        """
        Calculates annualized Sharpe ratio.
        For intraday session runs (<= 1 day), annualizing with sqrt(252*N_bars) causes extreme
        sample-size blowups. Hence for single session runs, we return the daily session Sharpe.
        """
        rets = np.array(returns)
        if len(rets) < 2:
            return 0.0
            
        return cls.daily_sharpe(returns, sampling_freq_hz)

    @staticmethod
    def sortino_ratio(returns: list[float] | np.ndarray, sampling_freq_hz: float) -> float:
        """
        Calculates daily Sortino ratio for the session.
        """
        rets = np.array(returns)
        if len(rets) < 2:
            return 0.0
            
        samples_per_day = sampling_freq_hz * 6.5 * 3600
        mean_ret = float(np.mean(rets))
        
        downside_rets = rets[rets < 0]
        if len(downside_rets) < 2:
            return float('inf') if mean_ret > 0 else 0.0
            
        downside_std = float(np.std(downside_rets, ddof=1))
        if downside_std <= 1e-12:
            return float('inf') if mean_ret > 0 else 0.0
            
        return float((mean_ret / downside_std) * math.sqrt(samples_per_day))

    @staticmethod
    def max_drawdown(equity_curve: list[float] | np.ndarray) -> tuple[float, int, int]:
        """
        Returns (max_dd_pct, peak_idx, trough_idx)
        """
        eq = np.array(equity_curve)
        if len(eq) < 2:
            return 0.0, 0, 0
            
        running_max = np.maximum.accumulate(eq)
        running_max = np.where(running_max == 0, 1e-12, running_max)
        
        dd = (running_max - eq) / running_max
        trough_idx = int(np.argmax(dd))
        
        if trough_idx == 0:
            return 0.0, 0, 0
            
        peak_idx = int(np.argmax(eq[:trough_idx+1]))
        max_dd_pct = float(dd[trough_idx])
        
        return max_dd_pct, peak_idx, trough_idx

    @classmethod
    def calmar_ratio(cls, returns: list[float] | np.ndarray, max_dd: float) -> float:
        """
        Calculates Calmar ratio.
        """
        rets = np.array(returns)
        if len(rets) < 2 or max_dd <= 1e-12:
            return 0.0
            
        total_return = float(np.sum(rets))
        return float(total_return / max_dd)

    @staticmethod
    def _get_round_trips(trades: list[Fill]) -> list[dict]:
        """
        Match fills FIFO to compute round-trip PnL and duration.
        Returns list of dicts with 'pnl' and 'duration_ns'.
        """
        open_positions = []  # list of (price, size, side, timestamp_ns, fee_per_unit)
        round_trips = []
        
        for fill in trades:
            remaining_size = fill.size
            fee_per_unit = fill.fee / fill.size if fill.size > 0 else 0.0
            
            while remaining_size > 0 and open_positions and open_positions[0][2] != fill.side:
                open_p, open_s, open_side, open_t, open_fpu = open_positions[0]
                
                match_size = min(remaining_size, open_s)
                
                # Calculate PnL for this matched portion
                if open_side == Side.BUY:
                    # Bought open_p, Sold fill.price
                    pnl = (fill.price - open_p) * match_size
                else:
                    # Sold open_p, Bought fill.price
                    pnl = (open_p - fill.price) * match_size
                    
                # Subtract fees for the matched size from both entry and exit
                pnl -= (open_fpu + fee_per_unit) * match_size
                
                duration = fill.timestamp_ns - open_t
                round_trips.append({'pnl': pnl, 'duration_ns': duration})
                
                remaining_size -= match_size
                if match_size == open_s:
                    open_positions.pop(0)
                else:
                    open_positions[0] = (open_p, open_s - match_size, open_side, open_t, open_fpu)
                    
            if remaining_size > 0:
                open_positions.append((fill.price, remaining_size, fill.side, fill.timestamp_ns, fee_per_unit))
                
        return round_trips

    @classmethod
    def profit_factor(cls, trades: list[Fill]) -> float:
        trips = cls._get_round_trips(trades)
        gross_profit = sum(t['pnl'] for t in trips if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trips if t['pnl'] < 0))
        
        if gross_loss == 0.0:
            return float('inf') if gross_profit > 0 else 0.0
        return float(gross_profit / gross_loss)

    @classmethod
    def win_rate(cls, trades: list[Fill]) -> float:
        trips = cls._get_round_trips(trades)
        if not trips:
            return 0.0
        wins = sum(1 for t in trips if t['pnl'] > 0)
        return float(wins / len(trips))

    @classmethod
    def avg_trade_duration(cls, trades: list[Fill]) -> float:
        """
        Returns average trade duration in seconds.
        """
        trips = cls._get_round_trips(trades)
        if not trips:
            return 0.0
        avg_ns = sum(t['duration_ns'] for t in trips) / len(trips)
        return float(avg_ns / 1e9)

    @classmethod
    def pnl_per_trade(cls, trades: list[Fill]) -> float:
        trips = cls._get_round_trips(trades)
        if not trips:
            return 0.0
        return float(sum(t['pnl'] for t in trips) / len(trips))

    @staticmethod
    def fill_ratio(orders_placed: int, fills_received: int) -> float:
        if orders_placed == 0:
            return 0.0
        return float(fills_received / orders_placed)

    @staticmethod
    def quote_to_trade_ratio(orders_placed: int, fills_received: int) -> float:
        if fills_received == 0:
            return float('inf')
        return float(orders_placed / fills_received)

    @classmethod
    def compute_all(cls, equity_curve: list[float] | np.ndarray, trades: list[Fill], orders_placed: int, sampling_freq_hz: float) -> dict[str, Any]:
        eq = np.array(equity_curve)
        if len(eq) > 1:
            prev_eq = eq[:-1]
            prev_eq = np.where(prev_eq == 0, 1e-12, prev_eq)
            returns = (eq[1:] - prev_eq) / prev_eq
        else:
            returns = np.array([])
            
        max_dd, peak, trough = cls.max_drawdown(eq)
        fills_received = len(trades)
        
        return {
            "session_sharpe": cls.session_sharpe(returns),
            "daily_sharpe": cls.daily_sharpe(returns, sampling_freq_hz),
            "annualized_sharpe": cls.annualized_sharpe(returns, sampling_freq_hz),
            "sortino_ratio": cls.sortino_ratio(returns, sampling_freq_hz),
            "max_drawdown_pct": max_dd,
            "max_drawdown_peak_idx": peak,
            "max_drawdown_trough_idx": trough,
            "calmar_ratio": cls.calmar_ratio(returns, max_dd),
            "profit_factor": cls.profit_factor(trades),
            "win_rate": cls.win_rate(trades),
            "avg_trade_duration_s": cls.avg_trade_duration(trades),
            "pnl_per_trade": cls.pnl_per_trade(trades),
            "fill_ratio": cls.fill_ratio(orders_placed, fills_received),
            "quote_to_trade_ratio": cls.quote_to_trade_ratio(orders_placed, fills_received),
            "total_trades": len(cls._get_round_trips(trades)),
            "total_orders": orders_placed,
            "total_fills": fills_received
        }
