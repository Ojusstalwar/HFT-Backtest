import { Activity, CheckCircle2, Radio, ShieldCheck } from "lucide-react";
import { Panel, Pill } from "./primitives";
import type { DeskSnapshot } from "@/lib/live-data";

export function ConnectivityWidget(connectivity: DeskSnapshot["connectivity"]) {
  return (
    <Panel
      eyebrow="Module 05 — Connectivity"
      title="Live Connectivity"
      right={
        <Pill tone="bull">
          <span className="size-1.5 animate-pulse rounded-full bg-current" />
          Feed live
        </Pill>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-md border border-border bg-surface-2/60 p-4">
          <p className="label-xs">Exchange segments</p>
          <div className="mt-3 space-y-2">
            {connectivity.segments.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <span className="num">{s.name}</span>
                <span className="inline-flex items-center gap-1.5 text-bull">
                  <CheckCircle2 className="size-3.5" aria-hidden />
                  {s.state}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-md border border-border bg-surface-2/60 p-4">
          <p className="label-xs">Account identifier</p>
          <p className="num mt-3 text-xl">{connectivity.ucc}</p>
          <p className="mt-2 text-xs text-muted-foreground">Masked · read-only</p>
        </div>

        <div className="rounded-md border border-border bg-surface-2/60 p-4">
          <p className="label-xs">Static IP validation</p>
          <p className="mt-3 inline-flex items-center gap-2 text-sm text-bull">
            <ShieldCheck className="size-4" aria-hidden />
            SEBI static IP validated
          </p>
          <p className="mt-2 text-xs text-muted-foreground">Routing: {connectivity.routing}</p>
        </div>

        <div className="rounded-md border border-border bg-surface-2/60 p-4">
          <p className="label-xs">WebSocket heartbeat</p>
          <p className="num mt-3 inline-flex items-center gap-2 text-xl text-primary">
            <Radio className="size-4 animate-pulse" aria-hidden />
            {connectivity.heartbeatMs} ms
          </p>
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Activity className="size-3" aria-hidden />
            {connectivity.feed} · ticks & order updates subscribed
          </p>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Read-only telemetry. No credentials, tokens, or raw account numbers are displayed or stored client-side.
      </p>
    </Panel>
  );
}
