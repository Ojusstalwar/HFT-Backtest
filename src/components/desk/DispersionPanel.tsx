import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { correlationSeries, heroStats } from "@/lib/desk-data";
import { Panel, Pill, Stat } from "./primitives";

const axis = {
  stroke: "var(--color-grid)",
  tick: { fill: "var(--color-muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" },
};

export function DispersionPanel() {
  return (
    <Panel
      eyebrow="Module 01 — Dispersion / Correlation"
      title="Volatility Dispersion Engine"
      right={<Pill tone="primary">60-day window</Pill>}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {heroStats.map((s) => (
          <Stat key={s.label} {...s} />
        ))}
      </div>

      <div className="mt-6 h-[320px] w-full rounded-md border border-border bg-surface-2/40 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={correlationSeries} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="spreadFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--color-grid)" strokeOpacity={0.35} vertical={false} />
            <XAxis dataKey="day" {...axis} interval={9} tickLine={false} />
            <YAxis yAxisId="left" domain={[0, 0.7]} {...axis} tickLine={false} width={48} />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 0.7]}
              {...axis}
              tickLine={false}
              width={48}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--color-foreground)",
              }}
            />
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="spread"
              stroke="none"
              fill="url(#spreadFill)"
              name="Spread"
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="implied"
              stroke="var(--color-primary)"
              strokeWidth={2}
              dot={false}
              name="Implied"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="realized"
              stroke="var(--color-info)"
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={false}
              name="Realized"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <LegendDot color="var(--color-primary)" label="Implied correlation (left axis)" />
        <LegendDot color="var(--color-info)" label="Realized correlation (right axis)" />
        <LegendDot color="var(--color-accent)" label="Spread premium" />
      </div>
    </Panel>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="size-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
