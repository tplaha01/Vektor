import { PlugZap, Save, SlidersHorizontal } from "lucide-react";
import { runAdminAction, updatePaperBrokerCapital } from "@/app/admin-actions";
import { EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  dataOr,
  recordValue,
  safeFetchJson,
  stringValue,
  type JsonRecord,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [runtimeResult, badgesResult, mlResult, streamResult, monitorAgentsResult] =
    await Promise.all([
      safeFetchJson<JsonRecord>("/api/admin/system/runtime/control"),
      safeFetchJson<JsonRecord>("/api/admin/system/status-badges"),
      safeFetchJson<JsonRecord>("/ml/status"),
      safeFetchJson<JsonRecord>("/fund/stream/status"),
      safeFetchJson<JsonRecord>("/api/monitor/agents"),
    ]);

  const runtime = dataOr(runtimeResult, {});
  const badges = dataOr(badgesResult, {});
  const ml = dataOr(mlResult, {});
  const executionMode = recordValue(badges.execution_mode);
  const dataSource = recordValue(badges.data_source);
  const orchestration = recordValue(badges.orchestration);

  return (
    <main className="min-h-screen pb-12">
      <div className="grid gap-0 xl:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-border p-5 xl:block">
          <nav className="sticky top-6 space-y-2 font-mono text-xs text-muted-foreground">
            {["runtime", "controls", "capital", "providers"].map((id) => (
              <a key={id} href={`#${id}`} className="block rounded-md border border-border bg-card/60 px-3 py-2 hover:text-primary">
                {id.toUpperCase()}
              </a>
            ))}
          </nav>
        </aside>

        <div className="p-5 lg:p-8">
          <div className="border-b border-border pb-6">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              /settings
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Settings
            </h1>
            <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
              Runtime control, provider state, OpenClaw health, and paper-broker capital
              actions mapped to existing backend endpoints.
            </p>
          </div>

          <section id="runtime" className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Runtime" value={stringValue(runtime.status, stringValue(runtime.state))} />
            <StatCard label="Execution" value={stringValue(executionMode.status)} />
            <StatCard label="Data Source" value={stringValue(dataSource.status)} />
            <StatCard label="Orchestration" value={stringValue(orchestration.status)} />
          </section>

          <section id="controls" className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <div className="mb-4 flex items-center gap-2">
              <SlidersHorizontal className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-card-foreground">Runtime Controls</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {[
                ["pause", "Pause Runtime"],
                ["resume", "Resume Runtime"],
                ["clear_halt", "Clear Halt"],
                ["autopilot_kick", "Kick Autopilot"],
                ["functional_verify", "Functional Verify"],
                ["data_integrity_drill", "Data Integrity Drill"],
                ["deterministic_recover", "Recover Deterministic ML"],
              ].map(([action, label]) => (
                <form key={action} action={runAdminAction}>
                  <input type="hidden" name="action" value={action} />
                  <button className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-border bg-background/50 px-3 font-mono text-xs text-foreground hover:border-primary/50">
                    <Save className="size-3 text-primary" aria-hidden="true" />
                    {label}
                  </button>
                </form>
              ))}
            </div>
            <EndpointError result={runtimeResult} />
          </section>

          <section id="capital" className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <div className="mb-4 flex items-center gap-2">
              <PlugZap className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-card-foreground">Paper Broker Capital</h2>
            </div>
            <form action={updatePaperBrokerCapital} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
                <span>Top Up USD</span>
                <input
                  name="amount_usd"
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none"
                />
              </label>
              <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
                <span>Reason</span>
                <input
                  name="reason"
                  defaultValue="operator_adjustment"
                  required
                  className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none"
                />
              </label>
              <button className="mt-auto h-10 rounded-md bg-primary px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary-foreground">
                Apply
              </button>
            </form>
          </section>

          <section id="providers" className="mt-6 grid gap-4 xl:grid-cols-2">
            <JsonPanel title="ML Status" data={ml} />
            <JsonPanel title="Stream Status" data={dataOr(streamResult, {})} />
            <JsonPanel title="Agent Monitor" data={dataOr(monitorAgentsResult, {})} />
          </section>

          <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <h2 className="text-xl font-semibold text-card-foreground">Status Badges</h2>
            <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
              {JSON.stringify(badges, null, 2)}
            </pre>
          </section>

          <EndpointError result={badgesResult} />
          <EndpointError result={mlResult} />
          <EndpointError result={streamResult} />
          <EndpointError result={monitorAgentsResult} />
        </div>
      </div>
    </main>
  );
}
