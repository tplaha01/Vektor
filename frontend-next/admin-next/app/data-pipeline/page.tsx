import { Database, Server } from "lucide-react";
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

export default async function DataPipelinePage() {
  const [statusResult, storageResult, spyFeaturesResult, warehouseResult, snapshotsResult] =
    await Promise.all([
      safeFetchJson<JsonRecord>("/data-pipeline/status"),
      safeFetchJson<JsonRecord>("/data-pipeline/storage-estimate"),
      safeFetchJson<JsonRecord>("/data-pipeline/features/SPY"),
      safeFetchJson<JsonRecord>("/data-pipeline/warehouse/data_market_bars?limit=20"),
      safeFetchJson<JsonRecord>("/fund/performance/snapshots?limit=20"),
    ]);

  const status = dataOr(statusResult, {});
  const storage = dataOr(storageResult, {});
  const features = dataOr(spyFeaturesResult, {});
  const warehouse = dataOr(warehouseResult, {});
  const snapshots = dataOr(snapshotsResult, {});
  const warehouseRows = arrayValue(recordValue(warehouse).rows);
  const performanceRows = Array.isArray(snapshots) ? snapshots : arrayValue(recordValue(snapshots).snapshots);

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /data-pipeline
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Data Pipeline
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Ingestion, warehouse, feature, and performance telemetry from existing
          TradingBot data pipeline endpoints.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Running" value={String(Boolean(status.running))} />
        <StatCard label="Symbols" value={arrayValue(status.configured_symbols).length} />
        <StatCard label="Warehouse Rows" value={warehouseRows.length} />
        <StatCard label="Snapshots" value={performanceRows.length} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Server className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Provider Health</h2>
          </div>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
            {JSON.stringify(status.provider_health || status, null, 2)}
          </pre>
          <EndpointError result={statusResult} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Database className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Storage Estimate</h2>
          </div>
          <dl className="space-y-3 font-mono text-xs">
            {Object.entries(storage).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3 rounded-md border border-border bg-background/50 p-3">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="text-foreground">
                  {typeof value === "number" ? numberValue(value).toLocaleString() : String(value)}
                </dd>
              </div>
            ))}
          </dl>
          <EndpointError result={storageResult} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <h2 className="text-lg font-semibold text-card-foreground">SPY Latest Features</h2>
          <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
            {JSON.stringify(features, null, 2)}
          </pre>
          <EndpointError result={spyFeaturesResult} />
        </article>
      </section>

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <h2 className="text-xl font-semibold text-card-foreground">Warehouse Rows</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[68rem] border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                {["Index", "Symbol", "Timestamp", "Payload"].map((header) => (
                  <th key={header} className="px-3 py-3 font-medium">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {warehouseRows.map((row, index) => {
                const record = recordValue(row);
                return (
                  <tr key={String(record.id || index)} className="border-b border-border last:border-b-0">
                    <td className="px-3 py-3 text-muted-foreground">{index + 1}</td>
                    <td className="px-3 py-3 text-foreground">{stringValue(record.symbol)}</td>
                    <td className="px-3 py-3 text-muted-foreground">{stringValue(record.timestamp, stringValue(record.ts))}</td>
                    <td className="px-3 py-3 text-muted-foreground">
                      <pre className="max-h-28 overflow-auto whitespace-pre-wrap">
                        {JSON.stringify(record, null, 2)}
                      </pre>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {warehouseRows.length === 0 ? (
          <p className="mt-4 font-mono text-sm text-muted-foreground">
            `/data-pipeline/warehouse/data_market_bars` returned no rows.
          </p>
        ) : null}
        <EndpointError result={warehouseResult} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <JsonPanel title="Pipeline Status" data={status} />
        <JsonPanel title="Performance Snapshot Feed" data={snapshots} />
      </section>
      <EndpointError result={snapshotsResult} />
    </main>
  );
}
