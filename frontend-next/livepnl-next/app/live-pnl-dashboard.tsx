"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  ChevronDown,
  Gauge,
  ShieldAlert,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BackendPosition,
  DrawdownPoint,
  LivePnlDashboardData,
  PerformanceSnapshot,
  PortfolioChartPoint,
} from "@/lib/types";

const rangeOptions = [
  { label: "1W", days: 7 },
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "All", days: Number.POSITIVE_INFINITY },
];

function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function signedMoney(value: number) {
  return `${value >= 0 ? "+" : ""}${money(value)}`;
}

function percent(value: number) {
  return `${value >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}%`;
}

function tone(value: number) {
  return value >= 0 ? "text-primary" : "text-destructive";
}

function heatColor(value: number) {
  if (value > 0) return "bg-primary/70";
  if (value < 0) return "bg-destructive/70";
  return "bg-secondary/70";
}

function formatDate(value?: string | null) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function assetClass(position: BackendPosition) {
  return (
    position.asset_class ||
    position.instrument_type ||
    position.routing_mode ||
    "unknown"
  ).replaceAll("_", " ");
}

function normalizePositions(positions: BackendPosition[], equity: number) {
  return positions.map((position) => ({
    ...position,
    weight: equity > 0 ? (Number(position.market_value || 0) / equity) * 100 : 0,
  }));
}

function orderedSnapshots(snapshots: PerformanceSnapshot[]) {
  return [...snapshots].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime(),
  );
}

function buildPortfolioSeries(snapshots: PerformanceSnapshot[]): PortfolioChartPoint[] {
  const rows = orderedSnapshots(snapshots);
  const inceptionEquity = rows[0]?.equity || 0;

  return rows.map((snapshot) => {
    const primaryBenchmark = snapshot.benchmarks?.[0];
    const benchmark =
      primaryBenchmark && inceptionEquity > 0
        ? inceptionEquity * (1 + Number(primaryBenchmark.return_pct || 0) / 100)
        : null;

    return {
      date: snapshot.recorded_at.slice(0, 10),
      equity: Number(snapshot.equity || 0),
      benchmark,
    };
  });
}

function buildDrawdownSeries(snapshots: PerformanceSnapshot[]): DrawdownPoint[] {
  let peak = 0;
  return orderedSnapshots(snapshots).map((snapshot) => {
    const equity = Number(snapshot.equity || 0);
    peak = Math.max(peak, equity);
    return {
      date: snapshot.recorded_at.slice(0, 10),
      drawdown: peak > 0 ? Number((((equity - peak) / peak) * 100).toFixed(2)) : 0,
    };
  });
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

export function LivePnlDashboard({
  data,
  wsUrl,
}: {
  data: LivePnlDashboardData;
  wsUrl: string;
}) {
  const [range, setRange] = useState("3M");
  const [positions, setPositions] = useState(data.positions);
  const [streamState, setStreamState] = useState<"idle" | "connected" | "error">("idle");
  const selectedRange = rangeOptions.find((option) => option.label === range) ?? rangeOptions[2];
  const latestSnapshot = data.performanceSummary.latest_snapshot;
  const inceptionSnapshot = data.performanceSummary.inception_snapshot;
  const latestEquity = data.metrics.total_equity || latestSnapshot?.equity || 0;
  const normalized = normalizePositions(positions, latestEquity);
  const assetClasses = uniqueSorted(normalized.map(assetClass));
  const portfolioSeries = useMemo(() => buildPortfolioSeries(data.snapshots), [data.snapshots]);
  const drawdownSeries = useMemo(() => buildDrawdownSeries(data.snapshots), [data.snapshots]);
  const chartData = portfolioSeries.slice(
    selectedRange.days === Number.POSITIVE_INFINITY ? 0 : -selectedRange.days,
  );
  const drawdownData = drawdownSeries.slice(
    selectedRange.days === Number.POSITIVE_INFINITY ? 0 : -selectedRange.days,
  );
  const trackRecord = data.performanceSummary.track_record || {};
  const dayPnl =
    latestSnapshot && data.snapshots.length > 1
      ? latestSnapshot.equity - orderedSnapshots(data.snapshots).at(-2)!.equity
      : data.metrics.pnl_change;
  const dayPnlPercent =
    latestSnapshot && latestEquity > 0 ? (dayPnl / latestEquity) * 100 : data.metrics.equity_change;
  const totalReturn = latestEquity - (inceptionSnapshot?.equity || data.metrics.baseline_equity || 0);
  const totalReturnPct = Number(trackRecord.total_return_pct ?? data.metrics.equity_change ?? 0);
  const latestOrderCount = data.orders.length;
  const activePriceCount = Object.keys(data.prices || {}).length;
  const riskHalted = Boolean(data.risk.drawdown_breaker?.halted);

  const stats = [
    {
      label: "Portfolio Value",
      value: money(latestEquity),
      sub: `${percent(totalReturnPct)} since inception`,
      icon: Wallet,
      valueClass: "text-foreground",
    },
    {
      label: "Latest PnL",
      value: signedMoney(dayPnl),
      sub: percent(dayPnlPercent),
      icon: Activity,
      valueClass: tone(dayPnl),
    },
    {
      label: "Total Return",
      value: signedMoney(totalReturn),
      sub: `${percent(Number(trackRecord.alpha_vs_primary_benchmark_pct || 0))} alpha`,
      icon: BarChart3,
      valueClass: tone(totalReturn),
    },
    {
      label: "Sharpe Ratio",
      value: Number(trackRecord.sharpe_ratio ?? data.metrics.sharpe_ratio ?? 0).toFixed(2),
      sub: `Max DD ${percent(Number(trackRecord.max_drawdown_pct ?? data.metrics.max_drawdown_ytd ?? 0))}`,
      icon: ShieldCheck,
      valueClass: "text-foreground",
    },
  ];

  useEffect(() => {
    if (!wsUrl) return;
    setStreamState("idle");
    const socket = new WebSocket(wsUrl);
    let closeWhenOpen = false;
    socket.onopen = () => setStreamState("connected");
    socket.onerror = () => setStreamState("error");
    socket.onclose = () => setStreamState((current) => (current === "error" ? "error" : "idle"));
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data));
        if (payload?.type === "positions_update" && Array.isArray(payload.data)) {
          setPositions(payload.data as BackendPosition[]);
        }
      } catch {
        setStreamState("error");
      }
    };

    return () => {
      if (socket.readyState === WebSocket.CONNECTING) {
        closeWhenOpen = true;
        socket.onopen = () => {
          if (closeWhenOpen) socket.close();
        };
        return;
      }

      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [wsUrl]);

  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-8 lg:py-10">
        <div className="flex flex-col gap-6 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Vektor Live PnL
            </p>
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Paper portfolio performance
            </h1>
            <p className="max-w-2xl font-mono text-sm leading-6 text-muted-foreground">
              Live account, position, order, risk, and performance data from the
              TradingBot backend.
            </p>
          </div>
          <div className="flex flex-col gap-2 lg:items-end">
            <div className="rounded-md border border-border bg-card/70 px-3 py-2 font-mono text-xs text-muted-foreground">
              Updated <span className="text-foreground">{formatDate(latestSnapshot?.recorded_at)}</span>
            </div>
            <div className="rounded-md border border-border bg-card/70 px-3 py-2 font-mono text-xs text-foreground">
              Stream: {streamState}
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <article
                key={stat.label}
                className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
              >
                <Icon className="mb-4 size-4 text-primary" aria-hidden="true" />
                <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {stat.label}
                </p>
                <p className={`mt-2 text-2xl font-semibold ${stat.valueClass}`}>
                  {stat.value}
                </p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">{stat.sub}</p>
              </article>
            );
          })}
        </div>

        <section className="mt-6 grid gap-3 md:grid-cols-3">
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              Orders
            </p>
            <p className="mt-2 text-2xl font-semibold text-card-foreground">{latestOrderCount}</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              Records from `/paper/orders`
            </p>
          </article>
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              Price Feed
            </p>
            <p className="mt-2 text-2xl font-semibold text-card-foreground">{activePriceCount}</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              Symbols returned by `/market/prices`
            </p>
          </article>
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              Risk Halt
            </p>
            <p className={`mt-2 text-2xl font-semibold ${riskHalted ? "text-destructive" : "text-primary"}`}>
              {riskHalted ? "Active" : "Clear"}
            </p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              Drawdown breaker from `/risk/status`
            </p>
          </article>
        </section>

        <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-card-foreground">
                Holdings Heatmap Bar
              </h2>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                Segment width equals live portfolio weight; color reflects unrealized PnL.
              </p>
            </div>
            <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <span className="size-2 rounded-full bg-primary" />
              Gain
              <span className="ml-2 size-2 rounded-full bg-destructive" />
              Loss
            </div>
          </div>
          {normalized.length > 0 ? (
            <div className="flex h-12 overflow-hidden rounded-md border border-border bg-background">
              {normalized.map((position) => (
                <div
                  key={position.symbol}
                  title={`${position.symbol}: ${position.weight.toFixed(2)}%, ${signedMoney(
                    Number(position.unrealized_pnl || 0),
                  )} unrealized PnL, ${money(Number(position.market_value || 0))} value`}
                  className={`${heatColor(
                    Number(position.unrealized_pnl || 0),
                  )} flex min-w-[1.6rem] items-center justify-center border-r border-background/60 px-1 font-mono text-[0.62rem] font-semibold text-background last:border-r-0`}
                  style={{ width: `${Math.max(1, position.weight)}%` }}
                >
                  <span className="truncate">{position.symbol}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="font-mono text-sm text-muted-foreground">
              No open positions returned by `/paper/positions`.
            </p>
          )}
        </section>

        <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {assetClasses.map((groupName) => {
            const rows = normalized.filter((position) => assetClass(position) === groupName);
            const allocated = rows.reduce((total, position) => total + Number(position.market_value || 0), 0);
            const openPnl = rows.reduce((total, position) => total + Number(position.unrealized_pnl || 0), 0);
            return (
              <article
                key={groupName}
                className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold capitalize text-card-foreground">
                    {groupName}
                  </h2>
                  <Gauge className="size-4 text-primary" aria-hidden="true" />
                </div>
                <dl className="mt-4 space-y-3 font-mono text-xs">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Allocated</dt>
                    <dd className="text-foreground">{money(allocated)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Portfolio Weight</dt>
                    <dd className="text-foreground">{percent((allocated / Math.max(1, latestEquity)) * 100)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Open PnL</dt>
                    <dd className={tone(openPnl)}>{signedMoney(openPnl)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Positions</dt>
                    <dd className="text-foreground">{rows.length}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </section>

        <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.65fr)]">
          <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-card-foreground">
                  Portfolio vs Benchmark
                </h2>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  Performance snapshots from `/fund/performance/snapshots`.
                </p>
              </div>
              <div className="flex rounded-md border border-border bg-background/60 p-1">
                {rangeOptions.map((option) => (
                  <button
                    key={option.label}
                    type="button"
                    onClick={() => setRange(option.label)}
                    className={`rounded px-3 py-1 font-mono text-xs ${
                      range === option.label
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                  <XAxis dataKey="date" stroke="#8d98aa" tickLine={false} tickMargin={10} />
                  <YAxis stroke="#8d98aa" tickFormatter={(value) => `$${Number(value) / 1000}k`} />
                  <Tooltip
                    contentStyle={{
                      background: "#141820",
                      border: "1px solid rgba(255,255,255,0.12)",
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => money(value)}
                  />
                  <Line type="monotone" dataKey="equity" stroke="#b8f09a" strokeWidth={2} dot={false} name="Vektor" />
                  <Line type="monotone" dataKey="benchmark" stroke="#f5c842" strokeWidth={2} dot={false} name="Benchmark" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <div className="mb-4 flex items-center gap-2">
              <ShieldAlert className="size-4 text-destructive" aria-hidden="true" />
              <div>
                <h2 className="text-xl font-semibold text-card-foreground">Drawdown</h2>
                <p className="font-mono text-xs text-muted-foreground">
                  Computed from recorded equity snapshots.
                </p>
              </div>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdownData}>
                  <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                  <XAxis dataKey="date" stroke="#8d98aa" tickLine={false} tickMargin={10} />
                  <YAxis stroke="#8d98aa" tickFormatter={(value) => `${value}%`} />
                  <Tooltip
                    contentStyle={{
                      background: "#141820",
                      border: "1px solid rgba(255,255,255,0.12)",
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => `${value.toFixed(2)}%`}
                  />
                  <Area type="monotone" dataKey="drawdown" stroke="#ff5f5f" fill="#ff5f5f" fillOpacity={0.22} name="Drawdown" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </article>
        </section>

        <section
          id="holdings-table"
          className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft"
        >
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-card-foreground">Holdings Table</h2>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              Open positions from `/paper/positions`.
            </p>
          </div>
          <div className="space-y-3">
            {assetClasses.map((groupName) => (
              <details
                key={groupName}
                open
                className="overflow-hidden rounded-md border border-border bg-background/50"
              >
                <summary className="flex cursor-pointer items-center justify-between gap-3 border-b border-border px-4 py-3">
                  <span className="font-mono text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
                    {groupName}
                  </span>
                  <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
                </summary>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[58rem] border-collapse font-mono text-xs">
                    <thead>
                      <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                        <th className="px-4 py-3 font-medium">Ticker</th>
                        <th className="px-4 py-3 font-medium">Asset Class</th>
                        <th className="px-4 py-3 font-medium">Qty</th>
                        <th className="px-4 py-3 font-medium">Avg Cost</th>
                        <th className="px-4 py-3 font-medium">Last</th>
                        <th className="px-4 py-3 font-medium">Market Value</th>
                        <th className="px-4 py-3 font-medium">Unrealized P&L</th>
                        <th className="px-4 py-3 font-medium">Weight</th>
                        <th className="px-4 py-3 font-medium">Routing</th>
                      </tr>
                    </thead>
                    <tbody>
                      {normalized
                        .filter((position) => assetClass(position) === groupName)
                        .map((position) => (
                          <tr key={position.symbol} className="border-b border-border last:border-b-0">
                            <td className="px-4 py-3 font-semibold text-foreground">
                              {position.symbol}
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{assetClass(position)}</td>
                            <td className="px-4 py-3 text-foreground">{position.qty}</td>
                            <td className="px-4 py-3 text-foreground">{money(position.avg_price)}</td>
                            <td className="px-4 py-3 text-foreground">{money(position.market_price)}</td>
                            <td className="px-4 py-3 text-foreground">{money(position.market_value)}</td>
                            <td className={`px-4 py-3 ${tone(position.unrealized_pnl)}`}>
                              {signedMoney(position.unrealized_pnl)}
                            </td>
                            <td className="px-4 py-3 text-foreground">{position.weight.toFixed(2)}%</td>
                            <td className="px-4 py-3 text-muted-foreground">
                              {position.routing_mode || position.instrument_type || "Unavailable"}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
