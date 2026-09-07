import pytest
from engine.types import Position, InstrumentType
from fno.margin_engine import MarginEngine

def test_span_margin_long_future():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.FUT, size=50)
    # price = 20000, vol = 0.15
    span = engine.calculate_span_margin(pos, 20000.0, 0.15)
    # price_scan = 0.1, max price move mult = 3/3 = 1
    # max price move = 1 * 0.1 * 0.15 = 0.015
    # span = 0.015 * 50 * 20000 = 15000
    assert span == pytest.approx(15000.0)

def test_span_margin_short_option():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.CE, size=-50)
    span = engine.calculate_span_margin(pos, 20000.0, 0.15)
    assert span == pytest.approx(-1650.0)

def test_exposure_margin():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.FUT, size=50)
    exposure = engine.calculate_exposure_margin(pos, 20000.0)
    # 5% of (50*20000) = 5% of 1000000 = 50000
    assert exposure == pytest.approx(50000.0)
    
    pos_opt = Position(symbol="NIFTY", instrument_type=InstrumentType.CE, size=50)
    exposure_opt = engine.calculate_exposure_margin(pos_opt, 20000.0)
    # 2% of 1000000 = 20000
    assert exposure_opt == pytest.approx(20000.0)

def test_total_margin():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.FUT, size=50)
    total = engine.calculate_total_margin(pos, 20000.0, 0.15)
    # SPAN (15000) + Exposure (50000) = 65000
    assert total == pytest.approx(65000.0)

def test_margin_check_sufficient():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.FUT, size=50)
    sufficient, ratio = engine.check_margin_requirement(
        [pos], 
        available_capital=100000.0, 
        prices={"NIFTY": 20000.0}, 
        vols={"NIFTY": 0.15}
    )
    assert sufficient is True
    assert ratio == pytest.approx(65000.0 / 100000.0)

def test_margin_check_insufficient():
    engine = MarginEngine()
    pos = Position(symbol="NIFTY", instrument_type=InstrumentType.FUT, size=50)
    sufficient, ratio = engine.check_margin_requirement(
        [pos], 
        available_capital=50000.0, 
        prices={"NIFTY": 20000.0}, 
        vols={"NIFTY": 0.15}
    )
    assert sufficient is False
    assert ratio == pytest.approx(65000.0 / 50000.0)
