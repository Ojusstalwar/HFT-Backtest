"""
HFT Backtesting Engine — module selection.

Selects Cython-accelerated implementations when available,
falls back to pure Python. Set HFT_DEBUG=1 to force pure Python
for pdb-friendly debugging.
"""

import os

if os.environ.get("HFT_DEBUG") == "1":
    from engine.event_queue import EventQueue
    from engine.order_book import OrderBook
    from engine.matching_engine import MatchingEngine
    from engine.latency_model import LatencyModel
else:
    try:
        from engine.event_queue_cy import EventQueue  # type: ignore
        from engine.order_book_cy import OrderBook  # type: ignore
        from engine.matching_engine_cy import MatchingEngine  # type: ignore
        from engine.latency_model_cy import LatencyModel  # type: ignore
    except ImportError:
        from engine.event_queue import EventQueue
        from engine.order_book import OrderBook
        from engine.matching_engine import MatchingEngine
        from engine.latency_model import LatencyModel
