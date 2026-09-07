"""
Run a real backtest simulation with genuine event-driven execution,
FIFO matched trade accounting, normalized markout curves (bps), and proper Sharpe metrics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np

from engine.types import (
    Event, EventType, Side, Order, Fill, OrderType, OrderStatus, 
    InstrumentType, BookSnapshot, PriceLevel, TradeEvent
)
from engine.config import load_config
from engine.event_queue import EventQueue
from engine.order_book import OrderBook
from engine.matching_engine import MatchingEngine
from engine.latency_model import LatencyModel
from engine.oms import OMS
from engine.portfolio import Portfolio
from engine.fees import FeeCalculator
from engine.price_bands import PriceBandManager
from engine.auction import AuctionManager
from strategies.market_maker import MarketMakerStrategy
from analytics.metrics import MetricsCalculator
from analytics.markout import MarkoutAnalyzer
from data.sample_generator import SampleDataGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_simulation():
    # 1. Load configuration
    config_path = Path("config/EXAMPLE_colo_nse.yaml")
    config = load_config(config_path)
    
    # 5 symbols with current market prices
    symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"]
    start_prices = {
        "RELIANCE": 1310.00,
        "TCS": 2361.00,
        "INFY": 1169.20,
        "HDFCBANK": 727.00,
        "SBIN": 1067.70
    }
    volatilities = {
        "RELIANCE": 0.014,
        "TCS": 0.012,
        "INFY": 0.015,
        "HDFCBANK": 0.013,
        "SBIN": 0.016
    }
    
    config.symbols = symbols
    config.start_date = "2024-08-15"
    config.end_date = "2024-08-15"
    
    # 2. Initialize Engine Components
    event_queue = EventQueue()
    order_books = {sym: OrderBook(sym) for sym in symbols}
    price_band_mgr = PriceBandManager()
    auction_mgr = AuctionManager()
    matching_engine = MatchingEngine(config.fill_model, price_band_mgr, auction_mgr)
    latency_model = LatencyModel(config.latency, seed=42)
    oms = OMS()
    portfolio = Portfolio(initial_capital=config.initial_capital)
    fee_calc = FeeCalculator(config.fees)
    
    # Set price bands (5% daily band per symbol)
    for sym, px in start_prices.items():
        price_band_mgr.set_band(sym, px, 0.05)
        
    # 3. Generate Interleaved High-Frequency L2 Snapshots & Trade Events
    generator = SampleDataGenerator(seed=123)
    logger.info("Generating realistic L2 market data and public trades for 5 symbols...")
    raw_events: list[Event] = []
    
    for sym in symbols:
        l2_events = generator.generate_l2_data(sym, num_snapshots=800, start_price=start_prices[sym])
        trade_events = generator.generate_tick_data(sym, num_ticks=1500, start_price=start_prices[sym], volatility=volatilities[sym])
        raw_events.extend(l2_events)
        raw_events.extend(trade_events)
        
    # Sort all market events into min-heap event queue
    raw_events.sort(key=lambda e: e.timestamp_ns)
    seq = 0
    for ev in raw_events:
        seq += 1
        event_queue.push(Event(
            timestamp_ns=ev.timestamp_ns,
            sequence_number=seq,
            type_priority=ev.type_priority,
            event_type=ev.event_type,
            symbol=ev.symbol,
            data=ev.data
        ))
        
    # 4. Strategy Setup
    strategy = MarketMakerStrategy(
        name="AvellanedaStoikov_MM",
        symbols=symbols,
        spread_bps=10.0,
        inventory_risk_aversion=0.08,
        max_position=150,
        order_size=10
    )
    
    current_sim_time = 0
    
    def strategy_order_cb(order: Order):
        oms.submit_order(order)
        latency_ns = latency_model.sample_order_ingress_latency()
        nonlocal seq
        seq += 1
        event_queue.push(Event(
            timestamp_ns=current_sim_time + latency_ns,
            sequence_number=seq,
            type_priority=EventType.ORDER_ACK.value,
            event_type=EventType.ORDER_ACK,
            symbol=order.symbol,
            data={"order": order}
        ))
        
    def strategy_cancel_cb(order_id: str):
        try:
            oms.request_cancel(order_id)
        except Exception:
            return
        latency_ns = latency_model.sample_order_ingress_latency()
        nonlocal seq
        seq += 1
        event_queue.push(Event(
            timestamp_ns=current_sim_time + latency_ns,
            sequence_number=seq,
            type_priority=EventType.CANCEL_ACK.value,
            event_type=EventType.CANCEL_ACK,
            symbol="",
            data={"order_id": order_id}
        ))
        
    strategy._order_callback = strategy_order_cb
    strategy._cancel_callback = strategy_cancel_cb
    
    # 5. Main Simulation Loop
    logger.info("Executing simulation loop across 5 symbols...")
    equity_curve: list[tuple[int, float]] = []
    mid_price_series: list[tuple[int, float]] = []
    executed_fills: list[Fill] = []
    
    last_equity_snapshot_ns = 0
    snapshot_interval_ns = 30_000_000_000  # Record equity every 30 seconds
    
    while event_queue.has_events():
        event = event_queue.pop()
        current_sim_time = event.timestamp_ns
        
        # Periodic equity recording
        if current_sim_time - last_equity_snapshot_ns >= snapshot_interval_ns:
            price_map = {}
            for sym, book in order_books.items():
                if book.mid_price is not None:
                    price_map[sym] = book.mid_price
            if price_map:
                portfolio.mark_to_market_all(price_map)
                
            equity_curve.append((current_sim_time, portfolio.get_equity()))
            last_equity_snapshot_ns = current_sim_time
            
        match event.event_type:
            case EventType.BOOK_UPDATE:
                book = order_books[event.symbol]
                book.update(event)
                mid = book.mid_price
                if mid is not None:
                    mid_price_series.append((event.timestamp_ns, mid))
                strategy.on_book_update(book.get_snapshot(), event.timestamp_ns)
                
            case EventType.ORDER_ACK:
                order = event.data["order"]
                ack_events = matching_engine.submit_order(order, event.timestamp_ns)
                for ack_ev in ack_events:
                    oms.handle_ack(ack_ev)
                    strategy.on_order_update(order)
                    
            case EventType.CANCEL_ACK:
                order_id = event.data["order_id"]
                cancel_ev = matching_engine.cancel_order(order_id, event.timestamp_ns)
                oms.handle_cancel_ack(cancel_ev)
                order = oms.get_order(order_id)
                if order:
                    strategy.on_order_update(order)
                    
            case EventType.TRADE:
                trade_data = event.data
                trade = TradeEvent(
                    symbol=event.symbol,
                    timestamp_ns=event.timestamp_ns,
                    price=trade_data["price"],
                    size=trade_data["size"],
                    side=trade_data["side"]
                )
                strategy.on_trade(trade)
                
                fill_events = matching_engine.process_trade(trade)
                for f_ev in fill_events:
                    fill: Fill = f_ev.data["fill"]
                    fill.fee = fee_calc.calculate_trade_fees(fill)
                    
                    portfolio.process_fill(fill, fee_calc)
                    oms.handle_fill(fill)
                    
                    executed_fills.append(fill)
                    strategy.on_fill(fill)
                    
                    order = oms.get_order(fill.order_id)
                    if order:
                        strategy.on_order_update(order)
                        
    # Final equity snapshot
    price_map = {sym: book.mid_price for sym, book in order_books.items() if book.mid_price is not None}
    if price_map:
        portfolio.mark_to_market_all(price_map)
    equity_curve.append((current_sim_time, portfolio.get_equity()))
    
    # 6. Post-Run Analytics
    logger.info("Computing metrics from executed fills and mark-to-market equity curve...")
    freq_hz = 1.0 / (snapshot_interval_ns / 1e9)  # 1/30 Hz
    equity_values = [eq for _, eq in equity_curve]
    orders_placed = len(oms.get_all_orders())
    
    metrics = MetricsCalculator.compute_all(
        equity_curve=equity_values,
        trades=executed_fills,
        orders_placed=orders_placed,
        sampling_freq_hz=freq_hz
    )
    
    round_trips = MetricsCalculator._get_round_trips(executed_fills)
    total_realized_pnl = sum(t['pnl'] for t in round_trips)
    gross_profit = sum(t['pnl'] for t in round_trips if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in round_trips if t['pnl'] < 0))
    total_rt = len(round_trips)
    
    metrics["total_pnl"] = round(portfolio.get_total_pnl() - portfolio._fees, 2)
    metrics["total_fees"] = round(portfolio._fees, 2)
    metrics["daily_sharpe"] = round(metrics["daily_sharpe"], 2)
    metrics["session_sharpe"] = round(metrics["session_sharpe"], 2)
    metrics["sharpe_ratio"] = round(metrics["daily_sharpe"], 2)  # Report Daily Session Sharpe
    metrics["sortino_ratio"] = round(metrics["sortino_ratio"], 2)
    metrics["max_drawdown_pct"] = round(metrics["max_drawdown_pct"] * 100, 2)
    metrics["profit_factor"] = round(metrics["profit_factor"], 2)
    metrics["win_rate"] = round(metrics["win_rate"] * 100, 1)
    metrics["pnl_per_trade"] = round(metrics["pnl_per_trade"], 2)
    metrics["avg_trade_duration_s"] = round(metrics["avg_trade_duration_s"], 1)
    metrics["fill_ratio"] = round(metrics["fill_ratio"], 2)
    metrics["quote_to_trade_ratio"] = round(metrics["quote_to_trade_ratio"], 1)
    metrics["total_trades"] = total_rt
    
    # Markout analysis in basis points (bps)
    avg_markout = MarkoutAnalyzer.compute_markout(executed_fills, mid_price_series)
    markout_dict = {str(int(k / 1e6)): round(v, 2) for k, v in avg_markout.items()}
    
    # Transform equity curve to ms timestamps for dashboard
    dashboard_equity_curve = [[int(ts / 1e6), round(eq, 2)] for ts, eq in equity_curve]
    
    # Transform fills to dashboard trade format
    dashboard_trades = []
    for fill in executed_fills:
        dashboard_trades.append({
            "timestamp_ms": int(fill.timestamp_ns / 1e6),
            "symbol": fill.symbol,
            "side": fill.side.name,
            "price": round(fill.price, 2),
            "size": fill.size,
            "pnl": 0.0,
            "fee": round(fill.fee, 2),
            "is_maker": fill.is_maker
        })
        
    # Build complete Report payload
    report = {
        "metadata": {
            "framework": "HFT Backtester v0.1.0",
            "strategy": "MarketMakerStrategy (Avellaneda-Stoikov)",
            "symbols": symbols,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_capital": config.initial_capital,
            "engine": "Discrete Event Queue (FIFO Queue Matching)",
            "markout_units": "basis points (bps)",
            "sharpe_basis": "Daily Session Sharpe"
        },
        "traceability": {
            "calibration_source": config.latency.calibration_source,
            "fill_discount_source": config.fill_model.fill_discount_source,
            "rate_source": "RBI repo rate as configured"
        },
        "metrics": metrics,
        "markout": markout_dict,
        "equity_curve": dashboard_equity_curve,
        "trades": dashboard_trades,
        "positions": {
            sym: {
                "symbol": pos.symbol,
                "size": pos.size,
                "avg_price": round(pos.avg_entry_price, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2)
            }
            for sym, pos in portfolio.get_all_positions().items()
        }
    }
    
    output_file = Path("results/backtest_report.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Report saved to {output_file}")
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Simulated Fills: {len(executed_fills)}, Matched Round-Trips: {total_rt}")
    logger.info(f"Gross Profit: INR {gross_profit:,.2f}, Gross Loss: INR {gross_loss:,.2f}")
    logger.info(f"Profit Factor: {metrics['profit_factor']}, Total PnL: INR {metrics['total_pnl']:,.2f}")
    logger.info(f"Daily Session Sharpe: {metrics['daily_sharpe']}, Max DD: {metrics['max_drawdown_pct']}%")
    logger.info(f"Markout (bps): {markout_dict}")

if __name__ == "__main__":
    run_simulation()
