import os
import sys
from growwapi import GrowwAPI

api_key = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NzYzOTg5MjksImlhdCI6MTc4Nzk5ODkyOSwibmJmIjoxNzg3OTk4OTI5LCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJiYzZmYzUzNi00YmM3LTQ1OTItOGNiYS1jM2QxMjY0YTZjNGNcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiNmRiMWM0OGItMjAxZi00MGMzLTliNzQtMGM2ODUyZDUxMzczXCIsXCJkZXZpY2VJZFwiOlwiNWNhOWEyZjYtY2FkMS01YmQzLWExNTAtMmI4NTk5N2Y1OWUwXCIsXCJzZXNzaW9uSWRcIjpcImMwNGQ5MjhkLTI4ZTgtNGM1OC05NTBiLTgwMTcyOTdiMTZkOFwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYkdzSWc1NDQ1Q0RDb1pOWjU3bmt4T3hSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxMDMuMjExLjUzLjIwLDEwNC4yMi40OC4yMTIsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NzYzOTg5Mjk2OTAsXCJ2ZW5kb3JOYW1lXCI6XCJncm93d0FwaVwifSIsImlzcyI6ImFwZXgtYXV0aC1wcm9kLWFwcCJ9.bVLMJxP0agTNuhohvUPelwxDy7H-5odTkPjTkW7vZ-7trGhMq1BeLmCplmcc4XMG_a_quINh3c3BK6v_stTunQ"

if len(sys.argv) > 1:
    totp = sys.argv[1].strip()
    print(f"Testing with TOTP code: {totp}")
    try:
        token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
        print("\n? SUCCESS! Live Session Access Token received:")
        print(token)
        
        # Test Live Data with new session token
        groww = GrowwAPI(token)
        q = groww.get_quote(trading_symbol="RELIANCE", exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_CASH)
        print("\n?? RELIANCE Live Quote:")
        print(q)
    except Exception as e:
        print(f"\n? Error with TOTP {totp}: {e}")
else:
    print("Please pass your current 6-digit TOTP: python test_live_groww_login.py <6_DIGIT_TOTP>")
