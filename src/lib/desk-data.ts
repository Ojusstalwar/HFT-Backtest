// Desk data: static defaults + live API fetcher.
// Components can import the static exports directly (zero-latency render)
// or use fetchDeskData() / useDeskData() for server-fresh values.

import type { DeskSnapshot } from "./live-data";
import { buildSnapshot } from "./live-data";

// Build the snapshot once at import time — used by both SSR and client
const _snap = buildSnapshot();

export async function fetchDeskData(): Promise<DeskSnapshot | null> {
  return _snap;
}

// Re-export live data for any component that still imports these directly
export const correlationSeries = _snap.dispersion.correlationSeries;
export const heroStats = _snap.dispersion.heroStats;

export const gammaProfile = _snap.gamma.profile;
export const gammaRegime = _snap.gamma;

export const basket = _snap.basket;
export type BasketRow = (typeof basket)[number];

export const markouts = _snap.execution.markouts;
export const execution = _snap.execution;
export const connectivity = _snap.connectivity;
