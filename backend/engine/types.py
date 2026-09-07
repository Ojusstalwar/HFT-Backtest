"""
Shared types, enums, and data structures for the HFT backtesting framework.

This is the canonical source of truth for all type definitions. Every module
imports from here — no module defines its own event types, order statuses, etc.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Event Types — canonical enum, used by event_queue, backtester, and all modules
# ---------------------------------------------------------------------------

class EventType(enum.IntEnum):
    """
    Canonical event types processed by the backtester event loop.
    The integer values double as tie-breaking priority (lower = higher priority).
    """
    CIRCUIT_HALT = 0   # Market-wide or per-symbol circuit halt
    BOOK_UPDATE  = 1   # L2 depth update
    TRADE        = 2   # Trade print / last-traded-price update
    AUCTION      = 3   # Pre-open / call-auction uncrossing event
    CANCEL_ACK   = 4   # Exchange acknowledges cancellation
    FILL         = 5   # Partial or full fill notification
    ORDER_ACK    = 6   # Exchange acknowledges order placement
    TIMER        = 7   # Strategy-scheduled timer callback


# ---------------------------------------------------------------------------
# Order / Trade Enums
# ---------------------------------------------------------------------------

class Side(enum.IntEnum):
    BUY  = 1
    SELL = -1


class OrderType(enum.Enum):
    LIMIT  = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(enum.Enum):
    """
    Order lifecycle states. Transitions enforced by OMS.

    PENDING_NEW  →  NEW  →  PARTIALLY_FILLED  →  FILLED
                         →  PENDING_CANCEL     →  CANCELLED
                                               →  CANCEL_REJECTED (TOO_LATE)
                 →  REJECTED
    """
    PENDING_NEW      = "PENDING_NEW"
    NEW              = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED           = "FILLED"
    PENDING_CANCEL   = "PENDING_CANCEL"
    CANCELLED        = "CANCELLED"
    CANCEL_REJECTED  = "CANCEL_REJECTED"
    REJECTED         = "REJECTED"


class InstrumentType(enum.Enum):
    EQ  = "EQ"    # Equity (cash segment)
    FUT = "FUT"   # Futures
    CE  = "CE"    # Call option (European)
    PE  = "PE"    # Put option (European)


class SessionType(enum.Enum):
    PRE_OPEN_ORDER_ENTRY   = "PRE_OPEN_ORDER_ENTRY"    # 9:00 – 9:08
    PRE_OPEN_MATCHING      = "PRE_OPEN_MATCHING"        # 9:08 – 9:12
    PRE_OPEN_BUFFER        = "PRE_OPEN_BUFFER"          # 9:12 – 9:15
    CONTINUOUS             = "CONTINUOUS"                 # 9:15 – 15:30
    POST_CLOSE_AUCTION     = "POST_CLOSE_AUCTION"        # 15:40 – 16:00
    CLOSED                 = "CLOSED"


class QueueCancellationModel(enum.Enum):
    PESSIMISTIC  = "pessimistic"   # Cancels assumed behind your order
    PROPORTIONAL = "proportional"  # Cancels uniformly distributed
    POWER_LAW    = "power_law"     # Calibrated power-law bias


# ---------------------------------------------------------------------------
# Core Data Structures
# ---------------------------------------------------------------------------

@dataclass(slots=True, order=True)
class Event:
    """
    A single event in the simulation. Ordered by the 3-tuple:
    (timestamp_ns, sequence_number, type_priority)
    """
    timestamp_ns: int                  # Nanosecond timestamp
    sequence_number: int               # Monotonic counter for stable ordering
    type_priority: int                 # EventType.value (lower = higher priority)
    event_type: EventType = field(compare=False)
    symbol: str = field(default="", compare=False)
    data: dict = field(default_factory=dict, compare=False)


@dataclass(slots=True)
class Order:
    """Represents an order submitted by a strategy."""
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    price: float                       # 0.0 for market orders
    size: int                          # Quantity in lots (F&O) or shares (EQ)
    remaining_size: int = 0
    status: OrderStatus = OrderStatus.PENDING_NEW
    timestamp_ns: int = 0              # Submission time
    fill_price_avg: float = 0.0        # Volume-weighted average fill price
    filled_size: int = 0
    instrument_type: InstrumentType = InstrumentType.EQ
    # Queue position tracking (matching engine internal)
    queue_ahead: int = 0


@dataclass(slots=True)
class Fill:
    """Represents a fill (partial or complete) of an order."""
    order_id: str
    symbol: str
    side: Side
    price: float
    size: int
    timestamp_ns: int
    is_maker: bool                     # True = passive fill, False = aggressive
    instrument_type: InstrumentType = InstrumentType.EQ
    fee: float = 0.0


@dataclass(slots=True)
class PriceLevel:
    """A single price level in the order book."""
    price: float
    size: int
    order_count: int = 0


@dataclass(slots=True)
class BookSnapshot:
    """Snapshot of the order book at a point in time."""
    symbol: str
    timestamp_ns: int
    bids: list[PriceLevel]            # Sorted best (highest) first
    asks: list[PriceLevel]            # Sorted best (lowest) first

    @property
    def best_bid(self) -> PriceLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> PriceLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2.0
        return None

    @property
    def spread(self) -> float | None:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def micro_price(self) -> float | None:
        """Volume-weighted mid price biased toward the heavier side."""
        if self.best_bid and self.best_ask:
            vb = self.best_bid.size
            va = self.best_ask.size
            total = vb + va
            if total == 0:
                return self.mid_price
            return (
                self.best_ask.price * vb / total
                + self.best_bid.price * va / total
            )
        return None

    @property
    def order_book_imbalance(self) -> float | None:
        """OBI = (V_bid - V_ask) / (V_bid + V_ask). Range [-1, 1]."""
        if self.best_bid and self.best_ask:
            vb = self.best_bid.size
            va = self.best_ask.size
            total = vb + va
            if total == 0:
                return 0.0
            return (vb - va) / total
        return None


@dataclass(slots=True)
class TradeEvent:
    """A trade print from market data."""
    symbol: str
    timestamp_ns: int
    price: float
    size: int
    side: Side                         # Aggressor side


@dataclass(slots=True)
class ContractSpec:
    """F&O contract specification."""
    symbol: str
    instrument_type: InstrumentType
    lot_size: int
    tick_size: float
    expiry_date: str | None = None     # ISO date string e.g. "2026-08-28"
    strike_price: float | None = None
    underlying: str | None = None


@dataclass(slots=True)
class Greeks:
    """Options Greeks for a single contract."""
    iv: float           # Implied volatility
    delta: float
    gamma: float
    theta: float
    vega: float
    underlying_price: float
    timestamp_ns: int


@dataclass(slots=True)
class Position:
    """Tracks a position in a single instrument."""
    symbol: str
    instrument_type: InstrumentType
    size: int = 0                      # Positive = long, negative = short
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    contract_spec: ContractSpec | None = None


@dataclass(slots=True)
class PriceBand:
    """Daily price band for a symbol."""
    symbol: str
    lower: float
    upper: float
    band_pct: float                    # e.g. 0.05 for 5%
    reference_price: float             # Previous close


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class PairDiscoveryViolationError(Exception):
    """
    Raised when discover_pairs() is called during the out-of-sample test phase.
    Pair selection must be restricted to the training window to prevent
    data snooping.
    """
    pass


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class RiskLimitBreached(Exception):
    """Raised when a pre-trade risk check fails."""
    pass


class CircuitHaltError(Exception):
    """Raised when an operation is attempted on a halted symbol."""
    pass
