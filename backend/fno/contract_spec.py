from __future__ import annotations
from datetime import date, timedelta
import calendar
import logging
from engine.types import ContractSpec, InstrumentType, ConfigurationError

logger = logging.getLogger(__name__)

class ContractSpecDB:
    """
    NSE F&O contract specifications database.
    """
    
    _LOT_SIZES = {
        "NIFTY": 75,
        "BANKNIFTY": 30,
        "RELIANCE": 250,
        "TCS": 150,
        "INFY": 300,
        "HDFCBANK": 550,
        "SBIN": 1500,
        "ITC": 1600,
        "TATAMOTORS": 700,
        "LT": 150,
    }

    _STRIKE_INTERVALS = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
    }

    @classmethod
    def get_spec(cls, symbol: str, instrument_type: InstrumentType, expiry_date: date | None = None, strike_price: float | None = None) -> ContractSpec:
        """Get the contract specification for a given symbol and instrument."""
        lot_size = cls.get_lot_size(symbol)
        tick_size = cls.get_tick_size(instrument_type)
        return ContractSpec(
            symbol=symbol,
            instrument_type=instrument_type,
            lot_size=lot_size,
            tick_size=tick_size,
            expiry_date=expiry_date,
            strike_price=strike_price
        )

    @classmethod
    def get_lot_size(cls, symbol: str) -> int:
        """Get the built-in lot size for major NSE symbols."""
        return cls._LOT_SIZES.get(symbol, 1)

    @classmethod
    def get_tick_size(cls, instrument_type: InstrumentType) -> float:
        """Get the tick size for the instrument type."""
        return 0.05

    @classmethod
    def get_next_expiry(cls, from_date: date, expiry_type: str = 'monthly') -> date:
        """Calculate the next expiry date."""
        if expiry_type == 'monthly':
            # Last Thursday of month
            dates = cls.get_expiry_dates(from_date.year, from_date.month)
            if dates:
                last_thursday = dates[-1]
                if last_thursday >= from_date:
                    return last_thursday
            
            # Next month
            next_month_date = from_date.replace(day=28) + timedelta(days=4)
            return cls.get_expiry_dates(next_month_date.year, next_month_date.month)[-1]
        elif expiry_type == 'weekly':
            # Every Thursday
            days_ahead = 3 - from_date.weekday()
            if days_ahead < 0:
                days_ahead += 7
            return from_date + timedelta(days=days_ahead)
        else:
            raise ValueError(f"Unknown expiry type: {expiry_type}")

    @classmethod
    def get_expiry_dates(cls, year: int, month: int) -> list[date]:
        """Get all Thursday expiry dates for a given month."""
        c = calendar.monthcalendar(year, month)
        thursdays = []
        for week in c:
            if week[calendar.THURSDAY] != 0:
                thursdays.append(date(year, month, week[calendar.THURSDAY]))
        return thursdays

    @classmethod
    def is_expiry_day(cls, d: date) -> bool:
        """Check if a given date is an expiry day (Thursday)."""
        return d.weekday() == calendar.THURSDAY

    @classmethod
    def get_strike_range(cls, underlying_price: float, symbol: str, num_strikes: int = 10) -> list[float]:
        """Get a range of strike prices around the underlying price."""
        interval = cls._STRIKE_INTERVALS.get(symbol, 10)
        atm_strike = round(underlying_price / interval) * interval
        strikes = []
        for i in range(-num_strikes, num_strikes + 1):
            strikes.append(atm_strike + i * interval)
        return strikes
