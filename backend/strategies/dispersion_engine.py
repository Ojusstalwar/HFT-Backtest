"""
dispersion_engine.py

Core quantitative engine for a Nifty (index) vs. constituent single-stock
dispersion / correlation arbitrage strategy.

This module intentionally separates three concerns that get conflated in
most "dispersion arb" writeups:

 1. Implied correlation extraction -- given the index's implied vol and each
    constituent's implied vol (+ weights), back out the average pairwise
    implied correlation the market is pricing.
 2. Vega-neutral basket construction -- a real dispersion trade is vega-
    matched (short index vega == long basket vega), NOT notional-matched.
    Sizing on notional instead of vega is the single most common mistake
    in retail attempts at this trade.
 3. A toy backtest harness that consumes a time series of index/constituent
    IV and realized vol, and produces the classic dispersion P&L
    decomposition: correlation P&L vs. vol-level P&L.

None of this assumes access to correlation swaps or variance swaps --
those don't trade in listed form on NSE. Everything here is built from
vanilla option IVs (straddles), which is what you can actually execute.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# 1. Implied correlation
# ---------------------------------------------------------------------------

def implied_correlation(index_iv: float, weights: Dict[str, float],
                         constituent_ivs: Dict[str, float]) -> float:
    """
    Solve for the single 'average pairwise implied correlation' rho that
    reconciles the index IV with the constituent IVs, using the standard
    variance decomposition:

        sigma_index^2 = sum(w_i^2 * sigma_i^2) + rho * sum_{i != j} w_i w_j sigma_i sigma_j

    This is the same construction CBOE uses for its implied correlation
    indices, simplified to a single average rho rather than a full
    correlation matrix -- which is the right simplification here, since
    you cannot independently observe every pairwise correlation from
    listed single-name IVs alone.

    Important: if you're trading a 5-6 stock subset of Nifty rather than
    the full 50, renormalize their weights to sum to 1 (see
    `renormalize_weights`). That subset captures a large fraction of
    Nifty's free-float weight but is NOT the true index variance
    decomposition -- treat the resulting rho as a proxy, not the "real"
    implied correlation. This basis gap is a genuine, unhedgeable risk
    of the trade at retail/small-fund scale -- see module docstring notes
    in the accompanying writeup.
    """
    tickers = list(weights.keys())
    w = np.array([weights[t] for t in tickers])
    sig = np.array([constituent_ivs[t] for t in tickers])

    weighted_var_sum = np.sum((w * sig) ** 2)

    n = len(tickers)
    cross_term = 0.0
    for i in range(n):
        for j in range(n):
            if i != j:
                cross_term += w[i] * w[j] * sig[i] * sig[j]

    if cross_term == 0:
        raise ValueError("Degenerate basket: cross term is zero (need >= 2 names).")

    rho = (index_iv ** 2 - weighted_var_sum) / cross_term
    return rho


def renormalize_weights(subset_weights: Dict[str, float]) -> Dict[str, float]:
    """Renormalize a subset of index weights so they sum to 1."""
    total = sum(subset_weights.values())
    return {k: v / total for k, v in subset_weights.items()}


# ---------------------------------------------------------------------------
# 2. Vega-neutral basket construction
# ---------------------------------------------------------------------------

@dataclass
class OptionLeg:
    ticker: str
    spot: float
    strike: float
    iv: float
    vega_per_contract: float   # vega for ONE unit (per share), from your pricer
    lot_size: int


def size_vega_matched_basket(index_leg: OptionLeg,
                              index_target_vega_notional: float,
                              constituent_weights: Dict[str, float],
                              constituent_legs: Dict[str, OptionLeg]) -> pd.DataFrame:
    """
    Given a short-index-straddle position sized to `index_target_vega_notional`
    total vega, compute how many lots of each constituent straddle to BUY so
    the basket's vega is split across names in proportion to their
    (renormalized) index weight -- i.e. vega-weighted, not notional-weighted.

    This is the sizing step that makes the "auto-locking" delta-hedge claim
    in the original writeup actually true in practice: size by notional
    instead of vega, and a spike in one stock's IV blows out your net vega
    balance -- the position stops being a clean correlation bet and starts
    being an accidental single-name vol bet.
    """
    weights = renormalize_weights(constituent_weights)
    rows = []
    for ticker, w in weights.items():
        leg = constituent_legs[ticker]
        target_vega = index_target_vega_notional * w
        vega_per_lot = leg.vega_per_contract * leg.lot_size
        lots_needed = target_vega / vega_per_lot
        rows.append({
            "ticker": ticker,
            "weight": round(w, 4),
            "target_vega": round(target_vega, 2),
            "vega_per_lot": round(vega_per_lot, 2),
            "lots_to_buy": round(lots_needed),
        })
    index_vega_per_lot = index_leg.vega_per_contract * index_leg.lot_size
    index_lots = index_target_vega_notional / index_vega_per_lot
    rows.append({
        "ticker": "INDEX (SELL)",
        "weight": 1.0,
        "target_vega": index_target_vega_notional,
        "vega_per_lot": round(index_vega_per_lot, 2),
        "lots_to_buy": -round(index_lots),
    })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Toy backtest: correlation P&L vs vol-level P&L decomposition
# ---------------------------------------------------------------------------

def dispersion_pnl_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    """
    df must have columns: date, weighted_constituent_realized_vol,
    implied_corr, realized_corr

    Returns a per-period P&L attribution: the trade makes money when
    realized_corr < implied_corr (dispersion), independent of whether vol
    as a whole rose or fell -- which is the point of vega-matching in
    step 2. This is a toy approximation only. It does NOT model
    transaction costs, bid-ask spread on single-stock options beyond the
    most liquid ~10-15 NSE names, margin (SPAN + exposure per underlying,
    no cross-margin benefit for a retail/small-fund account), or
    corporate-action-driven weight changes -- add all of these before
    trusting any Sharpe number it produces.
    """
    out = df.copy()
    out["correlation_spread"] = out["implied_corr"] - out["realized_corr"]
    out["approx_period_pnl"] = out["correlation_spread"] * out["weighted_constituent_realized_vol"]
    out["cum_pnl"] = out["approx_period_pnl"].cumsum()
    return out


if __name__ == "__main__":
    # --- Worked example using an approximate, illustrative Nifty subset ---
    raw_weights = {
        "RELIANCE": 0.091,
        "HDFCBANK": 0.058,
        "ICICIBANK": 0.052,
        "SBIN": 0.049,
        "TCS": 0.043,
        "INFY": 0.024,
    }
    weights = renormalize_weights(raw_weights)

    constituent_ivs = {
        "RELIANCE": 0.24, "HDFCBANK": 0.21, "ICICIBANK": 0.26,
        "SBIN": 0.30, "TCS": 0.22, "INFY": 0.27,
    }
    index_iv = 0.16

    rho = implied_correlation(index_iv, weights, constituent_ivs)
    print("Renormalized weights:")
    for k, v in weights.items():
        print(f"  {k}: {v:.4f}")
    print(f"\nImplied avg pairwise correlation (6-name subset proxy): {rho:.3f}")

    # --- Vega-matched basket sizing example ---
    index_leg = OptionLeg("NIFTY", spot=24800, strike=24800, iv=index_iv,
                          vega_per_contract=12.0, lot_size=25)
    constituent_legs = {
        "RELIANCE": OptionLeg("RELIANCE", 1380, 1380, 0.24, vega_per_contract=1.6, lot_size=500),
        "HDFCBANK": OptionLeg("HDFCBANK", 1650, 1650, 0.21, vega_per_contract=1.9, lot_size=550),
        "ICICIBANK": OptionLeg("ICICIBANK", 1200, 1200, 0.26, vega_per_contract=1.4, lot_size=700),
        "SBIN": OptionLeg("SBIN", 820, 820, 0.30, vega_per_contract=1.0, lot_size=1500),
        "TCS": OptionLeg("TCS", 3500, 3500, 0.22, vega_per_contract=3.8, lot_size=175),
        "INFY": OptionLeg("INFY", 1550, 1550, 0.27, vega_per_contract=1.7, lot_size=400),
    }
    basket = size_vega_matched_basket(index_leg, index_target_vega_notional=50000,
                                       constituent_weights=raw_weights,
                                       constituent_legs=constituent_legs)
    print("\nVega-matched basket sizing (illustrative lot sizes/vegas):")
    print(basket.to_string(index=False))
