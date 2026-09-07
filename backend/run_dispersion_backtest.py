"""
run_dispersion_backtest.py

End-to-end runner for the Volatility Dispersion Arbitrage strategy.

Generates synthetic IV time series for NIFTY + 6 constituents, runs the
dispersion engine with GEX regime filtering, and produces a full report
with correlation spread P&L, basket sizing, and implied correlation history.

This is a standalone simulation that demonstrates the full pipeline:
  1. Synthetic IV generation (with mean-reversion + jumps to mimic real vol surfaces)
  2. GEX regime detection from synthetic options chains
  3. Dispersion P&L decomposition: correlation spread vs vol-level noise
  4. Report output to results/dispersion_report.json
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.dispersion_engine import (
    implied_correlation, renormalize_weights, size_vega_matched_basket,
    dispersion_pnl_decomposition, OptionLeg,
)
from strategies.gex_regime import (
    GEXDetector, GEXRegime, generate_synthetic_chain,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Synthetic IV time series generator
# ---------------------------------------------------------------------------

def generate_iv_time_series(
    n_periods: int = 60,
    base_ivs: dict[str, float] | None = None,
    index_base_iv: float = 0.16,
    mean_reversion_speed: float = 0.15,
    vol_of_vol: float = 0.08,
    jump_prob: float = 0.05,
    jump_size: float = 0.04,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic daily IV time series for index + constituents.

    Uses an Ornstein-Uhlenbeck process for mean-reverting IV dynamics
    with occasional jumps (VIX spikes).

    Returns:
        (constituent_iv_df, index_iv_series) where:
        - constituent_iv_df has columns = ticker names, index = date
        - index_iv_series has column 'index_iv', index = date
    """
    rng = np.random.default_rng(seed)

    if base_ivs is None:
        base_ivs = {
            "RELIANCE": 0.24, "HDFCBANK": 0.21, "ICICIBANK": 0.26,
            "SBIN": 0.30, "TCS": 0.22, "INFY": 0.27,
        }

    tickers = list(base_ivs.keys())
    n_stocks = len(tickers)

    # Generate correlated IV innovations
    # Stocks share a common factor (market vol) + idiosyncratic component
    common_factor_loading = 0.6

    dates = pd.bdate_range(start="2026-07-01", periods=n_periods)

    # Constituent IVs
    iv_matrix = np.zeros((n_periods, n_stocks))
    iv_matrix[0] = [base_ivs[t] for t in tickers]

    # Index IV
    index_ivs = np.zeros(n_periods)
    index_ivs[0] = index_base_iv

    for t in range(1, n_periods):
        # Common market vol shock
        common_shock = rng.normal(0, vol_of_vol)

        # Jump component (affects index more than single names)
        is_jump = rng.random() < jump_prob
        jump = jump_size * rng.choice([-1, 1]) if is_jump else 0.0

        for i, ticker in enumerate(tickers):
            base = base_ivs[ticker]
            prev = iv_matrix[t - 1, i]
            idio_shock = rng.normal(0, vol_of_vol * 0.8)

            # OU: dIV = kappa * (theta - IV) * dt + sigma * dW
            drift = mean_reversion_speed * (base - prev)
            diffusion = common_factor_loading * common_shock + (1 - common_factor_loading) * idio_shock

            new_iv = prev + drift + diffusion + jump * 0.5  # Index jumps transmit partially
            iv_matrix[t, i] = max(0.05, min(0.80, new_iv))

        # Index IV: tracks weighted average but with a "correlation premium"
        # from hedging demand (this is the structural feature we're trading)
        prev_idx = index_ivs[t - 1]
        idx_drift = mean_reversion_speed * (index_base_iv - prev_idx)
        idx_diffusion = common_shock * 1.2  # Index vol is more sensitive to common shocks
        idx_jump = jump * 1.5  # And more sensitive to jumps (hedging demand spike)

        index_ivs[t] = max(0.05, min(0.60, prev_idx + idx_drift + idx_diffusion + idx_jump))

    constituent_df = pd.DataFrame(iv_matrix, columns=tickers, index=dates)
    index_df = pd.DataFrame({"index_iv": index_ivs}, index=dates)

    return constituent_df, index_df


# ---------------------------------------------------------------------------
# 2. Realized correlation estimator
# ---------------------------------------------------------------------------

def estimate_realized_correlation(
    returns_df: pd.DataFrame,
    window: int = 10,
) -> pd.Series:
    """
    Estimate realized average pairwise correlation from a rolling window
    of returns.

    Uses the Pearson correlation matrix averaged across all unique pairs.
    """
    n_stocks = returns_df.shape[1]
    if n_stocks < 2:
        return pd.Series(0.0, index=returns_df.index)

    realized_corrs = []
    for end_idx in range(len(returns_df)):
        start_idx = max(0, end_idx - window + 1)
        window_data = returns_df.iloc[start_idx:end_idx + 1]

        if len(window_data) < 3:
            realized_corrs.append(0.5)  # Default before enough data
            continue

        corr_matrix = window_data.corr()
        # Average of off-diagonal elements
        mask = ~np.eye(n_stocks, dtype=bool)
        avg_corr = corr_matrix.values[mask].mean()
        realized_corrs.append(avg_corr)

    return pd.Series(realized_corrs, index=returns_df.index)


# ---------------------------------------------------------------------------
# 3. Main simulation
# ---------------------------------------------------------------------------

def run_dispersion_simulation():
    """Run the full dispersion arbitrage simulation."""

    logger.info("=" * 70)
    logger.info("VOLATILITY DISPERSION ARBITRAGE SIMULATION")
    logger.info("=" * 70)

    # --- Configuration ---
    raw_weights = {
        "RELIANCE": 0.091, "HDFCBANK": 0.058, "ICICIBANK": 0.052,
        "SBIN": 0.049, "TCS": 0.043, "INFY": 0.024,
    }
    weights = renormalize_weights(raw_weights)
    tickers = list(raw_weights.keys())

    lot_sizes = {
        "NIFTY": 25, "RELIANCE": 500, "HDFCBANK": 550,
        "ICICIBANK": 700, "SBIN": 1500, "TCS": 175, "INFY": 400,
    }

    # --- Step 1: Fetch Real Market Data (Groww / Yahoo) ---
    logger.info("Step 1: Fetching LIVE market data...")
    from data.groww_client import GrowwAPIClient
    
    # Authenticate via TOTP
    client = GrowwAPIClient()
    client.authenticate()
    
    # Fetch 90 days of real market data to compute 30 days of rolling realized vol
    returns_df = client.fetch_real_market_data(tickers, days=90)
    
    if returns_df is None or returns_df.empty:
        logger.error("Failed to fetch real market data. Aborting.")
        return
        
    dates = returns_df.index
    logger.info(f"Loaded {len(dates)} days of real returns.")
    
    # Calculate rolling 20-day realized volatility (annualized) as a proxy for IV
    rolling_vol = returns_df.rolling(20).std() * np.sqrt(252)
    rolling_vol.dropna(inplace=True)
    dates = rolling_vol.index
    
    constituent_iv_df = rolling_vol[tickers]
    index_iv_df = rolling_vol[["NIFTY"]].rename(columns={"NIFTY": "index_iv"})
    
    daily_returns = returns_df.loc[dates][tickers]

    logger.info(f"  Generated {len(dates)} days of IV data for {len(tickers)} constituents + index")

    # --- Step 2: Compute implied correlation time series ---
    logger.info("Step 2: Computing implied correlation time series...")
    implied_corrs = []
    for i, date in enumerate(dates):
        constituent_ivs = {t: constituent_iv_df.loc[date, t] for t in tickers}
        index_iv = index_iv_df.loc[date, "index_iv"]

        try:
            rho = implied_correlation(index_iv, weights, constituent_ivs)
            rho = max(-1.0, min(1.0, rho))  # Clamp to valid range
        except (ValueError, ZeroDivisionError):
            rho = 0.5  # Fallback

        implied_corrs.append(rho)

    implied_corr_series = pd.Series(implied_corrs, index=dates)
    logger.info(
        f"  Implied corr: mean={implied_corr_series.mean():.3f}, "
        f"std={implied_corr_series.std():.3f}, "
        f"range=[{implied_corr_series.min():.3f}, {implied_corr_series.max():.3f}]"
    )

    # --- Step 3: Compute realized correlation ---
    logger.info("Step 3: Estimating realized correlation (10-day rolling window)...")
    realized_corr_series = estimate_realized_correlation(daily_returns, window=10)

    # --- Step 4: GEX regime detection ---
    logger.info("Step 4: Running GEX regime detection...")
    gex_detector = GEXDetector()
    gex_regimes = []
    gex_values = []
    flip_levels = []

    for i, date in enumerate(dates):
        # Synthetic spot price (drifting around 24800)
        spot = 24800.0 * (1 + daily_returns.iloc[:i + 1].mean(axis=1).sum() * 0.5)

        # Generate synthetic chain with varying put skew
        # Higher implied corr → more hedging demand → higher put skew
        put_skew = 1.0 + implied_corrs[i] * 0.8
        chain = generate_synthetic_chain(
            spot=spot, num_strikes=21, strike_step=100.0,
            put_oi_skew=put_skew, seed=42 + i,
        )

        result = gex_detector.compute_gex(
            spot=spot, strikes=chain,
            iv_surface=float(index_iv_df.iloc[i]["index_iv"]),
            time_to_expiry=max(0.01, 0.07 - (i % 30) * 0.07 / 30),  # Decaying to expiry
            lot_size=lot_sizes["NIFTY"],
        )

        gex_regimes.append(result.regime.value)
        gex_values.append(result.total_gex)
        flip_levels.append(result.gamma_flip_level)

    regime_counts = pd.Series(gex_regimes).value_counts()
    logger.info(f"  GEX regime distribution: {regime_counts.to_dict()}")

    # --- Step 5: Dispersion P&L decomposition ---
    logger.info("Step 5: Computing dispersion P&L decomposition...")

    # Weighted constituent realized vol
    constituent_realized_vols = daily_returns.rolling(10).std() * math.sqrt(252)
    weighted_realized_vol = sum(
        weights[t] * constituent_realized_vols[t] for t in tickers
    )

    pnl_df = pd.DataFrame({
        "date": dates,
        "implied_corr": implied_corrs,
        "realized_corr": realized_corr_series.values,
        "weighted_constituent_realized_vol": weighted_realized_vol.fillna(0.15).values,
    })

    # Apply GEX filter: only count P&L on days where we'd actually be positioned
    gex_mask = pd.Series(gex_regimes).isin(["SHORT_GAMMA", "NEUTRAL"])
    pnl_df["gex_active"] = gex_mask.values

    pnl_result = dispersion_pnl_decomposition(pnl_df)

    # Filtered P&L (only when GEX allows entry)
    pnl_result["filtered_period_pnl"] = pnl_result["approx_period_pnl"] * pnl_result["gex_active"].astype(float)
    pnl_result["filtered_cum_pnl"] = pnl_result["filtered_period_pnl"].cumsum()

    total_pnl_unfiltered = pnl_result["approx_period_pnl"].sum()
    total_pnl_filtered = pnl_result["filtered_period_pnl"].sum()

    logger.info(f"  Unfiltered cumulative P&L (proxy): {total_pnl_unfiltered:.4f}")
    logger.info(f"  GEX-filtered cumulative P&L (proxy): {total_pnl_filtered:.4f}")

    # --- Step 6: Vega-matched basket sizing (snapshot) ---
    logger.info("Step 6: Computing vega-matched basket sizing (final day snapshot)...")
    final_constituent_ivs = {t: float(constituent_iv_df.iloc[-1][t]) for t in tickers}
    final_index_iv = float(index_iv_df.iloc[-1]["index_iv"])

    # Extract real spot prices from the client
    index_spot = float(getattr(client, "last_prices", {}).get("^NSEI", 24800))
    spot_prices = {}
    for t in tickers:
        spot_prices[t] = float(getattr(client, "last_prices", {}).get(f"{t}.NS", 1000))

    index_leg = OptionLeg("NIFTY", spot=index_spot, strike=index_spot, iv=final_index_iv,
                          vega_per_contract=12.0, lot_size=25)
    constituent_legs = {}
    vega_estimates = {
        "RELIANCE": 1.6, "HDFCBANK": 1.9, "ICICIBANK": 1.4,
        "SBIN": 1.0, "TCS": 3.8, "INFY": 1.7,
    }
    for t in tickers:
        constituent_legs[t] = OptionLeg(
            t, spot_prices[t], spot_prices[t], final_constituent_ivs[t],
            vega_per_contract=vega_estimates[t], lot_size=lot_sizes[t],
        )

    basket = size_vega_matched_basket(
        index_leg, index_target_vega_notional=50000,
        constituent_weights=raw_weights, constituent_legs=constituent_legs,
    )
    
    # Add spot prices to the basket DataFrame for UI display
    basket["spot"] = basket["ticker"].apply(lambda t: index_spot if t == "INDEX (SELL)" else spot_prices.get(t, 0.0))
    basket["spot"] = basket["spot"].round(2)
    
    logger.info("\n" + basket.to_string(index=False))

    # Verify vega neutrality
    long_vega = basket[basket["lots_to_buy"] > 0]["target_vega"].sum()
    short_vega = abs(basket[basket["lots_to_buy"] < 0]["target_vega"].sum())
    logger.info(f"\n  Long basket vega: {long_vega:.0f}")
    logger.info(f"  Short index vega: {short_vega:.0f}")
    logger.info(f"  Net vega: {long_vega - short_vega:.0f}")

    # --- Step 7: Build report ---
    logger.info("Step 7: Building report...")

    # Compute summary statistics
    corr_spread = pnl_result["correlation_spread"]
    winning_days = (pnl_result["filtered_period_pnl"] > 0).sum()
    total_active_days = pnl_result["gex_active"].sum()

    report = {
        "metadata": {
            "strategy": "Volatility Dispersion Arbitrage (NIFTY vs 6-name subset)",
            "framework": "HFT Backtester v0.1.0 — Dispersion Module",
            "simulation_days": int(len(dates)),
            "basket_constituents": tickers,
            "index": "NIFTY",
            "gex_entry_filter": True,
            "vega_matched": True,
            "pnl_units": "Approximate (correlation-spread × weighted-realized-vol proxy)",
            "warnings": [
                "P&L is a toy approximation — does NOT include transaction costs, bid-ask, or margin.",
                "IVs are synthetic (OU process + jumps), not from live NSE options chains.",
                "6-name subset proxy — NOT the true 50-name NIFTY variance decomposition.",
                "Realized correlation from 10-day rolling window of synthetic returns.",
            ],
        },
        "summary": {
            "total_pnl_unfiltered": round(float(total_pnl_unfiltered), 6),
            "total_pnl_gex_filtered": round(float(total_pnl_filtered), 6),
            "gex_filter_improvement_pct": round(
                ((total_pnl_filtered - total_pnl_unfiltered) / abs(total_pnl_unfiltered) * 100)
                if abs(total_pnl_unfiltered) > 1e-10 else 0.0, 2
            ),
            "avg_implied_correlation": round(float(implied_corr_series.mean()), 4),
            "avg_realized_correlation": round(float(realized_corr_series.mean()), 4),
            "avg_correlation_spread": round(float(corr_spread.mean()), 4),
            "correlation_spread_std": round(float(corr_spread.std()), 4),
            "winning_days_of_active": f"{int(winning_days)}/{int(total_active_days)}",
            "win_rate_pct": round(float(winning_days / max(total_active_days, 1) * 100), 1),
        },
        "gex_analysis": {
            "regime_distribution": {str(k): int(v) for k, v in regime_counts.items()},
            "active_days": int(total_active_days),
            "inactive_days": int(len(dates) - total_active_days),
            "avg_gex_when_active": round(float(
                np.mean([gex_values[i] for i in range(len(gex_values)) if gex_mask.iloc[i]])
            ), 2) if gex_mask.any() else 0.0,
        },
        "basket_sizing_snapshot": {
            "index_iv": round(final_index_iv, 4),
            "constituent_ivs": {k: round(v, 4) for k, v in final_constituent_ivs.items()},
            "implied_correlation": round(float(implied_corrs[-1]), 4),
            "target_vega_notional": 50000,
            "basket": basket.to_dict(orient="records"),
            "net_vega": round(float(long_vega - short_vega), 2),
        },
        "time_series": {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "implied_correlation": [round(float(x), 4) for x in implied_corrs],
            "realized_correlation": [round(float(x), 4) for x in realized_corr_series.values],
            "correlation_spread": [round(float(x), 4) for x in corr_spread.values],
            "cumulative_pnl_unfiltered": [round(float(x), 6) for x in pnl_result["cum_pnl"].values],
            "cumulative_pnl_filtered": [round(float(x), 6) for x in pnl_result["filtered_cum_pnl"].values],
            "gex_regime": gex_regimes,
            "gex_total": [round(float(x), 2) for x in gex_values],
            "index_iv": [round(float(x), 4) for x in index_iv_df["index_iv"].values],
        },
    }

    output_path = Path("results/dispersion_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"\nReport saved to {output_path}")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"  Avg implied correlation:  {implied_corr_series.mean():.3f}")
    logger.info(f"  Avg realized correlation: {realized_corr_series.mean():.3f}")
    logger.info(f"  Avg correlation spread:   {corr_spread.mean():.4f}")
    logger.info(f"  Unfiltered P&L (proxy):   {total_pnl_unfiltered:.6f}")
    logger.info(f"  GEX-filtered P&L (proxy): {total_pnl_filtered:.6f}")
    logger.info(f"  GEX active days:          {int(total_active_days)}/{len(dates)}")
    logger.info(f"  Win rate (active days):   {winning_days / max(total_active_days, 1) * 100:.1f}%")
    logger.info(f"  Net vega (basket):        {long_vega - short_vega:.0f} (target: 0)")
    logger.info("=" * 70)

    return report


if __name__ == "__main__":
    run_dispersion_simulation()
