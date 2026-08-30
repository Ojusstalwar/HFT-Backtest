import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel, Pill, Ring } from "./primitives";
import type { DeskSnapshot } from "@/lib/live-data";

export function GammaPanel(gammaRegime: DeskSnapshot["gamma"]) {
  const positive = gammaRegime.positive;
  return (
    <Panel
      eyebrow="Module 02 — Regime filter"
      title="Dealer Gamma Exposure"
      right={
        <Pill tone={positive ? "bull" : "bear"}>
          <span className="size-1.5 rounded-full bg-current" />
          {positive ? "Positive Gamma — Stable" : "Negative Gamma — De-risking"}
        </Pill>
      }
    >
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="h-[280px] rounded-md border border-border bg-surface-2/40 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={gammaRegime.profile} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 4 }}>
              <CartesianGrid stroke="var(--color-grid)" strokeOpacity={0.3} horizontal={false} />
              <XAxis
                type="number"
                stroke="var(--color-grid)"
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="strike"
                width={54}
                stroke="var(--color-grid)"
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "var(--color-grid)", fillOpacity: 0.2 }}
                contentStyle={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              />
              <ReferenceLine
                x={0}
                stroke="var(--color-accent)"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                label={{
                  value: `Flip ${gammaRegime.flipStrike}`,
                  position: "top",
                  fill: "var(--color-accent)",
                  fontSize: 11,
                }}
              />
              <Bar dataKey="gamma" radius={[2, 2, 2, 2]} barSize={14}>
                {gammaRegime.profile.map((d) => (
                  <Cell
                    key={d.strike}
                    fill={d.gamma >= 0 ? "var(--color-primary)" : "var(--color-accent)"}
                    fillOpacity={0.92}
                    stroke={d.gamma >= 0 ? "var(--color-primary)" : "var(--color-accent)"}
                    strokeOpacity={0.45}
                    strokeWidth={1}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-between gap-5 rounded-md border border-border bg-surface-2/40 p-4">
          <Ring
            value={gammaRegime.winRate}
            label="GEX-filtered win rate"
            caption={`${gammaRegime.wins} / ${gammaRegime.sessions} active sessions`}
            tone="bull"
          />
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="label-xs">Net GEX</dt>
              <dd className="num mt-1 text-bear">{gammaRegime.netGex}</dd>
            </div>
            <div>
              <dt className="label-xs">Zero-gamma flip</dt>
              <dd className="num mt-1">{gammaRegime.flipStrike}</dd>
            </div>
          </dl>
        </div>
      </div>
    </Panel>
  );
}
