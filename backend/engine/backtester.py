from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.types import Event, EventType, Fill, Order, Side
from engine.config import BacktestConfig
from analytics.metrics import MetricsCalculator
from analytics.markout import MarkoutAnalyzer
from analytics.report import ReportGenerator

logger = logging.getLogger(__name__)

# Assume these imports exist as stated in the prompt
from engine.event_queue import EventQueue
from engine.order_book import OrderBook
from engine.matching_engine import MatchingEngine
from engine.latency_model import LatencyModel
from engine.oms import OMS
from engine.risk_manager import RiskManager
from engine.portfolio import Portfolio
from engine.fees import FeeCalculator
from engine.auction import AuctionManager
from engine.price_bands import PriceBandManager

# Optional F&O modules
try:
    from engine.margin_engine import MarginEngine
except ImportError:
    MarginEngine = None
try:
    from engine.greeks import GreeksCalculator
except ImportError:
    GreeksCalculator = None
try:
    from engine.corporate_actions import SettlementManager
except ImportError:
    SettlementManager = None
try:
    from engine.corporate_actions import RolloverManager
except ImportError:
    RolloverManager = None


@dataclass
class BacktestResult:
    metrics: dict[str, Any]
    markout: dict[str, dict[int, float]]
    equity_curve: list[tuple[int, float]]
    trades: list[Fill]
    report: dict[str, Any]


class Backtester:
    """
    Main orchestrator that wires the HFT framework together.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        
        self.event_queue = EventQueue()
        self.order_books = {sym: OrderBook(sym) for sym in config.symbols}
        self.matching_engine = MatchingEngine(config.fill_model)
        self.latency_model = LatencyModel(config.latency)
        
        self.risk_manager = RiskManager(
            max_position=config.max_position_limit,
            max_drawdown_pct=config.max_drawdown_pct,
            max_order_rate=config.max_order_rate_per_sec
        )
        self.portfolio = Portfolio(initial_capital=config.initial_capital)
        self.oms = OMS()
        self.fee_calculator = FeeCalculator(config.fees)
        self.auction_manager = AuctionManager()
        self.price_band_manager = PriceBandManager()
        
        # Determine if F&O is present
        self.has_fno = False
        for sym in config.symbols:
            if sym.endswith("-FUT") or "-CE" in sym or "-PE" in sym:
                self.has_fno = True
                break
                
        self.margin_engine = None
        self.greeks_calc = None
        self.settlement_manager = None
        self.rollover_manager = None
        
        if self.has_fno:
            if MarginEngine:
                self.margin_engine = MarginEngine()
            if GreeksCalculator and config.greeks:
                self.greeks_calc = GreeksCalculator(config.greeks)
            if SettlementManager:
                self.settlement_manager = SettlementManager()
            if RolloverManager:
                self.rollover_manager = RolloverManager()
                
        self.equity_curve: list[tuple[int, float]] = []
        self.trades: list[Fill] = []
        self.mid_price_series: list[tuple[int, float]] = []

    def run(self, strategy: Any, data_events: list[Event]) -> BacktestResult:
        """
        Runs the backtest event loop.
        """
        # Load all data events
        for ev in data_events:
            self.event_queue.push(ev)
            
        # Wire strategy callbacks
        def _place_order(order: Order):
            try:
                self.risk_manager.check_order(order, self.portfolio)
            except Exception as e:
                logger.warning(f"Risk check failed: {e}")
                return
                
            self.oms.register_order(order)
            latency_ns = self.latency_model.get_order_ingress_latency()
            
            # Send to matching engine with latency
            ev = Event(
                timestamp_ns=self.event_queue.current_time + latency_ns,
                sequence_number=self.event_queue.next_seq(),
                type_priority=EventType.ORDER_ACK.value,
                event_type=EventType.ORDER_ACK,
                symbol=order.symbol,
                data={'order': order}
            )
            self.event_queue.push(ev)
            
        def _cancel_order(order_id: str):
            order = self.oms.get_order(order_id)
            if not order:
                return
                
            latency_ns = self.latency_model.get_order_ingress_latency()
            ev = Event(
                timestamp_ns=self.event_queue.current_time + latency_ns,
                sequence_number=self.event_queue.next_seq(),
                type_priority=EventType.CANCEL_ACK.value,
                event_type=EventType.CANCEL_ACK,
                symbol=order.symbol,
                data={'order_id': order_id}
            )
            self.event_queue.push(ev)
            
        strategy.set_order_callback(_place_order)
        strategy.set_cancel_callback(_cancel_order)
        
        if hasattr(strategy, 'initialize'):
            strategy.initialize()

        last_equity_snapshot_time = 0
        snapshot_interval_ns = 60_000_000_000  # 1 minute

        # Main Event Loop
        while not self.event_queue.is_empty():
            event = self.event_queue.pop()
            
            # Record equity periodically
            if event.timestamp_ns - last_equity_snapshot_time > snapshot_interval_ns:
                nav = self.portfolio.get_nav()
                self.equity_curve.append((event.timestamp_ns, nav))
                last_equity_snapshot_time = event.timestamp_ns

            match event.event_type:
                case EventType.CIRCUIT_HALT:
                    self.risk_manager.handle_halt(event.symbol)
                    strategy.on_halt(event)
                    
                case EventType.BOOK_UPDATE:
                    book = self.order_books.get(event.symbol)
                    if book:
                        book.update(event.data)
                        mid = book.mid_price
                        if mid is not None:
                            self.mid_price_series.append((event.timestamp_ns, mid))
                    strategy.on_book_update(event)
                    self.matching_engine.process_book_update(event.symbol, event.data)
                    
                case EventType.TRADE:
                    strategy.on_trade(event)
                    
                case EventType.AUCTION:
                    self.auction_manager.process_auction(event.symbol, event.data)
                    self.matching_engine.process_auction(event.symbol, event.data)
                    strategy.on_auction(event)
                    
                case EventType.CANCEL_ACK:
                    order_id = event.data.get('order_id')
                    self.oms.process_cancel_ack(order_id)
                    strategy.on_cancel_ack(event)
                    
                case EventType.FILL:
                    fill: Fill = event.data['fill']
                    fill.fee = self.fee_calculator.calculate(fill)
                    
                    self.portfolio.process_fill(fill)
                    if self.has_fno and self.margin_engine:
                        self.margin_engine.update_margin(self.portfolio)
                        
                    self.trades.append(fill)
                    self.oms.process_fill(fill)
                    strategy.on_fill(event)
                    
                case EventType.ORDER_ACK:
                    order = event.data['order']
                    self.oms.process_order_ack(order.order_id)
                    strategy.on_order_ack(event)
                    
                case EventType.TIMER:
                    strategy.on_timer(event)

        # Final snapshot
        self.equity_curve.append((self.event_queue.current_time, self.portfolio.get_nav()))
        
        # Post-run Analytics
        freq_hz = 1.0 / (snapshot_interval_ns / 1e9)  # E.g., 1/60 Hz
        equity_values = [eq for _, eq in self.equity_curve]
        orders_placed = self.oms.get_total_orders() if hasattr(self.oms, 'get_total_orders') else len(self.trades) * 2
        
        metrics = MetricsCalculator.compute_all(
            equity_curve=equity_values,
            trades=self.trades,
            orders_placed=orders_placed,
            sampling_freq_hz=freq_hz
        )
        
        markout = MarkoutAnalyzer.get_markout_by_side(self.trades, self.mid_price_series)
        
        margin_history = None
        if self.has_fno and self.margin_engine and hasattr(self.margin_engine, 'history'):
            margin_history = self.margin_engine.history
            
        greeks_history = None
        if self.has_fno and self.greeks_calc and hasattr(self.greeks_calc, 'history'):
            greeks_history = self.greeks_calc.history
            
        report = ReportGenerator.generate_report(
            config=self.config,
            metrics=metrics,
            markout=markout,
            equity_curve=self.equity_curve,
            trades=self.trades,
            positions=self.portfolio.positions,
            margin_history=margin_history,
            greeks_history=greeks_history
        )
        
        return BacktestResult(
            metrics=metrics,
            markout=markout,
            equity_curve=self.equity_curve,
            trades=self.trades,
            report=report
        )
