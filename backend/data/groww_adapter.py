"""
data/groww_adapter.py
======================
Production Live Data & Order Routing Adapter for Groww Trading API.
Integrates live WebSocket market feeds, order execution, and account management.
"""

import os
import logging
from typing import Dict, List, Optional, Any

try:
    from growwapi import GrowwAPI, GrowwFeed
except ImportError:
    GrowwAPI = None
    GrowwFeed = None

logger = logging.getLogger(__name__)

def _load_env_file(filepath: str = ".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("\"'")

_load_env_file()

class GrowwAdapter:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        _load_env_file()
        self.api_key = api_key or os.getenv("GROWW_API_KEY")
        self.api_secret = api_secret or os.getenv("GROWW_API_SECRET")
        self.client: Optional[GrowwAPI] = None
        self.feed: Optional[GrowwFeed] = None
        self.access_token: Optional[str] = None

    def connect(self) -> bool:
        if not self.api_key or not self.api_secret:
            logger.error("GrowwAdapter: GROWW_API_KEY or GROWW_API_SECRET missing.")
            return False

        try:
            self.access_token = GrowwAPI.get_access_token(api_key=self.api_key, secret=self.api_secret)
            self.client = GrowwAPI(self.access_token)
            logger.info("GrowwAdapter: Authenticated successfully with Groww Live API!")
            return True
        except Exception as e:
            logger.error(f"GrowwAdapter: Authentication failed: {e}")
            return False

    def init_feed(self) -> Optional[GrowwFeed]:
        if not self.client:
            if not self.connect():
                return None
        try:
            self.feed = GrowwFeed(self.client)
            return self.feed
        except Exception as e:
            logger.error(f"GrowwAdapter: Feed initialization failed: {e}")
            return None

    def get_profile(self) -> Optional[dict]:
        if not self.client and not self.connect():
            return None
        try:
            return self.client.get_user_profile()
        except Exception as e:
            logger.error(f"Profile error: {e}")
            return None

    def get_holdings(self) -> Optional[dict]:
        if not self.client and not self.connect():
            return None
        try:
            return self.client.get_holdings_for_user()
        except Exception as e:
            logger.error(f"Holdings error: {e}")
            return None

    def get_positions(self) -> Optional[dict]:
        if not self.client and not self.connect():
            return None
        try:
            return self.client.get_positions_for_user()
        except Exception as e:
            logger.error(f"Positions error: {e}")
            return None

    def get_orders(self) -> Optional[dict]:
        if not self.client and not self.connect():
            return None
        try:
            return self.client.get_order_list()
        except Exception as e:
            logger.error(f"Orders error: {e}")
            return None

    def place_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        price: float,
        order_type: str = "LIMIT",
        exchange: str = "NSE",
        segment: str = "CASH"
    ) -> Optional[dict]:
        if not self.client and not self.connect():
            return None
        try:
            return self.client.place_order(
                trading_symbol=symbol,
                quantity=quantity,
                exchange=self.client.EXCHANGE_NSE if exchange == "NSE" else self.client.EXCHANGE_BSE,
                segment=self.client.SEGMENT_CASH if segment == "CASH" else self.client.SEGMENT_FNO,
                product=self.client.PRODUCT_CNC if segment == "CASH" else self.client.PRODUCT_NRML,
                order_type=self.client.ORDER_TYPE_LIMIT if order_type == "LIMIT" else self.client.ORDER_TYPE_MARKET,
                transaction_type=self.client.TRANSACTION_TYPE_BUY if side.upper() == "BUY" else self.client.TRANSACTION_TYPE_SELL,
                price=price
            )
        except Exception as e:
            logger.error(f"Order placement failed for {symbol}: {e}")
            return None
