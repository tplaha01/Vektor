import { Activity, Power, RadioTower, ShieldAlert, Workflow } from "lucide-react";
import { runAdminAction } from "@/app/admin-actions";
import { EndpointError, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  dataOr,
  formatDateTime,
  money,
  numberValue,
  recordValue,
  safeFetchJson,
  stringValue,
  type BackendPosition,
  type JsonRecord,
  type JsonValue,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("healthy") || normalized.includes("paper") || normalized.includes("provider")) {
    return "border-primary/30 bg-primary/10 text-primary";
  }
  if (normalized.includes("degraded") || normalized.includes("warning")) {
    return "border-secondary/30 bg-secondary/10 text-secondary";
  }
  return "border-destructive/40 bg-destructive/10 text-destructive";
}

export default async function WarRoomPage() {
  const [
    health,
    metrics,
    statusBadges,
    performance,
    positionsResult,
    activeTasks,
    pendingDecisions,
    workerStatus,
  ] = await Promise.all([
    safeFetchJson<JsonRecord>("/health"),
    safeFetchJson<JsonRecord>("/api/admin/metrics/summary"),
    safeFetchJson<JsonRecord>("/api/admin/system/status-badges"),
    safeFetchJson<JsonRecord>("/fund/performance/summary"),
    safeFetchJson<BackendPosition[]>("/paper/positions"),
    safeFetchJson<JsonRecord[]>("/fund/agents/tasks/active"),
    safeFetchJson<JsonRecord[]>("/fund/decisions/pending"),
    safeFetchJson<JsonValue>("/fund/agents/workers/status"),
  ]);

  const metricsData = dataOr(metrics, {});
  const performanceData = dataOr(performance, {});
  const latestSnapshot = recordValue(performanceData.latest_snapshot);
  const positions = dataOr(positionsResult, []);
  const activeTaskRows = dataOr(activeTasks, []);
  const decisionRows = dataOr(pendingDecisions, []);
  const statusData = dataOr(statusBadges, {});
  const totalPositionValue = positions.reduce(
    (total, position) => total + Number(position.market_value || 0),
    0,
  );

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="flex flex-col gap-6 border-b border-border pb-6 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            /war-room
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
            War Room Command Center
          </h1>
          <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
            Operator view backed by TradingBot health, portfolio, orchestration, and
            runtime control endpoints.
          </p>
        </div>
        <span className="inline-flex h-fit items-center gap-2 rounded border border-primary/30 bg-primary/10 px-3 py-2 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary">
          <Activity className="size-4" aria-hidden="true" />
          {formatDateTime(latestSnapshot.recorded_at)}
        </span>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total Equity" value={money(numberValue(metricsData.total_equity))} />
        <StatCard label="Cash" value={money(numberValue(latestSnapshot.cash))} />
        <StatCard label="Market Value" value={money(numberValue(latestSnapshot.market_value))} />
        <StatCard
          label="Unrealized P&L"
          value={money(numberValue(metricsData.unrealized_pnl))}
          tone={numberValue(metricsData.unrealized_pnl) >= 0 ? "text-primary" : "text-destructive"}
        />
        <StatCard
          label="Drawdown"
          value={`${numberValue(metricsData.current_drawdown).toFixed(2)}%`}
          sub={`Limit ${numberValue(metricsData.max_drawdown_threshold).toFixed(2)}%`}
        />
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold text-card-foreground">Portfolio Heatmap</h2>
          <div className="font-mono text-xs text-muted-foreground">
            Current Value: {money(totalPositionValue)}
          </div>
        </div>
        {positions.length ? (
          <div className="flex h-14 overflow-hidden rounded-md border border-border bg-background">
            {positions.map((position) => {
              const pnl = Number(position.unrealized_pnl || 0);
              const width = totalPositionValue > 0 ? (Number(position.market_value || 0) / totalPositionValue) * 100 : 0;
              return (
                <div
                  key={position.symbol}
                  title={`${position.symbol}: ${money(Number(position.market_value || 0))} / ${money(pnl)} unrealized P&L`}
                  className={`flex min-w-[2rem] items-center justify-center border-r border-background/70 px-2 font-mono text-xs font-semibold text-background last:border-r-0 ${
                    pnl >= 0 ? "bg-primary/75" : "bg-destructive/75"
                  }`}
                  style={{ width: `${Math.max(1, width)}%` }}
                >
                  {position.symbol}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="font-mono text-sm text-muted-foreground">
            `/paper/positions` returned no open positions.
          </p>
        )}
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="min-w-0 space-y-4">
          {Object.entries(statusData).map(([key, value]) => {
            const row = recordValue(value);
            const status = stringValue(row.status, "Unavailable");
            return (
              <article key={key} className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-card-foreground">
                    {stringValue(row.label, key.replaceAll("_", " "))}
                  </h2>
                  <span className={`rounded border px-2 py-1 font-mono text-xs ${statusTone(status)}`}>
                    {status}
                  </span>
                </div>
                <p className="mt-3 font-mono text-xs leading-5 text-muted-foreground">
                  {stringValue(row.reason, "No reason field returned.")}
                </p>
              </article>
            );
          })}
          <EndpointError result={statusBadges} />
        </div>

        <div className="min-w-0 space-y-4">
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <div className="flex items-center gap-2">
              <Workflow className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold text-card-foreground">Active Tasks</h2>
            </div>
            <div className="mt-4 space-y-3">
              {activeTaskRows.length ? (
                activeTaskRows.map((task, index) => (
                  <pre
                    key={String(task.task_id || task.id || index)}
                    className="overflow-auto rounded-md border border-border bg-background/50 p-3 font-mono text-xs text-muted-foreground"
                  >
                    {JSON.stringify(task, null, 2)}
                  </pre>
                ))
              ) : (
                <p className="font-mono text-sm text-muted-foreground">
                  `/fund/agents/tasks/active` returned no active tasks.
                </p>
              )}
            </div>
            <EndpointError result={activeTasks} />
          </article>

          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <div className="flex items-center gap-2">
              <ShieldAlert className="size-4 text-secondary" aria-hidden="true" />
              <h2 className="text-base font-semibold text-card-foreground">Pending Decisions</h2>
            </div>
            <div className="mt-4 space-y-3">
              {decisionRows.length ? (
                decisionRows.map((decision, index) => (
                  <pre
                    key={String(decision.decision_id || decision.id || index)}
                    className="overflow-auto rounded-md border border-border bg-background/50 p-3 font-mono text-xs text-muted-foreground"
                  >
                    {JSON.stringify(decision, null, 2)}
                  </pre>
                ))
              ) : (
                <p className="font-mono text-sm text-muted-foreground">
                  `/fund/decisions/pending` returned no pending approvals.
                </p>
              )}
            </div>
            <EndpointError result={pendingDecisions} />
          </article>
        </div>

        <aside className="min-w-0 space-y-4">
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <div className="flex items-center gap-2">
              <RadioTower className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold text-card-foreground">Runtime Controls</h2>
            </div>
            <div className="mt-4 grid gap-2">
              {[
                ["pause", "Pause Runtime"],
                ["resume", "Resume Runtime"],
                ["autopilot_kick", "Kick Autopilot"],
                ["functional_verify", "Run Functional Verify"],
                ["clear_halt", "Clear Halt"],
              ].map(([action, label]) => (
                <form key={action} action={runAdminAction}>
                  <input type="hidden" name="action" value={action} />
                  <button className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-border bg-background/50 px-3 py-2 font-mono text-xs text-foreground hover:border-primary/50">
                    <Power className="size-3 text-primary" aria-hidden="true" />
                    {label}
                  </button>
                </form>
              ))}
            </div>
          </article>

          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <h2 className="text-base font-semibold text-card-foreground">Worker Status</h2>
            <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
              {JSON.stringify(dataOr(workerStatus, []), null, 2)}
            </pre>
            <EndpointError result={workerStatus} />
          </article>

          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <h2 className="text-base font-semibold text-card-foreground">Backend Health</h2>
            <div className="mt-4 space-y-2 font-mono text-xs text-muted-foreground">
              <p>Status: {stringValue(recordValue(dataOr(health, {})).status)}</p>
              <p>Version: {stringValue(recordValue(dataOr(health, {})).version)}</p>
              <p>Watchlist: {arrayValue(recordValue(dataOr(health, {})).watchlist).join(", ")}</p>
            </div>
            <EndpointError result={health} />
          </article>
        </aside>
      </section>
    </main>
  );
}
