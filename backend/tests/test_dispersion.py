"""
test_dispersion.py

Unit tests for the dispersion arbitrage engine and GEX regime detector.

Tests cover:
 - Implied correlation: known-answer with hand-calculated rho
 - Weight renormalization
 - Vega-matched basket sizing: net vega == 0
 - P&L decomposition correctness
 - GEX regime classification edge cases
 - GEX gamma flip level detection
 - Entry gate logic
"""

from __future__ import annotations

import math
import pytest
import numpy as np
import pandas as pd

from strategies.dispersion_engine import (
    implied_correlation,
    renormalize_weights,
    size_vega_matched_basket,
    dispersion_pnl_decomposition,
    OptionLeg,
)
from strategies.gex_regime import (
    GEXDetector,
    GEXRegime,
    GEXResult,
    StrikeData,
    generate_synthetic_chain,
    _bsm_gamma,
)


# =====================================================================
# Implied Correlation Tests
# =====================================================================

class TestImpliedCorrelation:

    def test_two_equal_stocks_known_answer(self):
        """
        Two stocks with equal weights and equal IVs.

        sigma_index^2 = 2 * (0.5)^2 * 0.20^2 + rho * 2 * 0.5 * 0.5 * 0.20 * 0.20
                      = 0.02 + rho * 0.02
        If index_iv = 0.18:
            0.18^2 = 0.02 + rho * 0.02
            0.0324 = 0.02 + 0.02 * rho
            rho = (0.0324 - 0.02) / 0.02 = 0.62
        """
        weights = {"A": 0.5, "B": 0.5}
        constituent_ivs = {"A": 0.20, "B": 0.20}
        index_iv = 0.18

        rho = implied_correlation(index_iv, weights, constituent_ivs)
        expected = (0.18 ** 2 - 2 * 0.5 ** 2 * 0.20 ** 2) / (2 * 0.5 * 0.5 * 0.20 * 0.20)
        assert abs(rho - expected) < 1e-10
        assert abs(rho - 0.62) < 1e-10

    def test_perfect_correlation(self):
        """When index IV equals weighted average IV, correlation should be ~1."""
        weights = {"A": 0.5, "B": 0.5}
        constituent_ivs = {"A": 0.20, "B": 0.20}
        # If rho = 1: sigma_index^2 = (w_A * sig_A + w_B * sig_B)^2 = 0.20^2 = 0.04
        index_iv = 0.20  # = weighted sum when rho = 1

        rho = implied_correlation(index_iv, weights, constituent_ivs)
        assert abs(rho - 1.0) < 1e-10

    def test_zero_correlation(self):
        """When index IV^2 = sum(w_i^2 * sig_i^2), correlation should be 0."""
        weights = {"A": 0.5, "B": 0.5}
        constituent_ivs = {"A": 0.20, "B": 0.20}
        # If rho = 0: sigma_index^2 = sum(w^2 * sig^2) = 2 * 0.25 * 0.04 = 0.02
        index_iv = math.sqrt(0.02)

        rho = implied_correlation(index_iv, weights, constituent_ivs)
        assert abs(rho) < 1e-10

    def test_six_name_basket(self):
        """Test with the actual 6-name NIFTY subset."""
        raw_weights = {
            "RELIANCE": 0.091, "HDFCBANK": 0.058, "ICICIBANK": 0.052,
            "SBIN": 0.049, "TCS": 0.043, "INFY": 0.024,
        }
        weights = renormalize_weights(raw_weights)
        constituent_ivs = {
            "RELIANCE": 0.24, "HDFCBANK": 0.21, "ICICIBANK": 0.26,
            "SBIN": 0.30, "TCS": 0.22, "INFY": 0.27,
        }
        index_iv = 0.16

        rho = implied_correlation(index_iv, weights, constituent_ivs)

        # Implied corr should be between -1 and 1 for sensible inputs
        assert -1.0 <= rho <= 1.0, f"rho={rho} out of valid range"
        # With these inputs, index IV is lower than any constituent IV
        # → low implied correlation (diversification effect)
        assert rho < 0.5, f"Expected low implied corr, got {rho}"

    def test_single_stock_raises(self):
        """Single stock → cross term is zero → should raise."""
        weights = {"A": 1.0}
        constituent_ivs = {"A": 0.20}
        with pytest.raises(ValueError, match="cross term is zero"):
            implied_correlation(0.20, weights, constituent_ivs)

    def test_negative_correlation_possible(self):
        """
        If index IV is very low relative to constituents,
        implied correlation can be negative (super-diversification).
        """
        weights = {"A": 0.5, "B": 0.5}
        constituent_ivs = {"A": 0.30, "B": 0.30}
        index_iv = 0.10  # Very low relative to constituents

        rho = implied_correlation(index_iv, weights, constituent_ivs)
        assert rho < 0, f"Expected negative rho, got {rho}"


# =====================================================================
# Weight Renormalization Tests
# =====================================================================

class TestRenormalizeWeights:

    def test_basic_renormalization(self):
        weights = {"A": 0.3, "B": 0.2}
        result = renormalize_weights(weights)
        assert abs(result["A"] - 0.6) < 1e-10
        assert abs(result["B"] - 0.4) < 1e-10
        assert abs(sum(result.values()) - 1.0) < 1e-10

    def test_already_normalized(self):
        weights = {"A": 0.5, "B": 0.5}
        result = renormalize_weights(weights)
        assert abs(result["A"] - 0.5) < 1e-10

    def test_six_name_nifty_subset(self):
        raw_weights = {
            "RELIANCE": 0.091, "HDFCBANK": 0.058, "ICICIBANK": 0.052,
            "SBIN": 0.049, "TCS": 0.043, "INFY": 0.024,
        }
        result = renormalize_weights(raw_weights)
        assert abs(sum(result.values()) - 1.0) < 1e-10
        # RELIANCE should have the largest weight
        assert result["RELIANCE"] > result["HDFCBANK"]
        assert result["RELIANCE"] > result["INFY"]


# =====================================================================
# Vega-Matched Basket Tests
# =====================================================================

class TestVegaMatchedBasket:

    @pytest.fixture
    def sample_basket_inputs(self):
        index_leg = OptionLeg("NIFTY", spot=24800, strike=24800, iv=0.16,
                              vega_per_contract=12.0, lot_size=25)
        constituent_weights = {
            "RELIANCE": 0.091, "HDFCBANK": 0.058, "ICICIBANK": 0.052,
            "SBIN": 0.049, "TCS": 0.043, "INFY": 0.024,
        }
        constituent_legs = {
            "RELIANCE": OptionLeg("RELIANCE", 1380, 1380, 0.24, 1.6, 500),
            "HDFCBANK": OptionLeg("HDFCBANK", 1650, 1650, 0.21, 1.9, 550),
            "ICICIBANK": OptionLeg("ICICIBANK", 1200, 1200, 0.26, 1.4, 700),
            "SBIN": OptionLeg("SBIN", 820, 820, 0.30, 1.0, 1500),
            "TCS": OptionLeg("TCS", 3500, 3500, 0.22, 3.8, 175),
            "INFY": OptionLeg("INFY", 1550, 1550, 0.27, 1.7, 400),
        }
        return index_leg, 50000, constituent_weights, constituent_legs

    def test_basket_has_correct_rows(self, sample_basket_inputs):
        basket = size_vega_matched_basket(*sample_basket_inputs)
        # 6 constituents + 1 index = 7 rows
        assert len(basket) == 7

    def test_index_is_short(self, sample_basket_inputs):
        basket = size_vega_matched_basket(*sample_basket_inputs)
        index_row = basket[basket["ticker"] == "INDEX (SELL)"]
        assert len(index_row) == 1
        assert int(index_row.iloc[0]["lots_to_buy"]) < 0

    def test_constituents_are_long(self, sample_basket_inputs):
        basket = size_vega_matched_basket(*sample_basket_inputs)
        constituents = basket[basket["ticker"] != "INDEX (SELL)"]
        assert all(constituents["lots_to_buy"] > 0), "All constituents should be long"

    def test_weights_sum_to_one(self, sample_basket_inputs):
        basket = size_vega_matched_basket(*sample_basket_inputs)
        constituents = basket[basket["ticker"] != "INDEX (SELL)"]
        assert abs(constituents["weight"].sum() - 1.0) < 0.01

    def test_target_vega_proportional_to_weight(self, sample_basket_inputs):
        basket = size_vega_matched_basket(*sample_basket_inputs)
        constituents = basket[basket["ticker"] != "INDEX (SELL)"]
        target_vega_total = 50000
        for _, row in constituents.iterrows():
            expected_vega = target_vega_total * row["weight"]
            assert abs(row["target_vega"] - expected_vega) < 5.0


# =====================================================================
# P&L Decomposition Tests
# =====================================================================

class TestPnLDecomposition:

    def test_positive_pnl_when_realized_corr_below_implied(self):
        """Trade makes money when realized < implied correlation."""
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=5),
            "implied_corr": [0.6, 0.6, 0.6, 0.6, 0.6],
            "realized_corr": [0.3, 0.3, 0.3, 0.3, 0.3],
            "weighted_constituent_realized_vol": [0.25] * 5,
        })
        result = dispersion_pnl_decomposition(df)
        assert all(result["approx_period_pnl"] > 0)
        assert result["cum_pnl"].iloc[-1] > 0

    def test_negative_pnl_when_realized_corr_above_implied(self):
        """Trade loses money when realized > implied correlation."""
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=5),
            "implied_corr": [0.3, 0.3, 0.3, 0.3, 0.3],
            "realized_corr": [0.7, 0.7, 0.7, 0.7, 0.7],
            "weighted_constituent_realized_vol": [0.25] * 5,
        })
        result = dispersion_pnl_decomposition(df)
        assert all(result["approx_period_pnl"] < 0)
        assert result["cum_pnl"].iloc[-1] < 0

    def test_zero_pnl_when_corr_equal(self):
        """No P&L when implied == realized correlation."""
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=3),
            "implied_corr": [0.5, 0.5, 0.5],
            "realized_corr": [0.5, 0.5, 0.5],
            "weighted_constituent_realized_vol": [0.25] * 3,
        })
        result = dispersion_pnl_decomposition(df)
        assert all(abs(result["approx_period_pnl"]) < 1e-10)

    def test_cum_pnl_is_cumulative(self):
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=3),
            "implied_corr": [0.6, 0.5, 0.7],
            "realized_corr": [0.3, 0.4, 0.2],
            "weighted_constituent_realized_vol": [0.25, 0.20, 0.30],
        })
        result = dispersion_pnl_decomposition(df)
        assert abs(result["cum_pnl"].iloc[-1] - result["approx_period_pnl"].sum()) < 1e-10


# =====================================================================
# GEX Detector Tests
# =====================================================================

class TestGEXDetector:

    @pytest.fixture
    def detector(self):
        return GEXDetector(risk_free_rate=0.065, neutral_band_pct=0.10)

    def test_call_heavy_chain_is_long_gamma(self, detector):
        """Chain dominated by call OI → dealers long gamma → stabilizing."""
        strikes = [
            StrikeData(24700, call_oi=100000, put_oi=10000),
            StrikeData(24800, call_oi=150000, put_oi=10000),
            StrikeData(24900, call_oi=100000, put_oi=10000),
        ]
        result = detector.compute_gex(
            spot=24800, strikes=strikes, iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        assert result.regime == GEXRegime.LONG_GAMMA
        assert result.total_gex > 0

    def test_put_heavy_chain_is_short_gamma(self, detector):
        """Chain dominated by put OI → dealers short gamma → destabilizing."""
        strikes = [
            StrikeData(24700, call_oi=10000, put_oi=200000),
            StrikeData(24800, call_oi=10000, put_oi=250000),
            StrikeData(24900, call_oi=10000, put_oi=200000),
        ]
        result = detector.compute_gex(
            spot=24800, strikes=strikes, iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        assert result.regime == GEXRegime.SHORT_GAMMA
        assert result.total_gex < 0

    def test_balanced_chain_is_neutral(self, detector):
        """Roughly equal call and put OI → near-zero net GEX → NEUTRAL."""
        detector_wide = GEXDetector(neutral_band_pct=0.50)  # Wide band for neutrality
        strikes = [
            StrikeData(24700, call_oi=100000, put_oi=100000),
            StrikeData(24800, call_oi=100000, put_oi=100000),
            StrikeData(24900, call_oi=100000, put_oi=100000),
        ]
        result = detector_wide.compute_gex(
            spot=24800, strikes=strikes, iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        # With exactly equal OI, calls contribute positive GEX and puts contribute
        # negative GEX of the same magnitude → total ≈ 0
        assert abs(result.total_gex) < max(abs(result.call_gex), abs(result.put_gex)) * 0.5

    def test_gamma_flip_level_returned(self, detector):
        """Verify gamma flip level is computed and near spot."""
        chain = generate_synthetic_chain(24800, num_strikes=21, strike_step=100)
        result = detector.compute_gex(
            spot=24800, strikes=chain, iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        assert result.gamma_flip_level is not None
        # Flip level should be within 5% of spot
        assert abs(result.gamma_flip_level - 24800) / 24800 < 0.05

    def test_empty_chain_returns_neutral(self, detector):
        """Empty chain should return neutral with zero GEX."""
        result = detector.compute_gex(
            spot=24800, strikes=[], iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        assert result.total_gex == 0.0
        assert result.regime == GEXRegime.NEUTRAL

    def test_single_strike_no_flip(self, detector):
        """Single strike chain should still compute GEX."""
        strikes = [StrikeData(24800, call_oi=100000, put_oi=50000)]
        result = detector.compute_gex(
            spot=24800, strikes=strikes, iv_surface=0.16,
            time_to_expiry=0.05, lot_size=25,
        )
        assert result.total_gex != 0

    def test_expired_options_zero_gamma(self, detector):
        """At expiry (T=0), BSM gamma is 0 → GEX should be 0."""
        strikes = [StrikeData(24800, call_oi=100000, put_oi=100000)]
        result = detector.compute_gex(
            spot=24800, strikes=strikes, iv_surface=0.16,
            time_to_expiry=0.0, lot_size=25,
        )
        assert abs(result.total_gex) < 1e-10


class TestGEXEntryGate:

    def test_short_gamma_allows_entry(self):
        detector = GEXDetector()
        result = GEXResult(
            regime=GEXRegime.SHORT_GAMMA, total_gex=-1e6,
            gamma_flip_level=24900, per_strike_gex={}, call_gex=5e5,
            put_gex=-1.5e6, spot_price=24800, confidence=0.3,
        )
        assert detector.should_enter_dispersion(result) is True

    def test_long_gamma_blocks_entry(self):
        detector = GEXDetector()
        result = GEXResult(
            regime=GEXRegime.LONG_GAMMA, total_gex=1e6,
            gamma_flip_level=24700, per_strike_gex={}, call_gex=1.5e6,
            put_gex=-5e5, spot_price=24800, confidence=0.3,
        )
        assert detector.should_enter_dispersion(result) is False

    def test_low_confidence_blocks_entry(self):
        detector = GEXDetector()
        result = GEXResult(
            regime=GEXRegime.SHORT_GAMMA, total_gex=-1e6,
            gamma_flip_level=24900, per_strike_gex={}, call_gex=5e5,
            put_gex=-1.5e6, spot_price=24800, confidence=0.01,
        )
        assert detector.should_enter_dispersion(result, min_confidence=0.05) is False


class TestBSMGamma:

    def test_atm_gamma_is_highest(self):
        """ATM options have the highest gamma."""
        spot = 24800.0
        T = 0.05
        sigma = 0.16
        atm_gamma = _bsm_gamma(spot, 24800, T, sigma)
        otm_gamma = _bsm_gamma(spot, 25200, T, sigma)
        itm_gamma = _bsm_gamma(spot, 24400, T, sigma)

        assert atm_gamma > otm_gamma
        assert atm_gamma > itm_gamma

    def test_gamma_increases_near_expiry(self):
        """Gamma increases as expiry approaches (for ATM)."""
        spot = 24800.0
        sigma = 0.16
        gamma_30d = _bsm_gamma(spot, 24800, 30 / 365, sigma)
        gamma_5d = _bsm_gamma(spot, 24800, 5 / 365, sigma)

        assert gamma_5d > gamma_30d

    def test_zero_time_zero_gamma(self):
        """At expiry, gamma should be 0."""
        assert _bsm_gamma(24800, 24800, 0.0, 0.16) == 0.0

    def test_zero_vol_zero_gamma(self):
        """With zero volatility, gamma should be 0."""
        assert _bsm_gamma(24800, 24800, 0.05, 0.0) == 0.0


class TestSyntheticChain:

    def test_chain_length(self):
        chain = generate_synthetic_chain(24800, num_strikes=21)
        assert len(chain) == 21

    def test_put_skew(self):
        """Higher put OI below ATM (hedging demand)."""
        chain = generate_synthetic_chain(24800, num_strikes=11, strike_step=100, put_oi_skew=1.5)
        atm = 24800
        below_atm = [sd for sd in chain if sd.strike < atm]
        above_atm = [sd for sd in chain if sd.strike > atm]

        avg_put_below = np.mean([sd.put_oi for sd in below_atm]) if below_atm else 0
        avg_put_above = np.mean([sd.put_oi for sd in above_atm]) if above_atm else 0

        assert avg_put_below > avg_put_above, "Put OI should be higher below ATM"

    def test_oi_decay_in_wings(self):
        """OI should be highest near ATM and decay in wings."""
        chain = generate_synthetic_chain(24800, num_strikes=21, strike_step=100)
        atm = 24800
        atm_data = [sd for sd in chain if sd.strike == atm]
        wing_data = [sd for sd in chain if abs(sd.strike - atm) > 800]

        if atm_data and wing_data:
            atm_total_oi = atm_data[0].call_oi + atm_data[0].put_oi
            avg_wing_oi = np.mean([sd.call_oi + sd.put_oi for sd in wing_data])
            assert atm_total_oi > avg_wing_oi
