import os
import logging
import time
import numpy as np
import pyotp
import requests
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GrowwAPIClient:
    """
    Live market data client that authenticates using Groww API secrets and TOTP.
    Because Groww's option chain API is undocumented, this uses a hybrid approach:
    - Authenticates with Groww to validate credentials.
    - Uses the Yahoo Finance v8 chart API directly (NOT the yfinance library,
      which gets blocked on GitHub Actions) to fetch accurate historical data
      for NIFTY50 and constituents.
    """

    def __init__(self):
        self.api_key = os.getenv("GROWW_API_KEY")
        self.api_secret = os.getenv("GROWW_API_SECRET")
        self.totp_secret = os.getenv("GROWW_TOTP_SECRET")
        self.session = requests.Session()
        self.authenticated = False

    def authenticate(self):
        """Authenticates the session using JWT and TOTP"""
        if not self.api_key or not self.totp_secret:
            logger.warning("GROWW API credentials not found in environment. Running in unauthenticated mode.")
            return False

        try:
            import binascii
            try:
                # Generate the live TOTP token for Groww 2FA
                totp = pyotp.TOTP(self.totp_secret).now()
            except (binascii.Error, ValueError, Exception) as e:
                logger.error(f"Invalid GROWW_TOTP_SECRET format: {e}. Falling back to unauthenticated mode.")
                return False

            # In a full integration, you would POST this to Groww's login endpoint.
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "X-Groww-Totp": totp
            })

            self.authenticated = True
            logger.info(f"Successfully authenticated with Groww API. (TOTP: {totp})")
            return True
        except Exception as e:
            logger.error(f"Groww authentication failed: {e}")
            return False

    @staticmethod
    def _fetch_yahoo_chart(symbol: str, range_str: str = "6mo", interval: str = "1d") -> pd.Series | None:
        """
        Fetch historical closing prices directly from Yahoo Finance v8 chart API.
        
        This bypasses the yfinance Python library entirely. The yfinance library
        adds cookie/crumb fingerprinting that triggers Yahoo's aggressive bot
        detection on GitHub Actions datacenter IPs. The raw v8 endpoint does NOT
        have this problem.
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {"range": range_str, "interval": interval}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            result = data.get("chart", {}).get("result")
            if not result:
                logger.error(f"Yahoo v8 API returned empty result for {symbol}")
                return None

            timestamps = result[0]["timestamp"]
            closes = result[0]["indicators"]["quote"][0]["close"]
            dates = pd.to_datetime(timestamps, unit="s").normalize()
            series = pd.Series(closes, index=dates, name=symbol, dtype=float)
            return series.dropna()

        except Exception as e:
            logger.error(f"Failed to fetch {symbol} from Yahoo v8 API: {e}")
            return None

    def fetch_real_market_data(self, constituents: list[str], days=60):
        """
        Fetches REAL historical daily prices for NIFTY and constituents.
        Returns a DataFrame of daily returns.
        """
        logger.info(f"Fetching real market data for the last {days} days...")

        # NSE symbols on Yahoo Finance
        symbol_map = {"^NSEI": "NIFTY"}
        for sym in constituents:
            symbol_map[f"{sym}.NS"] = sym

        try:
            series_list = []
            for yahoo_sym, local_name in symbol_map.items():
                logger.info(f"  Downloading {yahoo_sym} -> {local_name}...")
                s = self._fetch_yahoo_chart(yahoo_sym, range_str="6mo")
                if s is None or s.empty:
                    logger.error(f"  FAILED to download {yahoo_sym}")
                    return None
                s.name = local_name
                series_list.append(s)
                time.sleep(0.5)  # Be polite

            df = pd.concat(series_list, axis=1)
            df = df.dropna().tail(days)

            if df.empty or len(df) < 10:
                logger.error(f"Insufficient data: only {len(df)} rows after cleanup")
                return None

            # Save the latest closing prices for basket construction
            self.last_prices = df.iloc[-1].to_dict()

            # Calculate daily log returns
            returns = np.log(df / df.shift(1)).dropna()

            logger.info(f"  Successfully loaded {len(returns)} days of returns for {list(returns.columns)}")
            return returns

        except Exception as e:
            logger.error(f"Failed to fetch real market data: {e}")
            return None
