import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { DispersionPanel } from "@/components/desk/DispersionPanel";
import { GammaPanel } from "@/components/desk/GammaPanel";
import { BasketTable } from "@/components/desk/BasketTable";
import { ExecutionPanel } from "@/components/desk/ExecutionPanel";
import { ConnectivityWidget } from "@/components/desk/ConnectivityWidget";
import { useScrollY } from "@/hooks/use-scroll-fx";
import { useDeskData } from "@/hooks/use-desk-data";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dispersion Arbitrage & Implied Correlation Engine" },
      {
        name: "description",
        content:
          "Volatility dispersion desk: implied vs realized correlation, dealer gamma regime, vega-neutral basket and HFT execution microstructure analytics.",
      },
      { property: "og:title", content: "Dispersion Arbitrage & Implied Correlation Engine" },
      {
        property: "og:description",
        content:
          "Implied vs realized correlation, GEX regime filter, vega-neutral basket allocation and execution microstructure in one terminal.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const MODULE_TABS = [
  { id: "dispersion", label: "Dispersion", sub: "Vol Engine" },
  { id: "gamma", label: "Gamma Regime", sub: "GEX Filter" },
  { id: "basket", label: "Basket", sub: "Vega-Neutral" },
  { id: "execution", label: "Execution", sub: "Microstructure" },
  { id: "connectivity", label: "Connectivity", sub: "Live Feed" },
] as const;

type ModuleId = (typeof MODULE_TABS)[number]["id"];

function Index() {
  const y = useScrollY();
  const [progress, setProgress] = useState(0);
  const [active, setActive] = useState<ModuleId>("dispersion");
  const [entering, setEntering] = useState(true);

  const { data, isLoading } = useDeskData();

  const tape = data ? [
    `NIFTY ${(data.basket.find(b => b.symbol === "INDEX (SELL)")?.spot ?? 24800).toLocaleString()}`,
    `IMPL CORR ${data.dispersion.heroStats[0]?.value ?? "0.00"}`,
    `REAL CORR ${data.dispersion.heroStats[1]?.value ?? "0.00"}`,
    `SPREAD ${data.dispersion.heroStats[2]?.value ?? "0.00"}`,
    `GEX ${data.gamma.heroStats[0]?.value ?? "0.00"} Cr/pt`,
    `VEGA DRIFT 0.00`,
    `FILL ${((data.execution.fills / data.execution.orders) * 100).toFixed(1)}%`,
    `PF ${data.execution.profitFactor}`,
  ] : [
    "LOADING...", "LOADING...", "LOADING...", "LOADING...", "LOADING..."
  ];

  useEffect(() => {
    const h = document.documentElement.scrollHeight - window.innerHeight;
    setProgress(h > 0 ? Math.min(1, y / h) : 0);
  }, [y]);

  const switchTab = (id: ModuleId) => {
    if (id === active) return;
    setEntering(false);
    setActive(id);
    requestAnimationFrame(() => requestAnimationFrame(() => setEntering(true)));
  };

  return (
    <div className="relative overflow-x-clip">
      {/* scroll progress */}
      <div
        aria-hidden
        className="fixed inset-x-0 top-0 z-50 h-0.5 origin-left bg-primary/80"
        style={{ transform: `scaleX(${progress})` }}
      />

      {/* ambient depth layer */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div
          className="float-slow absolute -left-32 top-10 size-[420px] rounded-full blur-[110px]"
          style={{
            background: "oklch(0.79 0.13 195 / 16%)",
            transform: `translate3d(0, ${y * -0.08}px, 0)`,
          }}
        />
        <div
          className="float-slow absolute -right-24 top-[55%] size-[380px] rounded-full blur-[120px]"
          style={{
            background: "oklch(0.8 0.14 82 / 12%)",
            transform: `translate3d(0, ${y * -0.05}px, 0)`,
            animationDelay: "-4s",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(oklch(0.32 0.016 250 / 45%) 1px, transparent 1px), linear-gradient(90deg, oklch(0.32 0.016 250 / 45%) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(ellipse at 50% 0%, black, transparent 78%)",
            transform: `perspective(700px) rotateX(58deg) translate3d(0, ${-(y * 0.25) % 64}px, 0)`,
            transformOrigin: "50% 0%",
          }}
        />
      </div>

      <main className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
        <header
          className="mb-8"
          style={{
            transform: `translate3d(0, ${y * 0.12}px, 0)`,
            opacity: Math.max(0, 1 - y / 520),
          }}
        >
          <p className="label-xs">HFT Backtester · Options Desk</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-4xl">
            Dispersion Arbitrage &amp; Implied Correlation Engine
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            GEX-filtered, strictly vega-neutral index-vs-single-stock dispersion, with full execution
            microstructure diagnostics.
          </p>
        </header>

        <div
          aria-hidden
          className="mb-8 overflow-hidden rounded-md border border-border bg-surface/70 py-2"
        >
          <div className="ticker-track flex w-max gap-8 whitespace-nowrap px-4">
            {[...tape, ...tape].map((t, i) => (
              <span key={i} className="num text-xs text-muted-foreground">
                {t}
              </span>
            ))}
          </div>
        </div>

        <nav
          role="tablist"
          aria-label="Desk modules"
          className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-5"
        >
          {MODULE_TABS.map((m) => {
            const isActive = m.id === active;
            return (
              <button
                key={m.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => switchTab(m.id)}
                className={`group relative overflow-hidden rounded-md border px-3 py-2.5 text-left transition-all duration-300 ${
                  isActive
                    ? "border-primary/50 bg-primary/10 shadow-[0_0_24px_-6px] shadow-primary/40"
                    : "border-border bg-surface/60 hover:-translate-y-0.5 hover:border-muted-foreground/40 hover:bg-surface"
                }`}
              >
                <span
                  aria-hidden
                  className={`absolute inset-x-0 top-0 h-0.5 origin-left bg-primary transition-transform duration-300 ${
                    isActive ? "scale-x-100" : "scale-x-0 group-hover:scale-x-50"
                  }`}
                />
                <span className={`label-xs block ${isActive ? "text-primary" : ""}`}>{m.sub}</span>
                <span className="mt-0.5 block text-sm font-semibold tracking-tight">
                  {m.label}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="[perspective:1400px]">
          <div
            key={active}
            className={`transition-all duration-500 ease-out ${
              entering ? "translate-y-0 opacity-100 [transform:rotateX(0deg)]" : "translate-y-4 opacity-0 [transform:rotateX(3deg)]"
            }`}
          >
            {!data ? (
              <div className="flex h-64 items-center justify-center rounded-md border border-border bg-surface-2/40">
                <span className="relative flex size-4 items-center justify-center">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex size-3 rounded-full bg-primary" />
                </span>
                <span className="ml-3 text-sm text-muted-foreground">Loading desk data...</span>
              </div>
            ) : (
              <>
                {active === "dispersion" && <DispersionPanel {...data.dispersion} />}
                {active === "gamma" && <GammaPanel {...data.gamma} />}
                {active === "basket" && <BasketTable basket={data.basket} />}
                {active === "execution" && <ExecutionPanel {...data.execution} />}
                {active === "connectivity" && <ConnectivityWidget {...data.connectivity} />}
              </>
            )}
          </div>
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-center">
          <p className="label-xs">Made with love by Ojuss Talwar</p>
          <p className="label-xs mt-1">All Copyrights Reserved.</p>
        </footer>
      </main>
    </div>
  );
}
