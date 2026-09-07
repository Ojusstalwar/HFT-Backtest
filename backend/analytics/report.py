from __future__ import annotations

import json
from typing import Any
from pathlib import Path

from engine.config import BacktestConfig
from engine.types import Fill, Position

class ReportGenerator:
    """
    JSON report generation for dashboard consumption.
    """

    @staticmethod
    def generate_report(
        config: BacktestConfig,
        metrics: dict[str, Any],
        markout: dict[str, Any],
        equity_curve: list[tuple[int, float]],
        trades: list[Fill],
        positions: dict[str, Position],
        margin_history: list[tuple[int, float]] | None = None,
        greeks_history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Builds the complete JSON report payload.
        """
        # Extract traceability metadata
        calibration_source = config.latency.calibration_source if config.latency else "UNKNOWN"
        fill_discount_source = config.fill_model.fill_discount_source if config.fill_model else "UNKNOWN"
        rate_source = "N/A"
        if config.greeks and config.greeks.risk_free_rate:
            rate_source = config.greeks.risk_free_rate.rate_source
            
        traceability = {
            "calibration_source": calibration_source,
            "fill_discount_source": fill_discount_source,
            "rate_source": rate_source
        }
        
        # Serialize trades
        trade_log = []
        for t in trades:
            trade_log.append({
                "order_id": t.order_id,
                "symbol": t.symbol,
                "side": t.side.name,
                "price": t.price,
                "size": t.size,
                "timestamp_ns": t.timestamp_ns,
                "is_maker": t.is_maker,
                "instrument_type": t.instrument_type.name,
                "fee": t.fee
            })
            
        # Serialize positions
        pos_data = {}
        for sym, p in positions.items():
            pos_data[sym] = {
                "symbol": p.symbol,
                "instrument_type": p.instrument_type.name,
                "size": p.size,
                "avg_entry_price": p.avg_entry_price,
                "realized_pnl": p.realized_pnl,
                "unrealized_pnl": p.unrealized_pnl,
                "total_fees": p.total_fees
            }
            
        report = {
            "metadata": {
                "start_date": config.start_date,
                "end_date": config.end_date,
                "symbols": config.symbols,
                "initial_capital": config.initial_capital
            },
            "traceability": traceability,
            "metrics": metrics,
            "markout": markout,
            "equity_curve": [{"timestamp_ns": ts, "equity": eq} for ts, eq in equity_curve],
            "trades": trade_log,
            "positions": pos_data
        }
        
        if margin_history is not None:
            report["fno_margin_history"] = [{"timestamp_ns": ts, "margin": m} for ts, m in margin_history]
            
        if greeks_history is not None:
            report["fno_greeks_history"] = greeks_history
            
        return report

    @staticmethod
    def save_report(report_dict: dict[str, Any], output_path: str | Path) -> None:
        """
        Saves the report to a JSON file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2)
