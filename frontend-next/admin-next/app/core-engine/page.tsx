import {
  Activity,
  BrainCircuit,
  Cpu,
  DatabaseZap,
  Gauge,
  Network,
  RadioTower,
  ShieldCheck,
} from "lucide-react";
import { EndpointError, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  boolValue,
  dataOr,
  formatDateTime,
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
  if (
    normalized.includes("training") ||
    normalized.includes("provider") ||
    normalized.includes("paper") ||
    normalized.includes("live")
  ) {
    return "border-secondary/30 bg-secondary/10 text-secondary";
  }
  return "border-border bg-muted text-muted-foreground";
}

function parseRecord(value: unknown): JsonRecord {
  if (typeof value !== "string" || !value.trim()) return recordValue(value);
  try {
    return recordValue(JSON.parse(value));
  } catch {
    return {};
  }
}

function compactNumber(value: unknown) {
  const numeric = numberValue(value, Number.NaN);
  if (!Number.isFinite(numeric)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(numeric);
}

function score(value: unknown) {
  const numeric = numberValue(value, Number.NaN);
  if (!Number.isFinite(numeric)) return "Unavailable";
  return `${(numeric * 100).toFixed(1)}%`;
}

function signedPercent(value: unknown) {
  const numeric = numberValue(value, Number.NaN);
  if (!Number.isFinite(numeric)) return "Unavailable";
  const formatted = `${(numeric * 100).toFixed(2)}%`;
  return numeric > 0 ? `+${formatted}` : formatted;
}

function listValue(value: unknown) {
  return arrayValue(value)
    .map((item) => stringValue(item, ""))
    .filter(Boolean)
    .join(", ");
}

function pathTail(value: unknown) {
  const text = stringValue(value, "");
  if (!text) return "Unavailable";
  return text.split(/[\\/]/).filter(Boolean).pop() ?? text;
}

function SignalRow({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="min-w-0 border-b border-border py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
        <span className="min-w-0 break-words text-right font-mono text-sm font-semibold text-foreground">
          {value}
        </span>
      </div>
      {sub ? (
        <p className="mt-1 break-words font-mono text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
          {sub}
        </p>
      ) : null}
    </div>
  );
}

function WeightBar({ label, value }: { label: string; value: unknown }) {
  const numeric = Math.max(0, Math.min(1, numberValue(value)));

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 font-mono text-xs">
        <span className="uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
        <span className="font-semibold text-foreground">{score(numeric)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full border border-border bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${numeric * 100}%` }} />
      </div>
    </div>
  );
}

export default async function CoreEnginePage() {
  const [mlStatus, statusBadges, pipelineStatus, features, reports, streamStatus] =
    await Promise.all([
      safeFetchJson<JsonRecord>("/ml/status"),
      safeFetchJson<JsonRecord>("/api/admin/system/status-badges"),
      safeFetchJson<JsonRecord>("/data-pipeline/status"),
      safeFetchJson<JsonRecord>("/data-pipeline/features/SPY"),
      safeFetchJson<JsonRecord>("/api/research/reports?limit=8"),
      safeFetchJson<JsonRecord>("/fund/stream/status"),
    ]);

  const ml = dataOr(mlStatus, {});
  const lgbm = recordValue(ml.lgbm);
  const core = recordValue(ml.core_engine);
  const badges = dataOr(statusBadges, {});
  const dataSource = recordValue(badges.data_source);
  const executionMode = recordValue(badges.execution_mode);
  const llm = recordValue(badges.llm_agent_health);
  const roles = arrayValue<JsonRecord>(llm.by_role);
  const pipeline = dataOr(pipelineStatus, {});
  const pipelineCounts = recordValue(pipeline.counts);
  const pipelineStream = recordValue(pipeline.stream);
  const latestRun = recordValue(pipeline.latest_run);
  const latestRunCounts = parseRecord(latestRun.counts_json);
  const providerRows = arrayValue<JsonRecord>(dataSource.providers);
  const featureRows = arrayValue<JsonRecord>(recordValue(dataOr(features, {})).items);
  const primaryFeature = recordValue(featureRows[0]);
  const primaryFeatureMetrics = recordValue(primaryFeature.features);
  const primaryFeatureMeta = recordValue(primaryFeature.metadata);
  const reportRows = arrayValue<JsonRecord>(recordValue(dataOr(reports, {})).reports);
  const fundStream = dataOr(streamStatus, {});
  const profiles = arrayValue<JsonRecord>(core.available_profiles);
  const activeProfileName = stringValue(core.active_profile);
  const activeProfile =
    profiles.find((profile) => stringValue(profile.name, "").toLowerCase() === activeProfileName.toLowerCase()) ??
    recordValue(profiles[0]);
  const activeWeights = recordValue(activeProfile.stack_weights);
  const streamLive = boolValue(pipelineStream.started) && boolValue(pipelineStream.subscribed);
  const modelReady = boolValue(lgbm.ready);
  const executionStatus = stringValue(executionMode.status);
  const featureSet = stringValue(primaryFeatureMeta.feature_set);

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /core-engine
        </p>
        <div className="mt-3 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Core Engine
            </h1>
            <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
              Model contract, stream freshness, feature lineage, policy posture.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 font-mono text-xs">
            <span className={`rounded border px-3 py-2 ${statusClass(modelReady ? "ready" : "blocked")}`}>
              MODEL {modelReady ? "READY" : "BLOCKED"}
            </span>
            <span className={`rounded border px-3 py-2 ${statusClass(streamLive ? "live" : "stale")}`}>
              STREAM {streamLive ? "LIVE" : "CHECK"}
            </span>
            <span className={`rounded border px-3 py-2 ${statusClass(executionStatus)}`}>
              {executionStatus.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Core Profile"
          value={activeProfileName}
          sub={`request ${stringValue(core.default_request_profile)} / base ${stringValue(core.default_base_profile)}`}
        />
        <StatCard
          label="Feature Fabric"
          value={compactNumber(pipelineCounts.data_feature_vectors)}
          sub={`${compactNumber(lgbm.features)} model features / ${featureSet}`}
        />
        <StatCard
          label="Market Mode"
          value={stringValue(pipeline.mode)}
          sub={`REST cycles ${boolValue(pipeline.scheduled_rest_cycles_enabled) ? "enabled" : "disabled"}`}
        />
        <StatCard
          label="Event Bus"
          value={compactNumber(recordValue(fundStream).event_count)}
          sub={stringValue(recordValue(fundStream).latest_stream_id)}
        />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Cpu className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">Decision Contract</h2>
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="min-w-0">
              <SignalRow label="Active model" value={modelReady ? "Pinned" : "Unavailable"} sub={pathTail(lgbm.path)} />
              <SignalRow label="Training lock" value={boolValue(lgbm.training) ? "Training" : "Stable"} />
              <SignalRow label="Minimum confidence" value={score(activeProfile.min_confidence)} />
              <SignalRow label="Expected utility floor" value={score(activeProfile.min_expected_utility)} />
              <SignalRow
                label="Aggregate uncertainty cap"
                value={score(activeProfile.max_aggregate_uncertainty)}
              />
            </div>
            <div className="min-w-0 space-y-4">
              <WeightBar label="Technical" value={activeWeights.technical} />
              <WeightBar label="Fundamental" value={activeWeights.fundamental} />
              <WeightBar label="Sentiment" value={activeWeights.sentiment} />
              <div className="grid grid-cols-2 gap-3 border-t border-border pt-4 font-mono text-xs">
                <div>
                  <p className="uppercase tracking-[0.14em] text-muted-foreground">Fundamentals</p>
                  <p className="mt-1 font-semibold text-foreground">
                    {boolValue(activeProfile.require_fundamentals) ? "Required" : "Optional"}
                  </p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.14em] text-muted-foreground">Sentiment</p>
                  <p className="mt-1 font-semibold text-foreground">
                    {boolValue(activeProfile.require_sentiment) ? "Required" : "Optional"}
                  </p>
                </div>
              </div>
            </div>
          </div>
          <EndpointError result={mlStatus} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <DatabaseZap className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">Stream-First Market Fabric</h2>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="min-w-0">
              <SignalRow label="Stream state" value={streamLive ? "Started / subscribed" : "Not live"} />
              <SignalRow label="Feed" value={stringValue(pipelineStream.feed)} />
              <SignalRow label="Latest run" value={stringValue(latestRun.status)} sub={formatDateTime(latestRun.finished_at)} />
              <SignalRow label="Run features" value={compactNumber(latestRunCounts.features)} />
            </div>
            <div className="min-w-0">
              {providerRows.slice(0, 4).map((provider) => (
                <SignalRow
                  key={stringValue(provider.provider)}
                  label={stringValue(provider.provider)}
                  value={stringValue(provider.mode)}
                  sub={`${stringValue(provider.symbol)} / ${stringValue(provider.detail)} / ${formatDateTime(provider.last_at)}`}
                />
              ))}
            </div>
          </div>
          <EndpointError result={pipelineStatus} />
          <EndpointError result={statusBadges} />
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Gauge className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">SPY Alpha Snapshot</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <SignalRow label="Category" value={stringValue(primaryFeature.category)} />
            <SignalRow label="Score" value={score(primaryFeature.score)} />
            <SignalRow label="Last close" value={compactNumber(primaryFeatureMetrics.last_close)} />
            <SignalRow label="Liquidity" value={score(primaryFeatureMetrics.liquidity_score)} />
            <SignalRow label="Trend" value={score(primaryFeatureMetrics.trend_score)} />
            <SignalRow label="Realized vol 20D" value={signedPercent(primaryFeatureMetrics.realized_vol_20d)} />
            <SignalRow label="Return 1D" value={signedPercent(primaryFeatureMetrics.return_1d)} />
            <SignalRow label="Return 20D" value={signedPercent(primaryFeatureMetrics.return_20d)} />
          </div>
          <div className="mt-4 border-t border-border pt-4 font-mono text-xs leading-6 text-muted-foreground">
            <p>feature_id {stringValue(primaryFeature.feature_id)}</p>
            <p>snapshot {stringValue(primaryFeature.source_snapshot_id)}</p>
            <p>as_of {formatDateTime(primaryFeature.as_of)}</p>
          </div>
          <EndpointError result={features} />
        </article>

        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <RadioTower className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-card-foreground">LLM Role Mesh</h2>
          </div>
          <div className="grid gap-x-5 lg:grid-cols-2">
            {roles.length ? (
              roles.map((role) => {
                const status = stringValue(role.status);
                return (
                  <div key={stringValue(role.role)} className="border-b border-border py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <span className="font-mono text-xs font-semibold text-foreground">
                        {stringValue(role.role)}
                      </span>
                      <span className={`rounded border px-2 py-1 font-mono text-xs ${statusClass(status)}`}>
                        {status}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-xs leading-5 text-muted-foreground">
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

      <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
        <div className="mb-4 flex items-center gap-2">
          <BrainCircuit className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-card-foreground">Research Intelligence Feed</h2>
        </div>
        <div className="space-y-3 md:hidden">
          {reportRows.map((report, index) => (
            <div
              key={stringValue(report.report_id, String(index))}
              className="border-b border-border py-3 last:border-b-0"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 break-words font-mono text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                  {stringValue(report.title, stringValue(report.report_id))}
                </p>
                <span className="shrink-0 font-mono text-xs font-semibold text-primary">
                  {score(report.confidence)}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 font-mono text-xs text-muted-foreground">
                <div>
                  <p className="uppercase tracking-[0.14em]">Assets</p>
                  <p className="mt-1 font-semibold text-foreground">{listValue(report.asset_universe)}</p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.14em]">Status</p>
                  <p className="mt-1 font-semibold text-foreground">{stringValue(report.status)}</p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.14em]">Agent</p>
                  <p className="mt-1 break-words font-semibold text-foreground [overflow-wrap:anywhere]">
                    {stringValue(report.agent_role, stringValue(report.agent_id))}
                  </p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.14em]">Published</p>
                  <p className="mt-1 font-semibold text-foreground">
                    {formatDateTime(report.published_at || report.created_at)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[62rem] border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border text-left uppercase tracking-[0.12em] text-muted-foreground">
                {["Report", "Assets", "Confidence", "Status", "Agent", "Published"].map((header) => (
                  <th key={header} className="px-3 py-3 font-medium">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reportRows.map((report, index) => (
                <tr
                  key={stringValue(report.report_id, String(index))}
                  className="border-b border-border last:border-b-0"
                >
                  <td className="px-3 py-3 font-semibold text-foreground">
                    {stringValue(report.title, stringValue(report.report_id))}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{listValue(report.asset_universe)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{score(report.confidence)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.status)}</td>
                  <td className="px-3 py-3 text-muted-foreground">{stringValue(report.agent_role, stringValue(report.agent_id))}</td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {formatDateTime(report.published_at || report.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {reportRows.length === 0 ? (
          <p className="mt-4 font-mono text-sm text-muted-foreground">
            `/api/research/reports` returned no reports.
          </p>
        ) : null}
        <EndpointError result={reports} />
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Policy Posture</h2>
          </div>
          <SignalRow label="Execution" value={executionStatus} sub={stringValue(executionMode.reason)} />
          <SignalRow label="Broker" value={stringValue(executionMode.broker)} />
          <SignalRow label="Strict data" value={boolValue(dataSource.strict_real_data_only) ? "Enabled" : "Disabled"} />
        </article>
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Network className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Lineage Counters</h2>
          </div>
          <SignalRow label="Raw events" value={compactNumber(pipelineCounts.data_raw_events)} />
          <SignalRow label="Market bars" value={compactNumber(pipelineCounts.data_market_bars)} />
          <SignalRow label="Quality events" value={compactNumber(pipelineCounts.data_quality_events)} />
        </article>
        <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Fund Stream</h2>
          </div>
          <SignalRow label="Latest type" value={stringValue(recordValue(fundStream).latest_event_type)} />
          <SignalRow label="Latest run" value={stringValue(recordValue(fundStream).latest_run_id)} />
          <SignalRow label="Published" value={formatDateTime(recordValue(fundStream).latest_published_at)} />
          <EndpointError result={streamStatus} />
        </article>
      </section>
    </main>
  );
}
