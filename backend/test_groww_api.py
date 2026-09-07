import os
import json
import base64
import requests

def parse_jwt(token):
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            padded = payload + "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode()).decode()
            return json.loads(decoded)
    except Exception as e:
        return {"error": str(e)}
    return {}

def test_groww():
    token = None
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GROWW_API_KEY="):
                    token = line.strip().split("GROWW_API_KEY=")[1].strip("'\"")
    
    if not token:
        token = os.getenv("GROWW_API_KEY")
        
    print("=" * 60)
    print(" ?? GROWW API AUTHENTICATION & TOKEN INSPECTION")
    print("=" * 60)
    
    if not token:
        print("[ERROR] GROWW_API_KEY not found!")
        return

    print(f"[OK] Loaded Token (length: {len(token)} chars)")
    payload = parse_jwt(token)
    
    if "error" not in payload:
        print(f"  Issuer: {payload.get('iss')}")
        print(f"  Subject: {payload.get('sub')}")
        print(f"  Expiry TS: {payload.get('exp')}")
    else:
        print(f"  Token Parse Info: {payload}")

    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    # Test Groww API endpoints
    endpoints = [
        ("Groww Stocks Search / Quote", "https://groww.in/v1/api/stocks_data/v1/tr_live_prices/exchange/NSE/segment/CASH/latest_prices?symbols=RELIANCE,HDFCBANK"),
        ("Groww Holdings / User", "https://groww.in/v1/api/user/v1/holdings"),
        ("Groww F&O Option Chain", "https://groww.in/v1/api/option_chain/v1/exchange/NSE/symbol/NIFTY"),
    ]

    for name, url in endpoints:
        print(f"\nTesting {name}: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"  Status Code: {resp.status_code}")
            try:
                data = resp.json()
                sample = str(data)[:200]
                print(f"  Response Data: {sample}...")
            except:
                print(f"  Response Text: {resp.text[:200]}")
        except Exception as e:
            print(f"  Request error: {e}")

if __name__ == "__main__":
    test_groww()
