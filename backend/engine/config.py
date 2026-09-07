"""
Configuration loader and validator for the HFT backtesting framework.

All configurable parameters (latency, fill model, fees, Greeks inputs) are
loaded from YAML and validated at startup. The backtester fails fast if any
required field is missing.

Three traceability fields are required and stamped into every report:
  - calibration_source  (latency)
  - fill_discount_source (fill model)
  - rate_source (risk-free rate for Greeks)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from engine.types import ConfigurationError, QueueCancellationModel

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYWORDS = {"placeholder", "demo", "example", "uncalibrated"}


def _warn_if_placeholder(field_name: str, value: str) -> None:
    """Log a warning if a traceability field looks like a placeholder."""
    lower = value.lower()
    for kw in _PLACEHOLDER_KEYWORDS:
        if kw in lower:
            logger.warning(
                "⚠️  %s = '%s' appears to be a placeholder. "
                "Results are not suitable for real trading decisions.",
                field_name, value,
            )
            return


# ---------------------------------------------------------------------------
# Latency Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LatencyPhaseConfig:
    distribution: str  # "lognormal", "constant", "gamma"
    params: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class LatencyConfig:
    feed: LatencyPhaseConfig
    processing: LatencyPhaseConfig
    order_ingress: LatencyPhaseConfig
    ack_egress: LatencyPhaseConfig
    calibration_source: str  # Required traceability field
    bounds_min_us: float = 1.0
    bounds_max_us: float = 1_000_000.0


# ---------------------------------------------------------------------------
# Fill Model Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FillModelConfig:
    fill_probability_discount: float  # Required — no default
    fill_discount_source: str         # Required traceability field
    queue_cancellation_model: QueueCancellationModel = QueueCancellationModel.PESSIMISTIC


# ---------------------------------------------------------------------------
# Fee Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FeeConfig:
    stamp_duty_rate: float   # e.g. 0.00003 for 0.003%
    stamp_duty_state: str    # e.g. "Maharashtra"
    broker_commission_per_order: float = 0.0  # Flat fee per order if applicable


# ---------------------------------------------------------------------------
# Greeks Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RiskFreeRateConfig:
    type: str  # "constant" or "time_series"
    rate_source: str  # Required traceability field
    value: float | None = None  # Required if type == "constant"
    time_series_path: str | None = None  # Required if type == "time_series"


@dataclass(slots=True)
class DividendYieldConfig:
    type: str  # "per_symbol_schedule", "constant", "index_aggregate"
    schedule_path: str | None = None
    constant_yield: float | None = None


@dataclass(slots=True)
class GreeksConfig:
    risk_free_rate: RiskFreeRateConfig
    dividend_yield: DividendYieldConfig


# ---------------------------------------------------------------------------
# Master Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BacktestConfig:
    """Master configuration for a backtest run."""
    latency: LatencyConfig
    fill_model: FillModelConfig
    fees: FeeConfig
    greeks: GreeksConfig | None = None  # Only required if trading options
    data_path: str = ""
    symbols: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 10_000_000.0  # ₹1 crore default
    corporate_actions_path: str | None = None
    max_position_limit: int = 10_000
    max_drawdown_pct: float = 0.05  # 5% daily drawdown kill-switch
    max_order_rate_per_sec: int = 100


def _parse_latency_phase(d: dict) -> LatencyPhaseConfig:
    return LatencyPhaseConfig(
        distribution=d["distribution"],
        params=d.get("params", {}),
    )


def _validate_latency(raw: dict) -> LatencyConfig:
    """Parse and validate latency configuration."""
    if "calibration_source" not in raw:
        raise ConfigurationError(
            "latency.calibration_source is required. "
            "Specify the source of your latency measurements "
            "(e.g., 'measured from broker OMS logs, March 2026')."
        )
    phases = raw.get("latency", raw)
    # Support both nested and flat layouts
    if "feed" not in phases and "latency" in raw:
        phases = raw["latency"]

    config = LatencyConfig(
        feed=_parse_latency_phase(phases["feed"]),
        processing=_parse_latency_phase(phases["processing"]),
        order_ingress=_parse_latency_phase(phases["order_ingress"]),
        ack_egress=_parse_latency_phase(phases["ack_egress"]),
        calibration_source=raw["calibration_source"],
        bounds_min_us=raw.get("bounds", {}).get("min_us", 1.0),
        bounds_max_us=raw.get("bounds", {}).get("max_us", 1_000_000.0),
    )

    _warn_if_placeholder("calibration_source", config.calibration_source)

    # Sanity checks
    if config.bounds_min_us < 0:
        raise ConfigurationError("latency.bounds.min_us cannot be negative")
    if config.bounds_max_us <= config.bounds_min_us:
        raise ConfigurationError("latency.bounds.max_us must be > min_us")

    return config


def _validate_fill_model(raw: dict) -> FillModelConfig:
    """Parse and validate fill model configuration."""
    if "fill_probability_discount" not in raw:
        raise ConfigurationError(
            "fill_model.fill_probability_discount is required (no default). "
            "Calibrate against live fill rates if available."
        )
    if "fill_discount_source" not in raw:
        raise ConfigurationError(
            "fill_model.fill_discount_source is required. "
            "Specify the source of your fill discount calibration."
        )

    discount = raw["fill_probability_discount"]
    if not (0.0 < discount <= 1.0):
        raise ConfigurationError(
            f"fill_probability_discount must be in (0, 1], got {discount}"
        )

    model_str = raw.get("queue_cancellation_model", "pessimistic")
    try:
        q_model = QueueCancellationModel(model_str)
    except ValueError:
        raise ConfigurationError(
            f"Invalid queue_cancellation_model: '{model_str}'. "
            f"Must be one of: {[m.value for m in QueueCancellationModel]}"
        )

    config = FillModelConfig(
        fill_probability_discount=discount,
        fill_discount_source=raw["fill_discount_source"],
        queue_cancellation_model=q_model,
    )

    _warn_if_placeholder("fill_discount_source", config.fill_discount_source)
    return config


def _validate_fees(raw: dict) -> FeeConfig:
    """Parse and validate fee configuration."""
    return FeeConfig(
        stamp_duty_rate=raw.get("stamp_duty_rate", 0.00003),
        stamp_duty_state=raw.get("stamp_duty_state", "unspecified"),
        broker_commission_per_order=raw.get("broker_commission_per_order", 0.0),
    )


def _validate_greeks(raw: dict | None) -> GreeksConfig | None:
    """Parse and validate Greeks configuration."""
    if raw is None:
        return None

    rfr_raw = raw.get("risk_free_rate")
    if rfr_raw is None:
        raise ConfigurationError(
            "greeks.risk_free_rate is required when trading options."
        )
    if "rate_source" not in rfr_raw:
        raise ConfigurationError(
            "greeks.risk_free_rate.rate_source is required. "
            "Specify the source of your risk-free rate data "
            "(e.g., 'RBI repo rate as of July 2026')."
        )

    rfr_type = rfr_raw.get("type", "constant")
    if rfr_type == "constant" and rfr_raw.get("value") is None:
        raise ConfigurationError(
            "greeks.risk_free_rate.value is required when type='constant'."
        )
    if rfr_type == "time_series" and rfr_raw.get("time_series_path") is None:
        raise ConfigurationError(
            "greeks.risk_free_rate.time_series_path is required when type='time_series'."
        )

    rfr = RiskFreeRateConfig(
        type=rfr_type,
        rate_source=rfr_raw["rate_source"],
        value=rfr_raw.get("value"),
        time_series_path=rfr_raw.get("time_series_path"),
    )

    _warn_if_placeholder("rate_source", rfr.rate_source)

    div_raw = raw.get("dividend_yield", {"type": "constant", "constant_yield": 0.0})
    div = DividendYieldConfig(
        type=div_raw.get("type", "constant"),
        schedule_path=div_raw.get("schedule_path"),
        constant_yield=div_raw.get("constant_yield"),
    )

    return GreeksConfig(risk_free_rate=rfr, dividend_yield=div)


def load_config(config_path: str | Path) -> BacktestConfig:
    """
    Load and validate a complete backtest configuration from YAML.

    Fails fast with ConfigurationError if any required field is missing.
    Logs warnings for placeholder traceability values.
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigurationError(f"Config file is empty: {path}")

    # --- Required sections ---
    if "latency" not in raw and "calibration_source" not in raw:
        raise ConfigurationError(
            "Latency configuration is required. "
            "No default latency values are provided — you must supply your own. "
            "See docs/latency_calibration.md for guidance."
        )

    if "fill_model" not in raw:
        raise ConfigurationError(
            "fill_model configuration is required (no defaults). "
            "Specify fill_probability_discount and fill_discount_source."
        )

    latency_raw = raw.copy()
    if "latency" in raw and isinstance(raw["latency"], dict):
        latency_raw = {**raw, "latency": raw["latency"]}
        if "calibration_source" not in latency_raw and "calibration_source" in raw:
            latency_raw["calibration_source"] = raw["calibration_source"]
        elif "calibration_source" not in latency_raw:
            # Try inside latency block
            latency_raw["calibration_source"] = raw["latency"].get("calibration_source")

    latency = _validate_latency(latency_raw)
    fill_model = _validate_fill_model(raw["fill_model"])
    fees = _validate_fees(raw.get("fees", {}))
    greeks = _validate_greeks(raw.get("greeks"))

    return BacktestConfig(
        latency=latency,
        fill_model=fill_model,
        fees=fees,
        greeks=greeks,
        data_path=raw.get("data_path", ""),
        symbols=raw.get("symbols", []),
        start_date=raw.get("start_date", ""),
        end_date=raw.get("end_date", ""),
        initial_capital=raw.get("initial_capital", 10_000_000.0),
        corporate_actions_path=raw.get("corporate_actions_path"),
        max_position_limit=raw.get("max_position_limit", 10_000),
        max_drawdown_pct=raw.get("max_drawdown_pct", 0.05),
        max_order_rate_per_sec=raw.get("max_order_rate_per_sec", 100),
    )
