import { Brain, RadioTower, RefreshCw } from "lucide-react";
import { EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  dataOr,
  numberValue,
  recordValue,
  safeFetchJson,
  stringValue,
  type JsonRecord,
  type JsonValue,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("running") || normalized.includes("healthy") || normalized.includes("started")) {
    return "border-primary/30 bg-primary/10 text-primary";
  }
  if (normalized.includes("idle") || normalized.includes("pending")) {
    return "border-secondary/30 bg-secondary/10 text-secondary";
  }
  return "border-destructive/40 bg-destructive/10 text-destructive";
}

function rowKey(row: JsonRecord, index: number, prefix: string) {
  const id = stringValue(row.task_id, stringValue(row.agent_id, stringValue(row.id, "")));
  const timestamp = stringValue(row.created_at, stringValue(row.updated_at, stringValue(row.completed_at, "")));
  return `${prefix}-${id || "row"}-${timestamp || index}-${index}`;
}

export default async function AgentsPage() {
  const [workers, activeTasks, taskHistory, autopilot, debugStream, monitorAgents, hierarchy] =
    await Promise.all([
      safeFetchJson<JsonValue>("/fund/agents/workers/status"),
      safeFetchJson<JsonRecord[]>("/fund/agents/tasks/active"),
      safeFetchJson<JsonRecord[]>("/fund/agents/tasks/history?limit=40"),
      safeFetchJson<JsonRecord>("/fund/agents/autopilot/status"),
      safeFetchJson<JsonRecord>("/debug/websocket-stream"),
      safeFetchJson<JsonValue>("/api/monitor/agents"),
      safeFetchJson<JsonValue>("/api/monitor/agents/hierarchy"),
    ]);

  const activeRows = dataOr(activeTasks, []);
  const historyRows = dataOr(taskHistory, []);
  const workerRows = arrayValue<JsonRecord>(dataOr(workers, []));
  const autopilotData = dataOr(autopilot, {});
  const debugData = dataOr(debugStream, {});

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /agents
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Agent Orchestration
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Worker, task, autopilot, hierarchy, and websocket status from the backend
          orchestration services.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Workers" value={workerRows.length || "Unavailable"} />
        <StatCard label="Active Tasks" value={activeRows.length} />
        <StatCard label="Task History" value={historyRows.length} />
        <StatCard
          label="WS Clients"
          value={numberValue(debugData.active_connections)}
          sub={`${numberValue(debugData.event_buffer_size)} buffered events`}
        />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-3">
          {workerRows.length ? (
            workerRows.map((worker, index) => {
              const status = stringValue(worker.status, stringValue(worker.state));
              return (
                <article
                  key={stringValue(worker.agent_id, stringValue(worker.name, String(index)))}
                  className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-card-foreground">
                        {stringValue(worker.name, stringValue(worker.agent_id))}
                      </h2>
                      <p className="mt-1 font-mono text-xs text-muted-foreground">
                        {stringValue(worker.role, stringValue(worker.kind))}
                      </p>
                    </div>
                    <span className={`inline-flex items-center gap-2 rounded border px-2 py-1 font-mono text-xs ${statusTone(status)}`}>
                      <span className="size-2 rounded-full bg-current" />
                      {status}
                    </span>
                  </div>
                  <pre className="mt-4 max-h-52 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
                    {JSON.stringify(worker, null, 2)}
                  </pre>
                </article>
              );
            })
          ) : (
            <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
              <p className="font-mono text-sm text-muted-foreground">
                `/fund/agents/workers/status` returned no worker rows.
              </p>
              <pre className="mt-4 overflow-auto rounded-md border border-border bg-background/70 p-3 font-mono text-xs text-muted-foreground">
                {JSON.stringify(dataOr(workers, null), null, 2)}
              </pre>
            </article>
          )}
          <EndpointError result={workers} />
        </div>

        <div className="space-y-4">
          <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
            <div className="mb-4 flex items-center gap-2">
              <RefreshCw className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-card-foreground">Active Task Feed</h2>
            </div>
            <div className="max-h-[30rem] space-y-2 overflow-y-auto pr-1">
              {activeRows.length ? (
                activeRows.map((task, index) => (
                  <pre
                    key={rowKey(task, index, "active")}
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
            <div className="mb-4 flex items-center gap-2">
              <RadioTower className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-card-foreground">Recent Task History</h2>
            </div>
            <div className="max-h-[30rem] space-y-2 overflow-y-auto pr-1">
              {historyRows.slice(0, 12).map((task, index) => (
                <pre
                  key={rowKey(task, index, "history")}
                  className="overflow-auto rounded-md border border-border bg-background/50 p-3 font-mono text-xs text-muted-foreground"
                >
                  {JSON.stringify(task, null, 2)}
                </pre>
              ))}
            </div>
            {historyRows.length === 0 ? (
              <p className="font-mono text-sm text-muted-foreground">
                `/fund/agents/tasks/history` returned no task history.
              </p>
            ) : null}
            <EndpointError result={taskHistory} />
          </article>
        </div>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <JsonPanel title="Autopilot Status" data={autopilotData} />
        <JsonPanel title="Monitor Agents" data={dataOr(monitorAgents, null)} />
        <JsonPanel title="Agent Hierarchy" data={dataOr(hierarchy, null)} />
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex items-center gap-2">
          <Brain className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-card-foreground">Websocket Debug Stream</h2>
        </div>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
          {JSON.stringify(debugData, null, 2)}
        </pre>
        <EndpointError result={debugStream} />
      </section>
    </main>
  );
}
