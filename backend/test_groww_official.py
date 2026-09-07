import os
from growwapi import GrowwAPI

token = None
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GROWW_API_KEY="):
                token = line.strip().split("GROWW_API_KEY=")[1].strip("'\"")

if not token:
    token = os.getenv("GROWW_API_KEY")

print("=" * 60)
print(" ?? INITIALIZING OFFICIAL GROWW SDK (growwapi)")
print("=" * 60)

try:
    groww = GrowwAPI(token)
    print("? GrowwAPI instance initialized successfully!")

    print("\n1. Testing User Profile / Account Details...")
    try:
        profile = groww.get_user_profile()
        print(f"   Profile response: {profile}")
    except Exception as e:
        print(f"   Profile error: {e}")

    print("\n2. Testing Margin / Funds...")
    try:
        margins = groww.get_available_margin_details()
        print(f"   Margin Details: {margins}")
    except Exception as e:
        print(f"   Margin error: {e}")

    print("\n3. Testing Real-time Quotes / LTP (RELIANCE on NSE)...")
    try:
        ltp = groww.get_ltp(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            trading_symbol="RELIANCE"
        )
        print(f"   RELIANCE LTP: Rs. {ltp}")
    except Exception as e:
        print(f"   LTP error: {e}")

    print("\n4. Testing NIFTY Option Chain / Greeks...")
    try:
        chain = groww.get_option_chain(
            exchange=groww.EXCHANGE_NSE,
            underlying_symbol="NIFTY"
        )
        print(f"   Option Chain Data: {str(chain)[:300]}...")
    except Exception as e:
        print(f"   Option chain error: {e}")

except Exception as e:
    print(f"? Failed to connect GrowwAPI: {e}")
