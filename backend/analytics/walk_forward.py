from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import itertools
from typing import Any, Type

from engine.config import BacktestConfig
from engine.types import Event
from analytics.metrics import MetricsCalculator

@dataclass
class DateRange:
    start: str
    end: str

@dataclass
class WalkForwardResult:
    oos_sharpe: float
    oos_max_dd: float
    is_sharpe: float
    parameter_stability: dict[str, float]
    window_results: list[dict[str, Any]]
    overfitting_ratio: float = field(init=False)

    def __post_init__(self) -> None:
        if self.oos_sharpe > 0:
            self.overfitting_ratio = self.is_sharpe / self.oos_sharpe
        else:
            self.overfitting_ratio = float('inf')

class WalkForwardHarness:
    """
    Walk-forward / rolling-window out-of-sample evaluation harness.
    """

    def __init__(self, train_days: int = 20, test_days: int = 5, step_days: int = 5, param_grid: dict[str, list[Any]] | None = None):
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.param_grid = param_grid or {}

    def generate_windows(self, start_date: str, end_date: str) -> list[tuple[DateRange, DateRange]]:
        """
        Generates a list of (train_range, test_range) pairs.
        Dates are parsed as YYYY-MM-DD.
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        windows = []
        current_train_start = start_dt
        
        while True:
            current_train_end = current_train_start + timedelta(days=self.train_days - 1)
            current_test_start = current_train_end + timedelta(days=1)
            current_test_end = current_test_start + timedelta(days=self.test_days - 1)
            
            if current_test_start > end_dt:
                break
                
            train_range = DateRange(
                start=current_train_start.strftime("%Y-%m-%d"),
                end=current_train_end.strftime("%Y-%m-%d")
            )
            
            # Cap the test end at the overall end_date
            actual_test_end = min(current_test_end, end_dt)
            test_range = DateRange(
                start=current_test_start.strftime("%Y-%m-%d"),
                end=actual_test_end.strftime("%Y-%m-%d")
            )
            
            windows.append((train_range, test_range))
            current_train_start += timedelta(days=self.step_days)
            
        return windows

    def _filter_data_by_date(self, data: list[Event], d_range: DateRange) -> list[Event]:
        # Simple string comparison works for YYYY-MM-DD prefix if timestamp_ns can be mapped,
        # but events have timestamp_ns. Let's assume start/end are converted to ns.
        start_ns = int(datetime.strptime(d_range.start, "%Y-%m-%d").timestamp() * 1e9)
        end_dt = datetime.strptime(d_range.end, "%Y-%m-%d")
        # Include the entire end day
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        end_ns = int(end_dt.timestamp() * 1e9)
        
        return [e for e in data if start_ns <= e.timestamp_ns <= end_ns]

    def _generate_param_combinations(self) -> list[dict[str, Any]]:
        if not self.param_grid:
            return [{}]
            
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        combinations = []
        
        for prod in itertools.product(*values):
            combinations.append(dict(zip(keys, prod)))
            
        return combinations

    def run(self, strategy_class: Type, strategy_params: dict[str, Any], data: list[Event], backtester_config: BacktestConfig) -> WalkForwardResult:
        """
        Executes the walk-forward harness.
        """
        # Import inside to avoid circular dependencies if backtester imports analytics
        from engine.backtester import Backtester
        
        windows = self.generate_windows(backtester_config.start_date, backtester_config.end_date)
        param_combinations = self._generate_param_combinations()
        
        all_window_results = []
        is_sharpes = []
        oos_sharpes = []
        oos_drawdowns = []
        best_params_history = {k: [] for k in self.param_grid.keys()}
        
        for train_range, test_range in windows:
            train_data = self._filter_data_by_date(data, train_range)
            test_data = self._filter_data_by_date(data, test_range)
            
            best_is_sharpe = -float('inf')
            best_params = {}
            
            # 1 & 2. Optimize params on train set
            for p_combo in param_combinations:
                current_params = {**strategy_params, **p_combo}
                strategy = strategy_class(**current_params)
                
                if hasattr(strategy, 'discover_pairs'):
                    strategy.discover_pairs(train_data)
                if hasattr(strategy, 'freeze_pairs'):
                    strategy.freeze_pairs()
                    
                bt_is = Backtester(backtester_config)
                result_is = bt_is.run(strategy, train_data)
                
                sharpe = result_is.metrics.get('annualized_sharpe', 0.0)
                if sharpe > best_is_sharpe:
                    best_is_sharpe = sharpe
                    best_params = p_combo
                    
            if not best_params:
                best_params = {}
                
            for k, v in best_params.items():
                best_params_history[k].append(v)
                
            # 3. Run backtest on test set with best params
            final_params = {**strategy_params, **best_params}
            test_strategy = strategy_class(**final_params)
            
            if hasattr(test_strategy, 'discover_pairs'):
                test_strategy.discover_pairs(train_data)
            if hasattr(test_strategy, 'freeze_pairs'):
                test_strategy.freeze_pairs()
                
            bt_oos = Backtester(backtester_config)
            result_oos = bt_oos.run(test_strategy, test_data)
            
            oos_sharpe = result_oos.metrics.get('annualized_sharpe', 0.0)
            oos_dd = result_oos.metrics.get('max_drawdown_pct', 0.0)
            
            all_window_results.append({
                'train_range': train_range,
                'test_range': test_range,
                'best_params': best_params,
                'is_sharpe': best_is_sharpe,
                'oos_sharpe': oos_sharpe,
                'oos_max_dd': oos_dd,
                'metrics': result_oos.metrics
            })
            
            is_sharpes.append(best_is_sharpe)
            oos_sharpes.append(oos_sharpe)
            oos_drawdowns.append(oos_dd)
            
        # Aggregate results
        agg_is_sharpe = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
        agg_oos_sharpe = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0.0
        agg_oos_dd = max(oos_drawdowns) if oos_drawdowns else 0.0
        
        param_stability = {}
        import numpy as np
        for k, vals in best_params_history.items():
            try:
                param_stability[k] = float(np.std(vals))
            except Exception:
                param_stability[k] = 0.0
                
        return WalkForwardResult(
            oos_sharpe=agg_oos_sharpe,
            oos_max_dd=agg_oos_dd,
            is_sharpe=agg_is_sharpe,
            parameter_stability=param_stability,
            window_results=all_window_results
        )
