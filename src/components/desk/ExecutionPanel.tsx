import { Bar, BarChart, Cell, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { execution, markouts } from "@/lib/desk-data";
import { Panel, Pill, Ring, Stat } from "./primitives";

export function ExecutionPanel() {
  return (
    <Panel
      eyebrow="Module 04 — Microstructure"
      title="Execution Microstructure"
      right={<Pill tone="muted">FIFO matched · {execution.duration} session</Pill>}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Gross Profit" value={execution.grossProfit} note="FIFO coupled match" dir="up" />
        <Stat label="Gross Loss" value={execution.grossLoss} note="Adverse selection incl." dir="down" />
        <Stat label="Profit Factor" value={execution.profitFactor} note="Target ≥ 1.20" dir="down" />
        <Stat
          label="Sharpe / Sortino"
          value={execution.sharpe}
          note={`Sortino ${execution.sortino}`}
          dir="down"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.8fr]">
        <div className="flex flex-col justify-center gap-4 rounded-md border border-border bg-surface-2/40 p-4">
          <Ring
            value={execution.fillRatio}
            label="Fill ratio"
            caption={`${execution.fills.toLocaleString("en-IN")} fills / ${execution.orders.toLocaleString("en-IN")} orders`}
          />
        </div>

        <div className="h-[280px] rounded-md border border-border bg-surface-2/40 p-3">
          <p className="label-xs mb-2 px-1">Markout slippage by horizon (bps)</p>
          <ResponsiveContainer width="100%" height="88%">
            <BarChart data={markouts} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="var(--color-grid)" strokeOpacity={0.3} vertical={false} />
              <XAxis
                dataKey="horizon"
                stroke="var(--color-grid)"
                tickLine={false}
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" }}
              />
              <YAxis
                stroke="var(--color-grid)"
                tickLine={false}
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" }}
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
              <ReferenceLine y={0} stroke="var(--color-grid)" />
              <Bar dataKey="bps" radius={[2, 2, 2, 2]} barSize={26}>
                {markouts.map((m) => (
                  <Cell
                    key={m.horizon}
                    fill={m.bps >= 0 ? "var(--color-bull)" : "var(--color-bear)"}
                    fillOpacity={0.95}
                    stroke={m.bps >= 0 ? "var(--color-bull)" : "var(--color-bear)"}
                    strokeOpacity={0.5}
                    strokeWidth={1}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Panel>
  );
}
