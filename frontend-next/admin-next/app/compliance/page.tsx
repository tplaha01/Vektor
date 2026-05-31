import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Bar, EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
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

function statusClass(breached: boolean) {
  return breached
    ? "border-destructive/40 bg-destructive/10 text-destructive"
    : "border-primary/30 bg-primary/10 text-primary";
}

export default async function CompliancePage() {
  const [riskResult, metricsResult, positionsResult, ordersResult, controlHistoryResult, blockedTradesResult, badgesResult] =
    await Promise.all([
      safeFetchJson<JsonRecord>("/risk/status"),
      safeFetchJson<JsonRecord>("/api/admin/metrics/summary"),
      safeFetchJson<BackendPosition[]>("/paper/positions"),
      safeFetchJson<BackendOrder[]>("/paper/orders"),
      safeFetchJson<JsonRecord>("/api/admin/system/control-history?limit=25"),
      safeFetchJson<JsonRecord[]>("/fund/trades/blocked?limit=25"),
      safeFetchJson<JsonRecord>("/api/admin/system/status-badges"),
    ]);

  const risk = dataOr(riskResult, {});
  const metrics = dataOr(metricsResult, {});
  const positions = dataOr(positionsResult, []);
  const orders = dataOr(ordersResult, []);
  const blockedTrades = dataOr(blockedTradesResult, []);
  const controlHistoryData = dataOr(controlHistoryResult, {});
  const controlRows = Array.isArray(controlHistoryData)
    ? controlHistoryData
    : arrayValue<JsonRecord>(recordValue(controlHistoryData).events || recordValue(controlHistoryData).history);
  const drawdown = recordValue(risk.drawdown_breaker);
  const currentDrawdownPct = numberValue(drawdown.current_drawdown) * 100;
  const thresholdPct = numberValue(drawdown.max_drawdown_threshold) * 100;
  const totalValue = positions.reduce((total, position) => total + Number(position.market_value || 0), 0);
  const largestWeight = positions.reduce((max, position) => {
    const weight = totalValue > 0 ? (Number(position.market_value || 0) / totalValue) * 100 : 0;
    return Math.max(max, weight);
  }, 0);

  const rules = [
    {
      name: "Drawdown breaker",
      current: percent(currentDrawdownPct),
      limit: percent(thresholdPct),
      utilization: thresholdPct > 0 ? (currentDrawdownPct / thresholdPct) * 100 : 0,
      breached: Boolean(drawdown.halted),
    },
    {
      name: "Single position concentration",
      current: percent(largestWeight),
      limit: "50.00%",
      utilization: largestWeight / 50 * 100,
      breached: largestWeight > 50,
    },
    {
      name: "Open stop count",
      current: String(arrayValue(risk.open_stops).length),
      limit: "Informational",
      utilization: 0,
      breached: false,
    },
  ];

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /compliance
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Compliance
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Risk limits, blocked trades, runtime control history, and live portfolio
          concentration checks from backend services.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Equity" value={money(numberValue(metrics.total_equity))} />
        <StatCard label="Orders" value={orders.length} />
        <StatCard label="Blocked Trades" value={blockedTrades.length} />
        <StatCard label="Largest Weight" value={percent(largestWeight)} />
        <StatCard label="Risk Halted" value={String(Boolean(drawdown.halted))} />
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-card-foreground">Risk Limits Dashboard</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[58rem] border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                {["Rule", "Current", "Limit", "Utilization", "Status"].map((header) => (
                  <th key={header} className="px-3 py-3 font-medium">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.name} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-3 font-semibold text-foreground">{rule.name}</td>
                  <td className="px-3 py-3 text-foreground">{rule.current}</td>
                  <td className="px-3 py-3 text-foreground">{rule.limit}</td>
                  <td className="px-3 py-3">
                    <Bar value={rule.utilization} tone={rule.breached ? "bg-destructive" : "bg-primary"} />
                    <span className="mt-1 block text-muted-foreground">{percent(rule.utilization)}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 ${statusClass(rule.breached)}`}>
                      {rule.breached ? <AlertTriangle className="size-3" aria-hidden="true" /> : null}
                      {rule.breached ? "Breached" : "Clear"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <EndpointError result={riskResult} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <h2 className="text-xl font-semibold text-card-foreground">Runtime Control History</h2>
          <div className="mt-4 space-y-3">
            {controlRows.map((entry, index) => (
              <pre
                key={stringValue(entry.event_id, String(index))}
                className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground"
              >
                {JSON.stringify(entry, null, 2)}
              </pre>
            ))}
          </div>
          {controlRows.length === 0 ? (
            <p className="mt-4 font-mono text-sm text-muted-foreground">
              `/api/admin/system/control-history` returned no events.
            </p>
          ) : null}
          <EndpointError result={controlHistoryResult} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <h2 className="text-xl font-semibold text-card-foreground">Blocked Trades</h2>
          <div className="mt-4 space-y-3">
            {blockedTrades.map((entry, index) => (
              <pre
                key={String(recordValue(entry).decision_id || index)}
                className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground"
              >
                {JSON.stringify(entry, null, 2)}
              </pre>
            ))}
          </div>
          {blockedTrades.length === 0 ? (
            <p className="mt-4 font-mono text-sm text-muted-foreground">
              `/fund/trades/blocked` returned no blocked trades.
            </p>
          ) : null}
          <EndpointError result={blockedTradesResult} />
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <JsonPanel title="Risk Status" data={risk} />
        <JsonPanel title="System Status Badges" data={dataOr(badgesResult, {})} />
      </section>
      <EndpointError result={metricsResult} />
      <EndpointError result={positionsResult} />
      <EndpointError result={ordersResult} />
      <EndpointError result={badgesResult} />
    </main>
  );
}
