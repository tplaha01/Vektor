import { Target } from "lucide-react";
import { Bar, EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  dataOr,
  money,
  numberValue,
  percent,
  recordValue,
  safeFetchJson,
  stringValue,
  type BackendOrder,
  type BackendPosition,
  type JsonRecord,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

function assetClass(position: BackendPosition) {
  return stringValue(
    position.asset_class || position.instrument_type || position.routing_mode,
    "unknown",
  ).replaceAll("_", " ");
}

function tone(value: number) {
  return value >= 0 ? "text-primary" : "text-destructive";
}

export default async function PositionsPage() {
  const [positionsResult, ordersResult, riskResult, metricsResult, exposureResult] =
    await Promise.all([
      safeFetchJson<BackendPosition[]>("/paper/positions"),
      safeFetchJson<BackendOrder[]>("/paper/orders"),
      safeFetchJson<JsonRecord>("/risk/status"),
      safeFetchJson<JsonRecord>("/api/admin/metrics/summary"),
      safeFetchJson<JsonRecord>("/api/admin/ceo/exposure"),
    ]);

  const positions = dataOr(positionsResult, []);
  const orders = dataOr(ordersResult, []);
  const risk = dataOr(riskResult, {});
  const metrics = dataOr(metricsResult, {});
  const totalValue = positions.reduce((total, position) => total + Number(position.market_value || 0), 0);
  const totalPnl = positions.reduce((total, position) => total + Number(position.unrealized_pnl || 0), 0);
  const classes = Array.from(new Set(positions.map(assetClass))).sort();

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /positions
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Positions & Holdings
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Live paper-broker holdings, order count, risk state, and exposure returned by
          the TradingBot backend.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Portfolio Value" value={money(totalValue)} />
        <StatCard label="Account Equity" value={money(numberValue(metrics.total_equity))} />
        <StatCard label="Open Positions" value={positions.length} />
        <StatCard label="Orders" value={orders.length} />
        <StatCard label="Unrealized P&L" value={money(totalPnl)} tone={tone(totalPnl)} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <article className="overflow-hidden rounded-lg border border-border bg-card/70 shadow-black-soft">
          <div className="border-b border-border p-5">
            <div className="flex items-center gap-2">
              <Target className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-card-foreground">Open Positions</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[72rem] border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                  {[
                    "Ticker",
                    "Asset Class",
                    "Qty",
                    "Avg Entry",
                    "Market Price",
                    "Market Value",
                    "Unrealized P&L",
                    "Weight",
                    "Routing",
                  ].map((header) => (
                    <th key={header} className="px-3 py-3 font-medium">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => {
                  const weight = totalValue > 0 ? (Number(position.market_value || 0) / totalValue) * 100 : 0;
                  return (
                    <tr key={position.symbol} className="border-b border-border align-top last:border-b-0">
                      <td className="px-3 py-3 font-semibold text-foreground">{position.symbol}</td>
                      <td className="px-3 py-3 text-muted-foreground">{assetClass(position)}</td>
                      <td className="px-3 py-3 text-foreground">{position.qty}</td>
                      <td className="px-3 py-3 text-foreground">{money(position.avg_price)}</td>
                      <td className="px-3 py-3 text-foreground">{money(position.market_price)}</td>
                      <td className="px-3 py-3 text-foreground">{money(position.market_value)}</td>
                      <td className={`px-3 py-3 ${tone(position.unrealized_pnl)}`}>
                        {money(position.unrealized_pnl)}
                      </td>
                      <td className="px-3 py-3 text-foreground">{percent(weight)}</td>
                      <td className="px-3 py-3 text-muted-foreground">
                        {position.routing_mode || position.instrument_type || "Unavailable"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {positions.length === 0 ? (
            <p className="p-5 font-mono text-sm text-muted-foreground">
              `/paper/positions` returned no open positions.
            </p>
          ) : null}
          <EndpointError result={positionsResult} />
        </article>

        <aside className="space-y-4">
          <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <h2 className="text-lg font-semibold text-card-foreground">Asset Allocation</h2>
            <div className="mt-4 space-y-4">
              {classes.map((group) => {
                const value = positions
                  .filter((position) => assetClass(position) === group)
                  .reduce((total, position) => total + Number(position.market_value || 0), 0);
                const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;
                return (
                  <div key={group}>
                    <div className="mb-1 flex justify-between gap-3 font-mono text-xs">
                      <span className="capitalize text-muted-foreground">{group}</span>
                      <span className="text-foreground">{percent(weight)}</span>
                    </div>
                    <Bar value={weight} />
                  </div>
                );
              })}
            </div>
          </article>

          <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <h2 className="text-lg font-semibold text-card-foreground">Risk Status</h2>
            <dl className="mt-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Equity</dt>
                <dd className="text-foreground">{money(numberValue(risk.equity))}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Halted</dt>
                <dd className="text-foreground">
                  {String(Boolean(recordValue(risk.drawdown_breaker).halted))}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Current DD</dt>
                <dd className="text-foreground">
                  {percent(numberValue(recordValue(risk.drawdown_breaker).current_drawdown) * 100)}
                </dd>
              </div>
            </dl>
            <EndpointError result={riskResult} />
          </article>
        </aside>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <JsonPanel title="CEO Exposure" data={dataOr(exposureResult, null)} />
        <JsonPanel title="Metrics Summary" data={metrics} />
      </section>
      <EndpointError result={ordersResult} />
      <EndpointError result={metricsResult} />
      <EndpointError result={exposureResult} />
    </main>
  );
}
