// Server-side data provider.
// Currently reads from bundled JSON snapshots.
// To make data truly live, replace the static reads with Groww API calls
// or a scheduled re-computation that writes fresh JSON.

import dispersionReport from "../data/dispersion_report.json";
import backtestReport from "../data/backtest_report.json";

export interface DeskSnapshot {
  timestamp: string;
  dispersion: {
    heroStats: Array<{
      label: string;
      value: string;
      delta: string;
      dir: "up" | "down";
      note: string;
    }>;
    correlationSeries: Array<{
      day: string;
      implied: number;
      realized: number;
      spread: number;
    }>;
  };
  gamma: {
    positive: boolean;
    flipStrike: string;
    netGex: string;
    winRate: number;
    wins: number;
    sessions: number;
    profile: Array<{ strike: string; gamma: number }>;
  };
  basket: Array<{
    symbol: string;
    weight: number;
    spot: number;
    iv: number;
    vega: number;
    sizing: number;
    lots: number;
  }>;
  execution: {
    grossProfit: string;
    grossLoss: string;
    profitFactor: string;
    sharpe: string;
    sortino: string;
    fills: number;
    orders: number;
    fillRatio: number;
    duration: string;
    markouts: Array<{ horizon: string; bps: number }>;
    equityCurve: Array<{ time: string; equity: number }>;
  };
  connectivity: {
    ucc: string;
    segments: Array<{ name: string; state: string }>;
    routing: string;
    ipValidated: boolean;
    feed: string;
    heartbeatMs: number;
  };
}

export function buildSnapshot(): DeskSnapshot {
  const d = dispersionReport as any;
  const b = backtestReport as any;

  const ts = d.time_series || {};
  const dates: string[] = ts.dates || [];
  const impliedCorr: number[] = ts.implied_correlation || [];
  const realizedCorr: number[] = ts.realized_correlation || [];

  const correlationSeries = dates.map((day: string, i: number) => ({
    day,
    implied: Number((impliedCorr[i] ?? 0).toFixed(3)),
    realized: Number((realizedCorr[i] ?? 0).toFixed(3)),
    spread: Number(((impliedCorr[i] ?? 0) - (realizedCorr[i] ?? 0)).toFixed(3)),
  }));

  const summary = d.summary || {};
  const avgImplied = summary.avg_implied_correlation ?? 0.514;
  const avgRealized = summary.avg_realized_correlation ?? 0.024;
  const spread = avgImplied - avgRealized;
  const filteredPnl = summary.total_pnl_gex_filtered ?? 8.160;
  const rawPnl = summary.total_pnl_unfiltered ?? 8.090;

  const heroStats = [
    {
      label: "Implied Correlation",
      value: String(Number(avgImplied).toFixed(3)),
      delta: spread > 0 ? "+" + spread.toFixed(3) : spread.toFixed(3),
      dir: "up" as const,
      note: "Market-priced",
    },
    {
      label: "Realized Correlation",
      value: String(Number(avgRealized).toFixed(3)),
      delta: "-0.008",
      dir: "down" as const,
      note: "Actual 60d",
    },
    {
      label: "Spread Premium",
      value: (spread >= 0 ? "+" : "") + spread.toFixed(3),
      delta: (spread >= 0 ? "+" : "") + spread.toFixed(3),
      dir: spread >= 0 ? "up" as const : "down" as const,
      note: "Edge captured",
    },
    {
      label: "Filtered P&L",
      value: (filteredPnl >= 0 ? "+" : "") + Number(filteredPnl).toFixed(3),
      delta: (filteredPnl - rawPnl) >= 0
        ? "+" + (filteredPnl - rawPnl).toFixed(3)
        : (filteredPnl - rawPnl).toFixed(3),
      dir: filteredPnl >= 0 ? "up" as const : "down" as const,
      note: "Raw " + (rawPnl >= 0 ? "+" : "") + Number(rawPnl).toFixed(3),
    },
  ];

  const gex = d.gex_analysis || {};
  const winRateStr = summary.winning_days_of_active || "48/58";
  const [winsStr, sessionsStr] = winRateStr.split("/");

  const gamma = {
    positive: (gex.avg_gex_when_active ?? -1) >= 0,
    flipStrike: "24,118",
    netGex: String(gex.avg_gex_when_active ?? "-1.42") + " Cr / pt",
    winRate: summary.win_rate_pct ?? 82.8,
    wins: parseInt(winsStr) || 48,
    sessions: parseInt(sessionsStr) || 58,
    profile: (gex.strike_profile || [
      { strike: "23400", gamma: -412 },
      { strike: "23600", gamma: -318 },
      { strike: "23800", gamma: -164 },
      { strike: "24000", gamma: -47 },
      { strike: "24200", gamma: 96 },
      { strike: "24400", gamma: 248 },
      { strike: "24600", gamma: 391 },
      { strike: "24800", gamma: 287 },
      { strike: "25000", gamma: 152 },
      { strike: "25200", gamma: 64 },
    ]) as Array<{ strike: string; gamma: number }>,
  };

  // Map basket from Python format (ticker/target_vega/lots_to_buy) to UI format
  const sizing = d.basket_sizing_snapshot || {};
  const rawBasket: any[] = sizing.basket || [];
  const constituentIvs: Record<string, number> = sizing.constituent_ivs || {};
  const basket = rawBasket.length > 0
    ? rawBasket.map((item: any) => ({
        symbol: item.ticker,
        weight: Number((item.weight * 100).toFixed(1)),
        spot: item.spot ?? 0,
        iv: Number(((constituentIvs[item.ticker] ?? 0) * 100).toFixed(1)),
        vega: item.vega_per_lot,
        sizing: Math.round(item.target_vega),
        lots: item.lots_to_buy,
      }))
    : [
        { symbol: "RELIANCE", weight: 10.2, spot: 1398.5, iv: 22.0, vega: 4.85, sizing: 2040, lots: 10 },
        { symbol: "HDFCBANK", weight: 8.9, spot: 727.0, iv: 19.0, vega: 3.12, sizing: 1780, lots: 14 },
        { symbol: "ICICIBANK", weight: 7.6, spot: 1245.0, iv: 21.0, vega: 4.2, sizing: 1520, lots: 8 },
        { symbol: "INFY", weight: 6.1, spot: 1890.0, iv: 24.0, vega: 5.1, sizing: 1220, lots: 6 },
        { symbol: "TCS", weight: 4.8, spot: 4120.0, iv: 18.0, vega: 6.3, sizing: 960, lots: 4 },
      ];

  const metrics = b.metrics || {};
  const markoutRaw = b.markout || {};
  const markouts = Object.entries(markoutRaw).map(([k, v]) => ({
    horizon: Number(k) >= 1000 ? (Number(k) / 1000) + "s" : k + "ms",
    bps: Number(typeof v === "object" ? (v as any).mean_bps : v),
  }));

  const eqRaw: Array<[number, number]> = b.equity_curve || [];
  const equityCurve = eqRaw.map(([ts, eq]) => {
    const d = new Date(ts);
    return {
      time: d.getHours() + ":" + String(d.getMinutes()).padStart(2, "0"),
      equity: eq,
    };
  });

  return {
    timestamp: new Date().toISOString(),
    dispersion: { heroStats, correlationSeries },
    gamma,
    basket,
    execution: {
      grossProfit: "Rs. " + (metrics.gross_profit ?? 883415.82).toLocaleString("en-IN"),
      grossLoss: "Rs. " + (metrics.gross_loss ?? 968427.75).toLocaleString("en-IN"),
      profitFactor: String(metrics.profit_factor ?? "0.91"),
      sharpe: String(metrics.sharpe ?? "-1.24"),
      sortino: String(metrics.sortino ?? "-10.06"),
      fills: metrics.fills ?? 1000,
      orders: metrics.orders ?? 7990,
      fillRatio: metrics.fill_ratio ?? 13.0,
      duration: metrics.duration ?? "1.3s",
      markouts,
      equityCurve,
    },
    connectivity: {
      ucc: "UCC •••• 2185",
      segments: [
        { name: "NSE", state: "Enabled" },
        { name: "BSE", state: "Enabled" },
      ],
      routing: "CASH (Equity) — Active",
      ipValidated: true,
      feed: "GrowwFeed",
      heartbeatMs: 42,
    },
  };
}
