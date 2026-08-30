import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useReveal, useTilt } from "@/hooks/use-scroll-fx";

export function Panel({
  title,
  eyebrow,
  right,
  children,
  className,
}: {
  title: string;
  eyebrow?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const { ref: revealRef, shown } = useReveal<HTMLDivElement>();
  const tiltRef = useTilt<HTMLElement>(3.5);

  return (
    <div ref={revealRef} className={cn("reveal-base", shown && "reveal-in")}>
      <section
        ref={tiltRef}
        className={cn("panel tilt-3d sheen group p-5 sm:p-6 hover:tilt-3d-hover", className)}
      >
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background:
              "radial-gradient(600px circle at var(--gx) var(--gy), oklch(0.79 0.13 195 / 7%), transparent 60%)",
          }}
        />
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            {eyebrow ? <p className="label-xs">{eyebrow}</p> : null}
            <h2 className="mt-1 text-lg font-semibold tracking-tight sm:text-xl">{title}</h2>
          </div>
          {right}
        </header>
        {children}
      </section>
    </div>
  );
}


export function Stat({
  label,
  value,
  delta,
  dir,
  note,
}: {
  label: string;
  value: string;
  delta?: string;
  dir?: "up" | "down";
  note?: string;
}) {
  const Icon = dir === "down" ? ArrowDownRight : ArrowUpRight;
  return (
    <div className="rounded-md border border-border bg-surface-2/60 px-4 py-3 transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_20px_40px_-28px_oklch(0_0_0/90%)]">
      <p className="label-xs">{label}</p>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="num text-2xl font-semibold sm:text-3xl">{value}</span>
        {delta ? (
          <span
            className={cn(
              "num inline-flex items-center gap-0.5 text-xs",
              dir === "down" ? "text-bear" : "text-bull",
            )}
          >
            <Icon className="size-3" aria-hidden />
            {delta}
          </span>
        ) : null}
      </div>
      {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}

export function Ring({
  value,
  label,
  caption,
  tone = "primary",
}: {
  value: number;
  label: string;
  caption?: string;
  tone?: "primary" | "bull" | "warn";
}) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const stroke =
    tone === "bull" ? "var(--color-bull)" : tone === "warn" ? "var(--color-warn)" : "var(--color-primary)";
  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="size-24 -rotate-90" role="img" aria-label={`${label} ${value}%`}>
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--color-grid)" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(1, value / 100))}
        />
      </svg>
      <div>
        <p className="num text-2xl font-semibold">{value.toFixed(1)}%</p>
        <p className="label-xs mt-0.5">{label}</p>
        {caption ? <p className="mt-1 text-xs text-muted-foreground">{caption}</p> : null}
      </div>
    </div>
  );
}

export function Pill({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "bull" | "bear" | "muted" | "primary";
}) {
  const tones: Record<string, string> = {
    bull: "border-bull/40 bg-bull/10 text-bull",
    bear: "border-bear/40 bg-bear/10 text-bear",
    primary: "border-primary/40 bg-primary/10 text-primary",
    muted: "border-border bg-surface-2 text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium tracking-wide",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
