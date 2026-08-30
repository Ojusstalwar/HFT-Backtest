// Desk data: static defaults + live API fetcher.
// Components can import the static exports directly (zero-latency render)
// or use fetchDeskData() / useDeskData() for server-fresh values.

import type { DeskSnapshot } from "./live-data";
import { buildSnapshot } from "./live-data";

export async function fetchDeskData(): Promise<DeskSnapshot | null> {
  // Since GitHub Actions pushes data and triggers a Vercel rebuild,
  // we can just statically bundle the JSON instead of requiring a backend server API!
  return buildSnapshot();
}


function seeded(i: number, a: number, b: number, c: number) {
  return Math.sin(i * a) * b + Math.cos(i * c) * (b * 0.6);
}

export const correlationSeries = Array.from({ length: 60 }, (_, i) => {
  const implied = 0.42 + seeded(i, 0.21, 0.06, 0.09) + i * 0.0016;
  const realized = 0.11 + seeded(i, 0.17, 0.045, 0.13) - i * 0.0014;
  return {
    day: `D${i + 1}`,
    implied: Number(Math.max(0.05, implied).toFixed(3)),
    realized: Number(Math.max(0.01, realized).toFixed(3)),
    spread: Number(Math.max(0, implied - realized).toFixed(3)),
  };
});

export const heroStats = [
  { label: "Implied Correlation", value: "0.514", delta: "+0.031", dir: "up" as const, note: "Market-priced" },
  { label: "Realized Correlation", value: "0.024", delta: "-0.008", dir: "down" as const, note: "Actual 60d" },
  { label: "Spread Premium", value: "+0.489", delta: "+0.039", dir: "up" as const, note: "Edge captured" },
  { label: "Filtered P&L", value: "+8.160", delta: "+0.070", dir: "up" as const, note: "Raw +8.090" },
];

export const gammaProfile = [
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
];

export const gammaRegime = {
  positive: false,
  flipStrike: "24,118",
  netGex: "-1.42 Cr / pt",
  winRate: 82.8,
  wins: 48,
  sessions: 58,
};

export const basket = [
  { symbol: "RELIANCE", weight: 10.2, spot: 1398.5, iv: 22.0, vega: 4.85, sizing: 2040, lots: 10 },
  { symbol: "HDFCBANK", weight: 8.9, spot: 727.0, iv: 19.0, vega: 3.12, sizing: 1780, lots: 14 },
  { symbol: "ICICIBANK", weight: 7.6, spot: 1245.0, iv: 21.0, vega: 4.2, sizing: 1520, lots: 8 },
  { symbol: "INFY", weight: 6.1, spot: 1890.0, iv: 24.0, vega: 5.1, sizing: 1220, lots: 6 },
  { symbol: "TCS", weight: 4.8, spot: 4120.0, iv: 18.0, vega: 6.3, sizing: 960, lots: 4 },
];

export type BasketRow = (typeof basket)[number];

export const markouts = [
  { horizon: "10ms", bps: 1.8 },
  { horizon: "50ms", bps: 1.1 },
  { horizon: "250ms", bps: 0.4 },
  { horizon: "1s", bps: -0.6 },
  { horizon: "5s", bps: -1.4 },
  { horizon: "15s", bps: -2.1 },
  { horizon: "60s", bps: 0.9 },
];

export const execution = {
  grossProfit: "Rs. 8,83,415.82",
  grossLoss: "Rs. 9,68,427.75",
  profitFactor: "0.91",
  sharpe: "-1.24",
  sortino: "-10.06",
  fills: 1000,
  orders: 7990,
  fillRatio: 13.0,
  duration: "1.3s",
};

export const connectivity = {
  ucc: "UCC •••• 2185",
  segments: [
    { name: "NSE", state: "Enabled" },
    { name: "BSE", state: "Enabled" },
  ],
  routing: "CASH (Equity) — Active",
  ipValidated: true,
  feed: "GrowwFeed",
  heartbeatMs: 42,
};
