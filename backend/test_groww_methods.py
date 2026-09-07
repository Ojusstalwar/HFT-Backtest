import os
from growwapi import GrowwAPI

token = None
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GROWW_API_KEY="):
                token = line.strip().split("GROWW_API_KEY=")[1].strip("'\"")

groww = GrowwAPI(token)

print("1. Testing get_quote for RELIANCE...")
try:
    q = groww.get_quote(
        trading_symbol="RELIANCE",
        exchange=groww.EXCHANGE_NSE,
        segment=groww.SEGMENT_CASH
    )
    print("Quote:", q)
except Exception as e:
    print("Quote Error:", e)

print("\n2. Testing get_ltp for NSE_RELIANCE...")
try:
    ltp = groww.get_ltp(
        exchange_trading_symbols=("NSE_RELIANCE",),
        segment=groww.SEGMENT_CASH
    )
    print("LTP:", ltp)
except Exception as e:
    print("LTP Error:", e)

print("\n3. Testing get_expiries for NIFTY...")
try:
    expiries = groww.get_expiries(
        exchange=groww.EXCHANGE_NSE,
        underlying="NIFTY"
    )
    print("Expiries:", expiries)
except Exception as e:
    print("Expiries Error:", e)
