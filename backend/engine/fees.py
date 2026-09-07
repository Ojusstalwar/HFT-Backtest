from __future__ import annotations

import logging
from typing import Optional

from engine.types import Fill, InstrumentType, Side, Position
from engine.config import FeeConfig

logger = logging.getLogger(__name__)

class FeeCalculator:
    """
    Complete NSE/BSE fee engine for Indian markets.
    """
    def __init__(self, config: FeeConfig) -> None:
        self.config = config

    def calculate_stt(self, fill: Fill, instrument_type: InstrumentType, is_delivery: bool) -> float:
        """Calculate Securities Transaction Tax (STT)."""
        notional = fill.price * fill.size
        stt = 0.0
        
        if instrument_type == InstrumentType.EQ:
            if is_delivery:
                stt = notional * 0.001  # 0.1% buy+sell
            else:
                if fill.side == Side.SELL:
                    stt = notional * 0.00025  # 0.025% sell only
        elif instrument_type == InstrumentType.FUT:
            if fill.side == Side.SELL:
                stt = notional * 0.000125  # 0.0125% sell only
        elif instrument_type in (InstrumentType.CE, InstrumentType.PE):
            if fill.side == Side.SELL:
                stt = notional * 0.000625  # 0.0625% sell only
                
        return stt

    def calculate_exercise_stt(self, settlement_price: float, lot_size: int, instrument_type: InstrumentType) -> float:
        """
        Calculate STT for option exercise.
        CRITICAL: For CE/PE exercise, STT = 0.125% * settlement_price * lot_size (FULL NOTIONAL).
        """
        if instrument_type in (InstrumentType.CE, InstrumentType.PE):
            return 0.00125 * settlement_price * lot_size
        return 0.0

    def calculate_transaction_charges(self, fill: Fill, instrument_type: InstrumentType) -> float:
        """Calculate exchange transaction charges."""
        notional = fill.price * fill.size
        
        if instrument_type == InstrumentType.EQ:
            return notional * 0.0000297  # 0.00297%
        elif instrument_type == InstrumentType.FUT:
            return notional * 0.0000190  # 0.00190%
        elif instrument_type in (InstrumentType.CE, InstrumentType.PE):
            return notional * 0.0005  # 0.05% on premium
            
        return 0.0

    def calculate_sebi_turnover_fee(self, fill: Fill) -> float:
        """Calculate SEBI turnover fee (₹10 per crore)."""
        notional = fill.price * fill.size
        return notional * (10 / 10000000)

    def calculate_stamp_duty(self, fill: Fill) -> float:
        """Calculate stamp duty based on state-dependent configurable rate."""
        if fill.side == Side.BUY:
            notional = fill.price * fill.size
            return notional * self.config.stamp_duty_rate
        return 0.0

    def calculate_broker_commission(self) -> float:
        """Calculate flat per-order broker commission."""
        return getattr(self.config, 'broker_commission_per_order', getattr(self.config, 'broker_commission', 0.0))

    def calculate_gst(self, brokerage: float, transaction_charges: float) -> float:
        """Calculate GST (18% on brokerage + transaction charges)."""
        return 0.18 * (brokerage + transaction_charges)

    def is_delivery(self, fill: Fill, position_before: Optional[Position]) -> bool:
        """
        Determines if an equity trade is delivery or intraday based on position sign change.
        """
        if not position_before or position_before.size == 0:
            # We don't know yet, assume intraday until end of day for simple tracking,
            # but strictly speaking this might be delivery if held overnight.
            # True intraday checking often requires end of day resolution.
            # We will approximate based on position crossing zero or not closing.
            return True
            
        pos_qty = position_before.size
        if (pos_qty > 0 and fill.side == Side.SELL) or (pos_qty < 0 and fill.side == Side.BUY):
            return False  # Closing an intraday position
            
        return True # Adding to position, assume delivery for now

    def calculate_trade_fees(self, fill: Fill, instrument_type: InstrumentType = InstrumentType.EQ, position_before: Optional[Position] = None) -> float:
        """
        Returns total fee for a single fill.
        """
        is_deliv = self.is_delivery(fill, position_before)
        
        stt = self.calculate_stt(fill, instrument_type, is_deliv)
        txn_charges = self.calculate_transaction_charges(fill, instrument_type)
        sebi_fee = self.calculate_sebi_turnover_fee(fill)
        stamp_duty = self.calculate_stamp_duty(fill)
        brokerage = self.calculate_broker_commission()
        
        gst = self.calculate_gst(brokerage, txn_charges)
        
        return stt + txn_charges + sebi_fee + stamp_duty + brokerage + gst
