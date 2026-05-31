import Link from "next/link";
import { AlertTriangle, CheckCircle2, Clock3, Filter, ListOrdered } from "lucide-react";
import { getOrders } from "@/lib/live-api";
import type { BackendOrder } from "@/lib/types";

type SearchParams = Record<string, string | string[] | undefined>;

const pageSize = 20;

function getParam(params: SearchParams | undefined, key: string) {
  const value = params?.[key];
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function quantity(order: BackendOrder) {
  return Number(order.qty ?? order.quantity ?? 0);
}

function price(order: BackendOrder) {
  return Number(order.avg_price ?? order.price ?? 0);
}

function notional(order: BackendOrder) {
  return quantity(order) * price(order);
}

function orderTimestamp(order: BackendOrder) {
  return order.created_at || order.timestamp || "";
}

function formatDateTime(value: string) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function matchesFilters(order: BackendOrder, params: SearchParams | undefined) {
  const start = getParam(params, "start");
  const end = getParam(params, "end");
  const side = getParam(params, "side").toLowerCase();
  const status = getParam(params, "status").toLowerCase();
  const symbol = getParam(params, "symbol").toUpperCase();
  const executed = orderTimestamp(order).slice(0, 10);

  return (
    (!start || executed >= start) &&
    (!end || executed <= end) &&
    (!side || order.side.toLowerCase() === side) &&
    (!status || order.status.toLowerCase() === status) &&
    (!symbol || order.symbol.toUpperCase() === symbol)
  );
}

function pageHref(page: number, params: SearchParams | undefined) {
  const query = new URLSearchParams();
  for (const key of ["start", "end", "side", "status", "symbol"]) {
    const value = getParam(params, key);
    if (value) query.set(key, value);
  }
  query.set("page", String(page));
  return `/trades?${query.toString()}`;
}

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Trade Log",
  description: "Paper order log from the TradingBot backend.",
};

export default async function TradesPage({ searchParams }: { searchParams?: SearchParams }) {
  let orders: BackendOrder[];
  try {
    orders = await getOrders();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Trade API request failed";
    return (
      <main className="min-h-[calc(100vh-10rem)]">
        <section className="vektor-section py-8 lg:py-10">
          <div className="rounded-lg border border-destructive/40 bg-card/70 p-6 shadow-black-soft">
            <AlertTriangle className="mb-4 size-5 text-destructive" aria-hidden="true" />
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-destructive">
              Backend data unavailable
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-foreground">
              Trade log could not load
            </h1>
            <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
              {message}
            </p>
          </div>
        </section>
      </main>
    );
  }

  const filteredOrders = orders.filter((order) => matchesFilters(order, searchParams));
  const totalPages = Math.max(1, Math.ceil(filteredOrders.length / pageSize));
  const currentPage = Math.min(
    totalPages,
    Math.max(1, Number.parseInt(getParam(searchParams, "page") || "1", 10) || 1),
  );
  const visibleOrders = filteredOrders.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const filledOrders = orders.filter((order) => order.status.toLowerCase() === "filled");
  const pendingOrders = orders.filter((order) => order.status.toLowerCase() === "pending");
  const totalNotional = orders.reduce((total, order) => total + notional(order), 0);
  const sides = uniqueSorted(orders.map((order) => order.side));
  const statuses = uniqueSorted(orders.map((order) => order.status));
  const symbols = uniqueSorted(orders.map((order) => order.symbol));

  const stats = [
    { label: "Total orders", value: orders.length, icon: ListOrdered },
    { label: "Filled", value: filledOrders.length, icon: CheckCircle2 },
    { label: "Pending", value: pendingOrders.length, icon: Clock3 },
    { label: "Order notional", value: money(totalNotional), icon: Filter },
  ];

  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-8 lg:py-10">
        <div className="flex flex-col gap-6 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Trade Log
            </p>
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Paper broker orders
            </h1>
            <p className="max-w-2xl font-mono text-sm leading-6 text-muted-foreground">
              Paginated execution audit data from `/paper/orders`.
            </p>
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
                <p className="mt-2 text-xl font-semibold text-card-foreground">{stat.value}</p>
              </article>
            );
          })}
        </div>

        <form className="mt-6 rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              <span>Start</span>
              <input
                type="date"
                name="start"
                defaultValue={getParam(searchParams, "start")}
                className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none"
              />
            </label>
            <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              <span>End</span>
              <input
                type="date"
                name="end"
                defaultValue={getParam(searchParams, "end")}
                className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none"
              />
            </label>
            <Select name="symbol" label="Symbol" options={symbols} searchParams={searchParams} />
            <Select name="side" label="Side" options={sides} searchParams={searchParams} />
            <Select name="status" label="Status" options={statuses} searchParams={searchParams} />
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              className="inline-flex h-10 items-center rounded-md bg-primary px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary-foreground"
            >
              Apply Filters
            </button>
            <Link
              href="/trades"
              className="inline-flex h-10 items-center rounded-md border border-border px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground"
            >
              Reset
            </Link>
          </div>
        </form>

        <section className="mt-6 overflow-hidden rounded-lg border border-border bg-card/70 shadow-black-soft">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[64rem] border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Date/Time</th>
                  <th className="px-4 py-3 font-medium">Order ID</th>
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">Side</th>
                  <th className="px-4 py-3 font-medium">Qty</th>
                  <th className="px-4 py-3 font-medium">Price</th>
                  <th className="px-4 py-3 font-medium">Notional</th>
                  <th className="px-4 py-3 font-medium">Routing</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {visibleOrders.map((order) => (
                  <tr key={order.id} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDateTime(orderTimestamp(order))}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{order.id}</td>
                    <td className="px-4 py-3 font-semibold text-foreground">{order.symbol}</td>
                    <td className="px-4 py-3">
                      <SideBadge side={order.side} />
                    </td>
                    <td className="px-4 py-3 text-foreground">{quantity(order)}</td>
                    <td className="px-4 py-3 text-foreground">{money(price(order))}</td>
                    <td className="px-4 py-3 text-foreground">{money(notional(order))}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {order.routing_mode || order.instrument_type || order.asset_class || "Unavailable"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={order.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 font-mono text-xs text-muted-foreground">
            <span>
              Showing {visibleOrders.length} of {filteredOrders.length} orders / Page {currentPage}{" "}
              of {totalPages}
            </span>
            <div className="flex gap-2">
              <Link
                href={pageHref(Math.max(1, currentPage - 1), searchParams)}
                className="rounded border border-border px-3 py-2 hover:text-foreground"
              >
                Previous
              </Link>
              <Link
                href={pageHref(Math.min(totalPages, currentPage + 1), searchParams)}
                className="rounded border border-border px-3 py-2 hover:text-foreground"
              >
                Next
              </Link>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

function Select({
  name,
  label,
  options,
  searchParams,
}: {
  name: string;
  label: string;
  options: string[];
  searchParams?: SearchParams;
}) {
  return (
    <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
      <span>{label}</span>
      <select
        name={name}
        defaultValue={getParam(searchParams, name)}
        className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side.toLowerCase() === "buy";
  return (
    <span
      className={`rounded border px-2 py-1 ${
        isBuy
          ? "border-primary/30 bg-primary/10 text-primary"
          : "border-destructive/30 bg-destructive/10 text-destructive"
      }`}
    >
      {side}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const className =
    normalized === "filled"
      ? "border-primary/30 bg-primary/10 text-primary"
      : normalized === "pending"
        ? "border-secondary/30 bg-secondary/10 text-secondary"
        : "border-destructive/30 bg-destructive/10 text-destructive";

  return <span className={`rounded border px-2 py-1 ${className}`}>{status}</span>;
}
