import { Database, GitBranch } from "lucide-react";
import { EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  dataOr,
  recordValue,
  safeFetchJson,
  stringValue,
  type JsonRecord,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const [statsResult, eventsResult, lineageResult, monitorKnowledgeResult] = await Promise.all([
    safeFetchJson<JsonRecord>("/fund/knowledge/stats"),
    safeFetchJson<JsonRecord>("/fund/knowledge/events?limit=100"),
    safeFetchJson<JsonRecord>("/fund/knowledge/lineage?limit=50"),
    safeFetchJson<JsonRecord>("/api/monitor/knowledge"),
  ]);

  const stats = dataOr(statsResult, {});
  const eventData = dataOr(eventsResult, {});
  const lineageData = dataOr(lineageResult, {});
  const events = Array.isArray(eventData)
    ? eventData
    : arrayValue<JsonRecord>(recordValue(eventData).events || recordValue(eventData).items);
  const lineage = Array.isArray(lineageData)
    ? lineageData
    : arrayValue<JsonRecord>(recordValue(lineageData).lineage || recordValue(lineageData).items);

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /memory
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Memory
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Knowledge graph stats, recent events, lineage, and monitoring state from
          existing backend memory endpoints.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Events" value={String(stats.event_count ?? stats.events ?? events.length)} />
        <StatCard label="Lineage Rows" value={lineage.length} />
        <StatCard label="Namespaces" value={arrayValue(stats.namespaces).length || "Unavailable"} />
        <StatCard label="Recent Events" value={events.length} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Database className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">Recent Knowledge Events</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[68rem] border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                  {["ID", "Namespace", "Type", "Timestamp", "Payload"].map((header) => (
                    <th key={header} className="px-3 py-3 font-medium">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((event, index) => (
                  <tr key={stringValue(event.event_id, String(index))} className="border-b border-border align-top last:border-b-0">
                    <td className="px-3 py-3 text-primary">{stringValue(event.event_id, stringValue(event.id))}</td>
                    <td className="px-3 py-3 text-muted-foreground">{stringValue(event.namespace)}</td>
                    <td className="px-3 py-3 text-muted-foreground">{stringValue(event.event_type, stringValue(event.type))}</td>
                    <td className="px-3 py-3 text-muted-foreground">{stringValue(event.created_at, stringValue(event.timestamp))}</td>
                    <td className="px-3 py-3 text-muted-foreground">
                      <pre className="max-h-32 overflow-auto whitespace-pre-wrap">
                        {JSON.stringify(event, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {events.length === 0 ? (
            <p className="mt-4 font-mono text-sm text-muted-foreground">
              `/fund/knowledge/events` returned no events.
            </p>
          ) : null}
          <EndpointError result={eventsResult} />
        </article>

        <aside className="space-y-4">
          <JsonPanel title="Knowledge Stats" data={stats} />
          <JsonPanel title="Monitor Knowledge" data={dataOr(monitorKnowledgeResult, {})} />
        </aside>
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex items-center gap-2">
          <GitBranch className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-card-foreground">Lineage</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {lineage.map((row, index) => (
            <pre
              key={stringValue(row.lineage_id, String(index))}
              className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground"
            >
              {JSON.stringify(row, null, 2)}
            </pre>
          ))}
        </div>
        {lineage.length === 0 ? (
          <p className="font-mono text-sm text-muted-foreground">
            `/fund/knowledge/lineage` returned no lineage rows.
          </p>
        ) : null}
        <EndpointError result={lineageResult} />
      </section>

      <EndpointError result={statsResult} />
      <EndpointError result={monitorKnowledgeResult} />
    </main>
  );
}
