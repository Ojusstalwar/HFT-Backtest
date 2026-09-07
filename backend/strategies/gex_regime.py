"""
gex_regime.py

Dealer Gamma Exposure (GEX) regime detector.

Computes aggregate dealer gamma across an options chain, identifies the
"gamma flip level" (price where dealers shift from long to short gamma),
and classifies the current regime.

The key insight for the dispersion trade: when dealers are SHORT gamma on
the index (heavy put buying by funds for portfolio insurance), they are
forced to sell futures as the index drops and buy as it rises -- amplifying
moves and inflating index realized vol. This mechanically widens the
spread between index IV and constituent IVs (the correlation premium),
which is exactly the edge the dispersion trade captures.

So GEX regime == SHORT_GAMMA is the entry condition for dispersion.

Implementation notes:
 - We assume dealers are net short options at each strike (the standard
   assumption: retail/funds buy, dealers sell). This is approximately
   correct for index options and large-cap names on NSE, but breaks down
   for strikes where institutional flow is selling premium.
 - "Dealer gamma" at strike K = OI(K) * BSM_gamma(K) * spot * 0.01
   (the 0.01 is the 1% move convention for dollar gamma).
 - Calls contribute positive dealer gamma (dealer is short calls -> when
   spot rises, delta rises, dealer must sell to stay hedged -> mean-reverting).
 - Puts contribute negative dealer gamma (dealer is short puts -> when
   spot falls, delta becomes more negative, dealer must sell more ->
   momentum-amplifying).
"""

from __future__ import annotations

import math
import enum
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


class GEXRegime(enum.Enum):
    """Dealer gamma exposure regime classification."""
    LONG_GAMMA = "LONG_GAMMA"     # Dealers long gamma → vol suppression / pinning
    SHORT_GAMMA = "SHORT_GAMMA"   # Dealers short gamma → vol amplification
    NEUTRAL = "NEUTRAL"           # Near the flip level, ambiguous


@dataclass
class StrikeData:
    """Options data at a single strike."""
    strike: float
    call_oi: int             # Open interest for calls at this strike
    put_oi: int              # Open interest for puts at this strike
    call_volume: int = 0     # Today's volume (used for flow direction inference)
    put_volume: int = 0


@dataclass
class GEXResult:
    """Result of a GEX computation."""
    regime: GEXRegime
    total_gex: float                        # Net dealer gamma in ₹ terms (per 1% move)
    gamma_flip_level: Optional[float]       # Price where dealer gamma changes sign
    per_strike_gex: dict[float, float]      # Strike → dealer gamma contribution
    call_gex: float                         # Total call-side dealer gamma
    put_gex: float                          # Total put-side dealer gamma
    spot_price: float
    confidence: float                       # 0-1, based on OI concentration


def _bsm_gamma(spot: float, strike: float, T: float, sigma: float,
               r: float = 0.065) -> float:
    """
    Black-Scholes gamma (same for calls and puts).

    Returns gamma per share. T in years, sigma annualized.
    """
    if T <= 0 or sigma <= 0 or spot <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    # N'(d1) = standard normal PDF
    nprime_d1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)
    gamma = nprime_d1 / (spot * sigma * math.sqrt(T))
    return gamma


class GEXDetector:
    """
    Computes Dealer Gamma Exposure from an options chain.

    Usage:
        detector = GEXDetector(risk_free_rate=0.065)
        result = detector.compute_gex(
            spot=24800.0,
            strikes=[...StrikeData...],
            iv_surface={strike: iv, ...},  # or flat IV
            time_to_expiry=0.05,           # in years (~18 calendar days)
            lot_size=25,                    # NIFTY lot size
        )
        if result.regime == GEXRegime.SHORT_GAMMA:
            # Dispersion entry condition met
    """

    def __init__(self, risk_free_rate: float = 0.065,
                 neutral_band_pct: float = 0.10):
        """
        Args:
            risk_free_rate: Annualized risk-free rate (RBI repo rate).
            neutral_band_pct: If |total_gex| < neutral_band_pct * max(|call_gex|, |put_gex|),
                              classify as NEUTRAL rather than picking a side.
        """
        self.r = risk_free_rate
        self.neutral_band_pct = neutral_band_pct

    def compute_gex(self, spot: float, strikes: list[StrikeData],
                    iv_surface: dict[float, float] | float,
                    time_to_expiry: float,
                    lot_size: int = 25,
                    contract_multiplier: float = 1.0) -> GEXResult:
        """
        Compute aggregate dealer GEX across all strikes.

        Args:
            spot: Current underlying price.
            strikes: List of StrikeData with OI at each strike.
            iv_surface: Either a dict {strike: IV} for a full surface, or a
                        single float for flat vol assumption.
            time_to_expiry: Time to nearest expiry in years.
            lot_size: Contract lot size (25 for NIFTY, varies for stocks).
            contract_multiplier: Notional multiplier per contract.

        Returns:
            GEXResult with regime classification and breakdown.
        """
        per_strike_gex: dict[float, float] = {}
        total_call_gex = 0.0
        total_put_gex = 0.0

        for sd in strikes:
            # Get IV for this strike
            if isinstance(iv_surface, (int, float)):
                iv = float(iv_surface)
            else:
                iv = iv_surface.get(sd.strike, 0.16)  # fallback

            gamma = _bsm_gamma(spot, sd.strike, time_to_expiry, iv, self.r)

            # Dollar gamma per contract = gamma * spot * 0.01 * lot_size * multiplier
            # This is the $ P&L change in dealer's delta hedge for a 1% spot move
            dollar_gamma = gamma * spot * 0.01 * lot_size * contract_multiplier

            # Dealer is assumed NET SHORT options at each strike.
            # Short call gamma: positive (stabilizing — dealer sells on up, buys on down)
            # Short put gamma: negative (destabilizing — dealer sells on down, buys on up)
            #
            # Wait — this is counterintuitive. Let's be precise:
            # Gamma is always positive for both calls and puts.
            # If dealer is SHORT a call: their position gamma is -gamma.
            #   When spot goes up, their delta becomes more negative → they must BUY underlying → stabilizing.
            # If dealer is SHORT a put: their position gamma is -gamma.
            #   When spot goes down, their delta becomes more positive → they must SELL underlying → destabilizing.
            #
            # Convention: we report "dealer GEX" = -1 * (call_oi * gamma) + (-1) * (put_oi * (-gamma))
            # Simplified: GEX_call = -call_oi * dollar_gamma (dealer short calls)
            #             GEX_put  = +put_oi * dollar_gamma  (dealer short puts, but put delta
            #                         is negative, so the net effect flips)
            #
            # Standard GEX convention used by SpotGamma / SqueezeMetrics:
            #   GEX = call_oi * gamma * spot * 100 - put_oi * gamma * spot * 100
            # Positive total GEX = long gamma environment (stabilizing)
            # Negative total GEX = short gamma environment (destabilizing)

            call_contribution = sd.call_oi * dollar_gamma
            put_contribution = -sd.put_oi * dollar_gamma

            strike_gex = call_contribution + put_contribution
            per_strike_gex[sd.strike] = strike_gex

            total_call_gex += call_contribution
            total_put_gex += put_contribution

        total_gex = total_call_gex + total_put_gex

        # --- Find gamma flip level ---
        gamma_flip = self._find_gamma_flip(per_strike_gex, spot)

        # --- Regime classification ---
        max_component = max(abs(total_call_gex), abs(total_put_gex), 1e-10)
        if abs(total_gex) < self.neutral_band_pct * max_component:
            regime = GEXRegime.NEUTRAL
        elif total_gex > 0:
            regime = GEXRegime.LONG_GAMMA
        else:
            regime = GEXRegime.SHORT_GAMMA

        # Confidence: higher when OI is concentrated (clear positioning)
        oi_values = [sd.call_oi + sd.put_oi for sd in strikes]
        total_oi = sum(oi_values)
        if total_oi > 0 and len(oi_values) > 1:
            oi_fracs = np.array(oi_values) / total_oi
            # Herfindahl-Hirschman Index normalized to [0, 1]
            hhi = float(np.sum(oi_fracs ** 2))
            # HHI of 1/N (uniform) → 0 confidence, HHI of 1 (single strike) → 1
            n = len(oi_values)
            confidence = (hhi - 1.0 / n) / (1.0 - 1.0 / n) if n > 1 else 1.0
            confidence = max(0.0, min(1.0, confidence))
        else:
            confidence = 0.0

        return GEXResult(
            regime=regime,
            total_gex=total_gex,
            gamma_flip_level=gamma_flip,
            per_strike_gex=per_strike_gex,
            call_gex=total_call_gex,
            put_gex=total_put_gex,
            spot_price=spot,
            confidence=confidence,
        )

    def _find_gamma_flip(self, per_strike_gex: dict[float, float],
                         spot: float) -> Optional[float]:
        """
        Find the strike price where cumulative GEX changes sign
        (scanning from low strikes upward). This is the "gamma flip level" —
        below it, dealers are short gamma (destabilizing); above it,
        long gamma (stabilizing).

        Returns None if GEX doesn't change sign across the chain.
        """
        if len(per_strike_gex) < 2:
            return None

        sorted_strikes = sorted(per_strike_gex.keys())
        # Compute cumulative GEX from the bottom
        cum_gex = 0.0
        prev_cum = 0.0
        flip_level = None

        for k in sorted_strikes:
            prev_cum = cum_gex
            cum_gex += per_strike_gex[k]

            # Check for sign change
            if prev_cum != 0 and cum_gex != 0:
                if (prev_cum > 0 and cum_gex < 0) or (prev_cum < 0 and cum_gex > 0):
                    # Linear interpolation for the flip point
                    prev_strike = sorted_strikes[sorted_strikes.index(k) - 1]
                    # Weight by magnitude of each side
                    w = abs(prev_cum) / (abs(prev_cum) + abs(cum_gex))
                    flip_level = prev_strike + w * (k - prev_strike)

        # If no sign change found, check if total is dominated by one side
        # relative to spot
        if flip_level is None:
            # Use the strike nearest spot as a proxy
            nearest = min(sorted_strikes, key=lambda k: abs(k - spot))
            total = sum(per_strike_gex.values())
            # If total is negative, flip is above spot; if positive, below
            if total < 0:
                flip_level = spot * 1.01  # Approx: flip is slightly above
            elif total > 0:
                flip_level = spot * 0.99  # Approx: flip is slightly below

        return flip_level

    def should_enter_dispersion(self, result: GEXResult,
                                 min_confidence: float = 0.05) -> bool:
        """
        Entry gate for the dispersion trade.

        Returns True when dealers are SHORT GAMMA on the index, which is the
        condition that structurally inflates index IV via forced hedging flows
        and widens the correlation premium.

        Args:
            result: Output from compute_gex().
            min_confidence: Minimum OI concentration confidence to act.
        """
        return (result.regime == GEXRegime.SHORT_GAMMA and
                result.confidence >= min_confidence)


def generate_synthetic_chain(spot: float, num_strikes: int = 21,
                              strike_step: float = 100.0,
                              base_oi: int = 50000,
                              put_oi_skew: float = 1.3,
                              seed: int = 42) -> list[StrikeData]:
    """
    Generate a realistic-looking synthetic options chain for testing.

    The put_oi_skew parameter controls how much more put OI there is
    relative to call OI (> 1.0 = more puts = typical for index options
    where funds buy portfolio insurance).
    """
    rng = np.random.default_rng(seed)

    atm_strike = round(spot / strike_step) * strike_step
    half = num_strikes // 2
    chain = []

    for i in range(-half, half + 1):
        strike = atm_strike + i * strike_step
        # OI peaks near ATM and falls off at the wings
        distance = abs(i)
        oi_decay = math.exp(-0.15 * distance ** 1.5)

        call_oi = int(base_oi * oi_decay * rng.uniform(0.7, 1.3))
        put_oi = int(base_oi * oi_decay * put_oi_skew * rng.uniform(0.7, 1.3))

        # More put OI below ATM (hedging demand)
        if strike < atm_strike:
            put_oi = int(put_oi * 1.4)
        # More call OI above ATM (covered call writing)
        if strike > atm_strike:
            call_oi = int(call_oi * 1.2)

        chain.append(StrikeData(
            strike=strike,
            call_oi=call_oi,
            put_oi=put_oi,
            call_volume=int(call_oi * rng.uniform(0.02, 0.10)),
            put_volume=int(put_oi * rng.uniform(0.02, 0.10)),
        ))

    return chain
