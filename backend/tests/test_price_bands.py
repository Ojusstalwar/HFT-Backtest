import pytest
from engine.price_bands import PriceBandManager

def test_set_and_get_band():
    pb = PriceBandManager()
    pb.set_band("AAPL", reference_price=100.0, band_pct=0.05)
    band = pb.get_band("AAPL", 1000)
    assert band is not None
    assert band.lower == 95.0
    assert band.upper == 105.0

def test_within_band():
    pb = PriceBandManager()
    pb.set_band("AAPL", reference_price=100.0, band_pct=0.05)
    assert pb.is_within_band("AAPL", 100.0)
    assert pb.is_within_band("AAPL", 95.0)
    assert pb.is_within_band("AAPL", 105.0)

def test_outside_band():
    pb = PriceBandManager()
    pb.set_band("AAPL", reference_price=100.0, band_pct=0.05)
    assert not pb.is_within_band("AAPL", 94.9)
    assert not pb.is_within_band("AAPL", 105.1)

def test_circuit_breaker_10pct():
    pb = PriceBandManager()
    # 10% move before 13:00 triggers 45 min halt.
    # We will use 10:00 AM IST => 10*3600 + 5.5 hours IST shift but we can mock timestamp to be 10:00 IST.
    # 10:00 IST is 04:30 UTC. 04:30:00 is 4*3600+1800 = 16200 sec.
    timestamp_ns = 16200 * 1_000_000_000 # 1970-01-01 10:00 IST
    
    halt_duration_ns = pb.trigger_circuit_breaker("NIFTY", 0.10, timestamp_ns)
    assert halt_duration_ns == 45 * 60 * 1_000_000_000
    assert pb.is_halted("AAPL", timestamp_ns + 10 * 60 * 1_000_000_000) # halted
    assert not pb.is_halted("AAPL", timestamp_ns + 46 * 60 * 1_000_000_000) # unhalted

def test_circuit_breaker_20pct():
    pb = PriceBandManager()
    # 20% move at 10:00 IST => halt for remainder of day (16:00 is 16*60 minutes from start? Actually max(0, 16*60 - (10*60+0)) = 6*60 = 360 mins)
    timestamp_ns = 16200 * 1_000_000_000 # 10:00 IST
    halt_duration_ns = pb.trigger_circuit_breaker("NIFTY", 0.20, timestamp_ns)
    assert halt_duration_ns == 360 * 60 * 1_000_000_000
    assert pb.is_halted("AAPL", timestamp_ns + 10 * 60 * 1_000_000_000)

def test_is_halted():
    pb = PriceBandManager()
    pb._halts["AAPL"] = 2000
    assert pb.is_halted("AAPL", 1000)
    assert not pb.is_halted("AAPL", 2001)
    
def test_fno_no_band():
    # As per instructions: "test_fno_no_band: F&O derivatives don't have direct bands"
    pb = PriceBandManager()
    # No band set, is_within_band returns True
    assert pb.is_within_band("NIFTY26AUGFUT", 100000.0)
