# HFT Backtester for Indian Markets

A professional-grade High-Frequency Trading (HFT) backtesting framework specifically designed for Indian markets (NSE/BSE — Equities & F&O). This framework focuses on microstructural fidelity, deterministic event-loop processing, and comprehensive exchange fee/margin modeling.

## Project Overview and Architecture

The backtester operates on a purely deterministic, min-heap-based event loop. It simulates the exchange matching engine, latency distributions, order management systems, and risk controls.

```
+-----------------------------------------------------------------+
|                         BACKTESTER CORE                         |
|                                                                 |
|  +----------------+    +----------------+    +---------------+  |
|  |                |    |                |    |               |  |
|  |  Data Loader   +--->|  Event Queue   +--->|  Strategies   |  |
|  | (L2/L3 PCAP)   |    |  (Min-Heap)    |    |               |  |
|  +----------------+    +-------+--------+    +-------+-------+  |
|                                |                     |          |
|                                v                     v          |
|  +----------------+    +----------------+    +---------------+  |
|  |                |    |                |    |               |  |
|  |   Risk & OMS   |<---+ Matching Engine|<---+ Latency Model |  |
|  |                |    |                |    |               |  |
|  +----------------+    +-------+--------+    +---------------+  |
|                                |                                |
|                                v                                |
|  +----------------+    +----------------+                       |
|  |                |    |                |                       |
|  | Fee & Margin   |<---+   Analytics    |                       |
|  |                |    |                |                       |
|  +----------------+    +----------------+                       |
+-----------------------------------------------------------------+
```

## Quick Start

### 1. Install
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
python setup.py develop
```

### 2. Configure
Create a config file or use the dataclasses in `engine/config.py`. Ensure that `calibration_source`, `fill_discount_source`, and `rate_source` are defined.

### 3. Run
Execute a backtest via the command line (assuming a runner script is implemented):
```bash
python run_backtest.py --config config.yaml --strategy my_strat
```

## Configuration Guide

The engine relies heavily on dataclass configurations found in `engine/config.py`:
- **Latency (`LatencyModelConfig`):** Define base latencies, jitter, and geographic profiles. See [Latency Calibration](docs/latency_calibration.md) for details.
- **Fill Model (`FillModelConfig`):** Control queue tracking and fill probabilities.
- **Fees (`FeeConfig`):** STT, Transaction Charges, Stamp Duty, SEBI fees, and GST rates.
- **Greeks:** Implied volatility surfaces and pricing parameters for options.

## Strategy Development Guide

To write a custom strategy, inherit from the base strategy class (when fully implemented in `strategies/`) and implement the event handlers:
- `on_book_update(self, event)`
- `on_trade(self, event)`
- `on_order_ack(self, event)`
- `on_fill(self, event)`

Submit orders via the strategy's internal OMS reference: `self.oms.submit_order(Order(...))`.

## Dashboard Usage

The framework includes an analytics dashboard module (`dashboard/`). Run it to visualize PnL, drawdowns, latency metrics, and queue position heatmaps.

## Testing

The project uses `pytest` for all unit and integration tests. Run the full test suite:
```bash
pytest tests/
```
Key areas tested include determinism (`test_determinism.py`), fee accuracy, OMS state transitions, and margin calculations.

## Known Limitations Reference

Please refer to the [Known Limitations](docs/known_limitations.md) document for a comprehensive overview of the simulator's boundaries, including L2 queue approximation and SPAN margin simplifications.
