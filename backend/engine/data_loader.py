from __future__ import annotations

import logging
import csv
from typing import List

from engine.types import Event, EventType, Side
from engine.corporate_actions import CorporateActionManager

logger = logging.getLogger(__name__)

class DataLoader:
    """
    Multi-format data ingestion for the HFT backtester.
    """
    def __init__(self) -> None:
        pass

    def load_tick_data(self, path: str, format: str = 'csv') -> List[Event]:
        """
        Load tick data.
        Expected format: timestamp_ns, symbol, price, size, side
        """
        events = []
        if format == 'csv':
            try:
                with open(path, mode='r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        event = Event(
                            timestamp_ns=int(row['timestamp_ns']),
                            event_type=EventType.TICK,
                            symbol=row['symbol'],
                            price=float(row['price']),
                            size=int(row['size']),
                            side=Side[row['side'].upper()]
                        )
                        events.append(event)
            except Exception as e:
                logger.error(f"Failed to load tick data from {path}: {e}")
        else:
            raise NotImplementedError(f"Format {format} not supported.")
            
        return sorted(events, key=lambda x: x.timestamp_ns)

    def load_l2_data(self, path: str, format: str = 'csv') -> List[Event]:
        """
        Load L2 snapshots.
        """
        events = []
        if format == 'csv':
            try:
                with open(path, mode='r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Assuming simple format for L2 for this implementation
                        event = Event(
                            timestamp_ns=int(row['timestamp_ns']),
                            event_type=EventType.L2_SNAPSHOT,
                            symbol=row['symbol'],
                            bid_prices=[float(x) for x in row['bid_prices'].split('|')],
                            bid_sizes=[int(x) for x in row['bid_sizes'].split('|')],
                            ask_prices=[float(x) for x in row['ask_prices'].split('|')],
                            ask_sizes=[int(x) for x in row['ask_sizes'].split('|')]
                        )
                        events.append(event)
            except Exception as e:
                logger.error(f"Failed to load L2 data from {path}: {e}")
        else:
            raise NotImplementedError(f"Format {format} not supported.")
            
        return sorted(events, key=lambda x: x.timestamp_ns)

    def load_ohlcv_data(self, path: str, format: str = 'csv') -> List[Event]:
        """
        Load OHLCV candles and convert to synthetic ticks.
        """
        events = []
        if format == 'csv':
            try:
                with open(path, mode='r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ts = int(row['timestamp_ns'])
                        sym = row['symbol']
                        open_p = float(row['open'])
                        high_p = float(row['high'])
                        low_p = float(row['low'])
                        close_p = float(row['close'])
                        vol = int(row['volume'])
                        
                        # Generate synthetic ticks (Open, High, Low, Close)
                        tick_vol = vol // 4
                        
                        events.append(Event(timestamp_ns=ts, event_type=EventType.TICK, symbol=sym, price=open_p, size=tick_vol, side=Side.BUY))
                        events.append(Event(timestamp_ns=ts+1, event_type=EventType.TICK, symbol=sym, price=high_p, size=tick_vol, side=Side.BUY))
                        events.append(Event(timestamp_ns=ts+2, event_type=EventType.TICK, symbol=sym, price=low_p, size=tick_vol, side=Side.SELL))
                        events.append(Event(timestamp_ns=ts+3, event_type=EventType.TICK, symbol=sym, price=close_p, size=tick_vol, side=Side.SELL))
            except Exception as e:
                logger.error(f"Failed to load OHLCV data from {path}: {e}")
        else:
            raise NotImplementedError(f"Format {format} not supported.")
            
        return sorted(events, key=lambda x: x.timestamp_ns)

    def apply_corporate_actions(self, events: List[Event], ca_manager: CorporateActionManager) -> List[Event]:
        """Apply corporate actions to events."""
        adjusted_events = []
        for event in events:
            # Assuming we can extract a date string from timestamp_ns for CA lookup
            # This is a simplification; in reality, you'd convert timestamp_ns to YYYY-MM-DD
            # For this backtester, we will mock the date extraction.
            import datetime
            date_str = datetime.datetime.fromtimestamp(event.timestamp_ns / 1e9).strftime('%Y-%m-%d')
            
            new_sym = ca_manager.get_new_symbol(event.symbol, date_str)
            if new_sym != event.symbol:
                event.symbol = new_sym
                
            if hasattr(event, 'price') and event.price is not None:
                event.price = ca_manager.adjust_price(event.price, event.symbol, date_str)
            if hasattr(event, 'size') and event.size is not None:
                event.size = ca_manager.adjust_quantity(event.size, event.symbol, date_str)
                
            adjusted_events.append(event)
        return adjusted_events

    def validate_timestamps(self, events: List[Event]) -> None:
        """Warn on non-monotonic timestamps and gaps."""
        if not events:
            return
            
        prev_ts = events[0].timestamp_ns
        for event in events[1:]:
            if event.timestamp_ns < prev_ts:
                logger.warning(f"Non-monotonic timestamp detected: {prev_ts} -> {event.timestamp_ns}")
            elif event.timestamp_ns - prev_ts > 1_000_000_000 * 3600: # 1 hour gap warning
                logger.warning(f"Large timestamp gap detected: {event.timestamp_ns - prev_ts} ns")
            prev_ts = event.timestamp_ns
