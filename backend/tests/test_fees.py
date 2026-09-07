import pytest
from engine.types import Fill, InstrumentType, Side, Position
from engine.config import FeeConfig
from engine.fees import FeeCalculator

@pytest.fixture
def fees():
    config = FeeConfig(broker_commission_per_order=0.0, stamp_duty_rate=0.00015, stamp_duty_state="test")
    return FeeCalculator(config)

def test_equity_delivery_stt(fees):
    # Buy side
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=100.0, size=100, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_stt(fill, InstrumentType.EQ, is_delivery=True) == 10.0 # 0.1% of 10000
    
    # Sell side
    fill.side = Side.SELL
    assert fees.calculate_stt(fill, InstrumentType.EQ, is_delivery=True) == 10.0

def test_equity_intraday_stt(fees):
    # Buy side
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=100.0, size=100, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_stt(fill, InstrumentType.EQ, is_delivery=False) == 0.0
    
    # Sell side
    fill.side = Side.SELL
    assert fees.calculate_stt(fill, InstrumentType.EQ, is_delivery=False) == 2.5 # 0.025% of 10000

def test_futures_stt(fees):
    # Buy side
    fill = Fill(order_id="1", symbol="NIFTY", side=Side.BUY, price=10000.0, size=50, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_stt(fill, InstrumentType.FUT, is_delivery=False) == 0.0
    
    # Sell side
    fill.side = Side.SELL
    assert fees.calculate_stt(fill, InstrumentType.FUT, is_delivery=False) == 62.5 # 0.0125% of 500000

def test_options_stt(fees):
    # Buy side
    fill = Fill(order_id="1", symbol="NIFTY", side=Side.BUY, price=100.0, size=50, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_stt(fill, InstrumentType.CE, is_delivery=False) == 0.0
    
    # Sell side
    fill.side = Side.SELL
    assert fees.calculate_stt(fill, InstrumentType.CE, is_delivery=False) == 3.125 # 0.0625% of 5000

def test_options_exercise_stt(fees):
    stt = fees.calculate_exercise_stt(settlement_price=20500, lot_size=75, instrument_type=InstrumentType.CE)
    assert stt == pytest.approx(1921.875)

def test_transaction_charges(fees):
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=100.0, size=100, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_transaction_charges(fill, InstrumentType.EQ) == pytest.approx(0.297) # 0.00297% of 10000
    
    fill = Fill(order_id="1", symbol="NIFTY", side=Side.BUY, price=10000.0, size=50, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_transaction_charges(fill, InstrumentType.FUT) == pytest.approx(9.5) # 0.00190% of 500000
    
    fill = Fill(order_id="1", symbol="NIFTY", side=Side.BUY, price=100.0, size=50, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_transaction_charges(fill, InstrumentType.CE) == pytest.approx(2.5) # 0.05% of 5000

def test_gst(fees):
    assert fees.calculate_gst(brokerage=20.0, transaction_charges=10.0) == pytest.approx(5.4) # 18% of 30

def test_stamp_duty(fees):
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=100.0, size=100, timestamp_ns=1000, is_maker=True)
    assert fees.calculate_stamp_duty(fill) == pytest.approx(1.5) # 0.015% of 10000
    
    fill.side = Side.SELL
    assert fees.calculate_stamp_duty(fill) == 0.0

def test_sebi_fee(fees):
    fill = Fill(order_id="1", symbol="AAPL", side=Side.BUY, price=100.0, size=10000, timestamp_ns=1000, is_maker=True) # 10 lakhs
    assert fees.calculate_sebi_turnover_fee(fill) == pytest.approx(1.0) # 10 per crore => 1 per 10 lakhs
