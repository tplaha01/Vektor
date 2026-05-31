import { Cpu, Gauge, RadioTower } from "lucide-react";
import { EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  dataOr,
  numberValue,
  recordValue,
  safeFetchJson,
  stringValue,
  type JsonRecord,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("healthy") || normalized.includes("ready") || normalized === "true") {
    return "border-primary/30 bg-primary/10 text-primary";
  }
  if (normalized.includes("training") || normalized.includes("provider")) {
    return "border-secondary/30 bg-secondary/10 text-secondary";
  }
  return "border-border bg-muted text-muted-foreground";
}

export default async function CoreEnginePage() {
  const [mlStatus, statusBadges, pipelineStatus, features, reports, streamStatus] =
    await Promise.all([
      safeFetchJson<JsonRecord>("/ml/status"),
      safeFetchJson<JsonRecord>("/api/admin/system/status-badges"),
      safeFetchJson<JsonRecord>("/data-pipeline/status"),
      safeFetchJson<JsonRecord>("/data-pipeline/features/SPY"),
      safeFetchJson<JsonRecord>("/api/admin/reports?limit=8"),
      safeFetchJson<JsonRecord>("/fund/stream/status"),
    ]);

  const ml = dataOr(mlStatus, {});
  const lgbm = recordValue(ml.lgbm);
  const core = recordValue(ml.core_engine);
  const badges = dataOr(statusBadges, {});
  const llm = recordValue(badges.llm_agent_health);
  const roles = arrayValue<JsonRecord>(llm.by_role);
  const pipeline = dataOr(pipelineStatus, {});
  const featureData = dataOr(features, {});
  const reportRows = arrayValue<JsonRecord>(recordValue(dataOr(reports, {})).reports);

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /core-engine
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Core Engine
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          ML, signal, role-routing, and feature-pipeline status from TradingBot backend
          endpoints.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Model Ready" value={String(Boolean(lgbm.ready))} />
        <StatCard label="Feature Count" value={numberValue(lgbm.features)} />
        <StatCard label="Core Profile" value={stringValue(core.active_profile)} />
        <StatCard label="Stream Status" value={stringValue(recordValue(dataOr(streamStatus, {})).status)} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Cpu className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">ML Runtime</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                  {["Field", "Value"].map((header) => (
                    <th key={header} className="px-3 py-3 font-medium">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(lgbm).map(([key, value]) => (
                  <tr key={key} className="border-b border-border last:border-b-0">
                    <td className="px-3 py-3 text-muted-foreground">{key}</td>
                    <td className="px-3 py-3 text-foreground">{String(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <EndpointError result={mlStatus} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <RadioTower className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">LLM Role Routing</h2>
          </div>
          <div className="space-y-2">
            {roles.length ? (
              roles.map((role) => {
                const status = stringValue(role.status);
                return (
                  <div key={stringValue(role.role)} className="rounded-md border border-border bg-background/50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <span className="font-mono text-xs font-semibold text-foreground">
                        {stringValue(role.role)}
                      </span>
                      <span className={`rounded border px-2 py-1 font-mono text-xs ${statusClass(status)}`}>
                        {status}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-xs text-muted-foreground">
                      {stringValue(role.provider)} / {stringValue(role.model)} / {stringValue(role.reason)}
                    </p>
                  </div>
                );
              })
            ) : (
              <p className="font-mono text-sm text-muted-foreground">
                `/api/admin/system/status-badges` returned no role health rows.
              </p>
            )}
          </div>
          <EndpointError result={statusBadges} />
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <JsonPanel title="Data Pipeline Status" data={pipeline} />
        <JsonPanel title="SPY Feature Snapshot" data={featureData} />
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex items-center gap-2">
          <Gauge className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-card-foreground">Recent Research Reports</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[58rem] border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                {["Report", "Symbol", "Status", "Created", "Agent"].map((header) => (
                  <th key={header} className="px-3 py-3 font-medium">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reportRows.map((report, index) => (
                <tr key={stringValue(report.report_id, String(index))} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-3 font-semibold text-foreground">{stringValue(report.title, stringValue(report.report_id))}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.symbol)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.status)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.created_at)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.agent_id)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {reportRows.length === 0 ? (
          <p className="mt-4 font-mono text-sm text-muted-foreground">
            `/api/admin/reports` returned no reports.
          </p>
        ) : null}
        <EndpointError result={reports} />
      </section>
    </main>
  );
}
