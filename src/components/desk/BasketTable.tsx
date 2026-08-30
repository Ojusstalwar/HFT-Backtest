import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { basket, type BasketRow } from "@/lib/desk-data";
import { Panel, Pill } from "./primitives";
import { cn } from "@/lib/utils";

type Key = keyof BasketRow;

const columns: { key: Key; label: string; numeric?: boolean }[] = [
  { key: "symbol", label: "Symbol" },
  { key: "weight", label: "Weight", numeric: true },
  { key: "spot", label: "Spot (Rs)", numeric: true },
  { key: "iv", label: "ATM IV", numeric: true },
  { key: "vega", label: "Straddle Vega", numeric: true },
  { key: "sizing", label: "Sizing Vega", numeric: true },
  { key: "lots", label: "Lots", numeric: true },
];

const inr = (n: number, d = 2) =>
  n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });

export function BasketTable() {
  const [sort, setSort] = useState<{ key: Key; dir: "asc" | "desc" }>({ key: "weight", dir: "desc" });

  const rows = useMemo(() => {
    const sorted = [...basket].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv));
    });
    return sort.dir === "desc" ? sorted.reverse() : sorted;
  }, [sort]);

  const maxWeight = Math.max(...basket.map((r) => r.weight));

  const toggle = (key: Key) =>
    setSort((s) => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }));

  return (
    <Panel
      eyebrow="Module 03 — Basket construction"
      title="Vega-Neutral Single-Stock Basket"
      right={<Pill tone="muted">NIFTY constituents</Pill>}
    >
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="bg-surface-2/70">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn("px-3 py-2", c.numeric ? "text-right" : "text-left")}
                >
                  <button
                    onClick={() => toggle(c.key)}
                    className={cn(
                      "label-xs inline-flex items-center gap-1 transition-colors hover:text-foreground",
                      sort.key === c.key && "text-primary",
                    )}
                  >
                    {c.label}
                    {sort.key === c.key ? (
                      sort.dir === "desc" ? (
                        <ChevronDown className="size-3" />
                      ) : (
                        <ChevronUp className="size-3" />
                      )
                    ) : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="border-t border-border/70 transition-colors hover:bg-surface-2/50">
                <td className="px-3 py-2.5 font-medium tracking-tight">{r.symbol}</td>
                <td className="px-3 py-2.5 text-right">
                  <span className="num">{r.weight.toFixed(1)}%</span>
                  <span className="mt-1 block h-1 w-full overflow-hidden rounded-full bg-grid">
                    <span
                      className="block h-full rounded-full bg-primary"
                      style={{ width: `${(r.weight / maxWeight) * 100}%` }}
                    />
                  </span>
                </td>
                <td className="num px-3 py-2.5 text-right">{inr(r.spot)}</td>
                <td className="num px-3 py-2.5 text-right">{r.iv.toFixed(1)}%</td>
                <td className="num px-3 py-2.5 text-right">{inr(r.vega)}</td>
                <td className="num px-3 py-2.5 text-right">{inr(r.sizing, 0)}</td>
                <td className="num px-3 py-2.5 text-right text-primary">{r.lots}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-bull/30 bg-bull/5 px-4 py-3">
        <p className="label-xs">Net basket vega drift</p>
        <p className="num text-2xl font-semibold text-bull">
          0.00 Rs/vol <span className="text-sm font-normal">— Neutral</span>
        </p>
      </div>
    </Panel>
  );
}
