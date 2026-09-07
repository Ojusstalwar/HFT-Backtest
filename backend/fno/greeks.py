from __future__ import annotations
import math
import logging
from datetime import date
from engine.types import Greeks, InstrumentType, ConfigurationError
from engine.config import GreeksConfig

logger = logging.getLogger(__name__)

class GreeksCalculator:
    """Options pricing and Greeks computation.
    
    WARNING: European-style only. Pre-2021 NSE stock options were American-style.
    Framework does NOT support American pricing.
    """
    
    def __init__(self, config: GreeksConfig):
        self.config = config
        if not hasattr(config, 'risk_free_rate') or config.risk_free_rate is None:
            raise ConfigurationError("risk_free_rate must be configured")
        if not hasattr(config, 'dividend_yield') or config.dividend_yield is None:
            raise ConfigurationError("dividend_yield must be configured")

    def get_risk_free_rate(self, current_date: date) -> float:
        """Get interpolated risk-free rate for the date."""
        return self.config.risk_free_rate

    def get_dividend_yield(self, symbol: str, current_date: date) -> float:
        """Get dividend yield for the symbol on the date."""
        return self.config.dividend_yield

    def black_scholes_price(self, S: float, K: float, T: float, r: float, sigma: float, q: float, option_type: InstrumentType) -> float:
        """Raw Black-Scholes formula for European options."""
        if T <= 0 or sigma <= 0:
            return max(0.0, S - K) if option_type == InstrumentType.CALL else max(0.0, K - S)

        try:
            from scipy.stats import norm
            cdf = norm.cdf
        except ImportError:
            def cdf(x):
                return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == InstrumentType.CALL:
            return S * math.exp(-q * T) * cdf(d1) - K * math.exp(-r * T) * cdf(d2)
        elif option_type == InstrumentType.PUT:
            return K * math.exp(-r * T) * cdf(-d2) - S * math.exp(-q * T) * cdf(-d1)
        else:
            raise ValueError(f"Invalid option type for pricing: {option_type}")

    def calculate_iv(self, market_price: float, underlying_price: float, strike: float, expiry_date: date, option_type: InstrumentType, current_date: date) -> float:
        """Calculate Implied Volatility using Newton-Raphson solver."""
        T = (expiry_date - current_date).days / 365.25
        if T <= 0:
            return float('nan')
            
        r = self.get_risk_free_rate(current_date)
        q = self.get_dividend_yield("", current_date)
        
        sigma = 0.2
        max_iter = 100
        tol = 1e-8
        
        try:
            from scipy.stats import norm
            pdf = norm.pdf
        except ImportError:
            def pdf(x):
                return math.exp(-x**2/2) / math.sqrt(2*math.pi)
        
        for _ in range(max_iter):
            price = self.black_scholes_price(underlying_price, strike, T, r, sigma, q, option_type)
            diff = market_price - price
            if abs(diff) < tol:
                return sigma
                
            d1 = (math.log(underlying_price / strike) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            vega = underlying_price * math.exp(-q * T) * pdf(d1) * math.sqrt(T)
            
            if vega == 0:
                break
                
            sigma += diff / vega
            if sigma <= 0:
                sigma = 0.001
                
        return float('nan')

    def calculate_greeks(self, underlying_price: float, strike: float, expiry_date: date, option_type: InstrumentType, current_date: date, iv: float | None = None, market_price: float | None = None) -> Greeks:
        """Compute Black-Scholes Greeks."""
        if iv is None and market_price is not None:
            iv = self.calculate_iv(market_price, underlying_price, strike, expiry_date, option_type, current_date)
            
        if iv is None or math.isnan(iv):
            return Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

        T = (expiry_date - current_date).days / 365.25
        if T <= 0:
            if option_type == InstrumentType.CALL:
                delta = 1.0 if underlying_price > strike else 0.0
            else:
                delta = -1.0 if underlying_price < strike else 0.0
            return Greeks(delta=delta, gamma=0.0, theta=0.0, vega=0.0)

        r = self.get_risk_free_rate(current_date)
        q = self.get_dividend_yield("", current_date)
        
        try:
            from scipy.stats import norm
            cdf = norm.cdf
            pdf = norm.pdf
        except ImportError:
            def cdf(x):
                return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
            def pdf(x):
                return math.exp(-x**2/2) / math.sqrt(2*math.pi)

        d1 = (math.log(underlying_price / strike) + (r - q + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
        d2 = d1 - iv * math.sqrt(T)

        if option_type == InstrumentType.CALL:
            delta = math.exp(-q * T) * cdf(d1)
            theta = (-underlying_price * math.exp(-q * T) * pdf(d1) * iv / (2 * math.sqrt(T)) 
                     - r * strike * math.exp(-r * T) * cdf(d2) 
                     + q * underlying_price * math.exp(-q * T) * cdf(d1))
        else:
            delta = math.exp(-q * T) * (cdf(d1) - 1)
            theta = (-underlying_price * math.exp(-q * T) * pdf(d1) * iv / (2 * math.sqrt(T)) 
                     + r * strike * math.exp(-r * T) * cdf(-d2) 
                     - q * underlying_price * math.exp(-q * T) * cdf(-d1))

        gamma = math.exp(-q * T) * pdf(d1) / (underlying_price * iv * math.sqrt(T))
        vega = underlying_price * math.exp(-q * T) * pdf(d1) * math.sqrt(T)
        
        return Greeks(delta=delta, gamma=gamma, theta=theta / 365.25, vega=vega / 100)
