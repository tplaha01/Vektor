import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Gauge,
  GitBranch,
  Server,
  Tag,
} from "lucide-react";
import {
  getResearchReport,
  getResearchReports,
  reportHref,
  ResearchApiError,
} from "@/lib/research-api";
import { siteConfig } from "@/lib/site";
import type { LiveResearchReport } from "@/lib/types";

interface PaperPageProps {
  params: {
    slug: string;
  };
}

type TraceRow = {
  stage: string;
  input: string;
  value: string;
  source: string;
};

export const dynamic = "force-dynamic";

async function loadReportOrNotFound(reportId: string) {
  try {
    return await getResearchReport(reportId);
  } catch (error) {
    if (error instanceof ResearchApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}

export async function generateMetadata({ params }: PaperPageProps): Promise<Metadata> {
  try {
    const report = await getResearchReport(params.slug);
    const tags = reportTags(report);

    return {
      title: report.title,
      description: report.summary,
      authors: [{ name: report.agent_id }],
      keywords: [report.agent_role, report.status, ...report.asset_universe, ...tags],
      openGraph: {
        title: report.title,
        description: report.summary,
        type: "article",
        url: `${siteConfig.url}/paper/${encodeURIComponent(report.report_id)}`,
        publishedTime: report.published_at,
        modifiedTime: report.created_at,
        authors: [report.agent_id],
        tags,
      },
    };
  } catch (error) {
    if (error instanceof ResearchApiError && error.status === 404) {
      return {
        title: "Paper not found",
      };
    }

    return {
      title: "Research report",
      description: "Live research report from the TradingBot research API.",
    };
  }
}

function formatDate(value?: string | null) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(date);
}

function formatDateTime(value?: string | null) {
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

function formatPercent(value: number) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function valueText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => valueText(item)).filter(Boolean).join(" / ");
  }

  if (isPlainRecord(value)) {
    return JSON.stringify(value);
  }

  if (value === null || value === undefined || value === "") {
    return "";
  }

  return String(value);
}

function listFromRecord(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}

function reportTags(report: LiveResearchReport) {
  const provenance = isPlainRecord(report.provenance) ? report.provenance : {};
  return Array.from(
    new Set([
      ...report.asset_universe,
      ...listFromRecord(provenance, "data_sources"),
      ...listFromRecord(provenance, "policy_gates_applied"),
      ...listFromRecord(provenance, "decision_ids"),
    ]),
  ).filter(Boolean);
}

function buildSignalTrace(report: LiveResearchReport): TraceRow[] {
  const trace = isPlainRecord(report.ai_trace) ? report.ai_trace : {};
  const provenance = isPlainRecord(report.provenance) ? report.provenance : {};
  const rows: TraceRow[] = [];

  for (const [key, value] of Object.entries(trace)) {
    const text = valueText(value);
    if (!text) continue;
    rows.push({
      stage: key.replaceAll("_", " "),
      input: report.run_id || report.report_id,
      value: text,
      source: "ai_trace",
    });
  }

  for (const [key, value] of Object.entries(provenance)) {
    const text = valueText(value);
    if (!text) continue;
    rows.push({
      stage: key.replaceAll("_", " "),
      input: report.report_id,
      value: text,
      source: "provenance",
    });
  }

  return rows;
}

async function relatedReportsFor(report: LiveResearchReport) {
  try {
    const payload = await getResearchReports({ limit: 80, surface: "public" });
    const reportAssets = new Set(report.asset_universe.map((asset) => asset.toUpperCase()));

    return payload.reports
      .filter((candidate) => candidate.report_id !== report.report_id)
      .map((candidate) => {
        const sharedAssets = candidate.asset_universe.filter((asset) =>
          reportAssets.has(asset.toUpperCase()),
        ).length;
        const roleMatch = candidate.agent_role === report.agent_role ? 1 : 0;

        return {
          report: candidate,
          score: sharedAssets * 3 + roleMatch,
        };
      })
      .filter((candidate) => candidate.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((candidate) => candidate.report);
  } catch {
    return [];
  }
}

function MetadataRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border pb-3 last:border-b-0 last:pb-0">
      <span className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </span>
      <span className="max-w-[12rem] text-right font-mono text-xs text-foreground break-words">
        {value}
      </span>
    </div>
  );
}

export default async function PaperPage({ params }: PaperPageProps) {
  const report = await loadReportOrNotFound(params.slug);
  const signalTrace = buildSignalTrace(report);
  const relatedReports = await relatedReportsFor(report);
  const tags = reportTags(report);

  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-8 lg:py-10">
        <Link
          href="/"
          className="inline-flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground transition hover:text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Research index
        </Link>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <article className="min-w-0">
            <div className="border-b border-border pb-6">
              <div className="flex flex-wrap items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">
                <span>{report.agent_role}</span>
                <span className="text-border">/</span>
                <span>{formatDate(report.published_at)}</span>
                <span className="text-border">/</span>
                <span>{formatPercent(report.confidence)}</span>
              </div>

              <h1 className="mt-3 max-w-4xl text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
                {report.title}
              </h1>
              <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-accent">
                {report.summary}
              </p>

              <div className="mt-5 flex flex-wrap gap-2">
                {report.asset_universe.map((asset) => (
                  <span
                    key={asset}
                    className="rounded border border-border bg-card px-2 py-1 font-mono text-xs text-foreground"
                  >
                    {asset}
                  </span>
                ))}
              </div>
            </div>

            <section className="mt-6 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
              <div className="flex items-center gap-2">
                <FileText className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-card-foreground">Abstract</h2>
              </div>
              <p className="mt-4 font-mono text-sm leading-7 text-muted-foreground">
                {report.summary}
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
              <div className="flex items-center gap-2">
                <Database className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-card-foreground">Research Body</h2>
              </div>
              <div className="mt-5 grid gap-5">
                {report.findings.map((finding, index) => (
                  <div key={`${report.report_id}-finding-${index}`}>
                    <h3 className="font-mono text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
                      Finding {index + 1}
                    </h3>
                    <p className="mt-2 font-mono text-sm leading-7 text-muted-foreground">
                      {finding}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-4 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
              <div className="flex items-center gap-2">
                <GitBranch className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  Algorithm Signal Trace
                </h2>
              </div>
              {signalTrace.length > 0 ? (
                <div className="mt-5 overflow-x-auto">
                  <table className="w-full min-w-[44rem] border-collapse font-mono text-xs">
                    <thead>
                      <tr className="border-b border-border text-left uppercase tracking-[0.14em] text-muted-foreground">
                        <th className="py-3 pr-4 font-medium">Stage</th>
                        <th className="py-3 pr-4 font-medium">Input</th>
                        <th className="py-3 pr-4 font-medium">Value</th>
                        <th className="py-3 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {signalTrace.map((row) => (
                        <tr
                          key={`${row.source}-${row.stage}-${row.value}`}
                          className="border-b border-border last:border-b-0"
                        >
                          <td className="py-3 pr-4 text-foreground">{row.stage}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{row.input}</td>
                          <td className="max-w-[22rem] break-words py-3 pr-4 text-foreground">
                            {row.value}
                          </td>
                          <td className="py-3 text-accent">{row.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-4 font-mono text-sm leading-6 text-muted-foreground">
                  No AI trace or provenance fields were returned for this report.
                </p>
              )}
            </section>

            {relatedReports.length > 0 ? (
              <section className="mt-4">
                <div className="mb-3 flex items-center gap-2">
                  <Tag className="size-4 text-primary" aria-hidden="true" />
                  <h2 className="text-lg font-semibold text-foreground">Related Papers</h2>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {relatedReports.map((related) => (
                    <Link
                      key={related.report_id}
                      href={reportHref(related)}
                      className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft transition hover:border-primary/40"
                    >
                      <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                        {related.agent_role}
                      </p>
                      <h3 className="mt-2 text-base font-semibold text-card-foreground">
                        {related.title}
                      </h3>
                      <p className="mt-2 font-mono text-xs leading-5 text-muted-foreground">
                        {related.summary}
                      </p>
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}
          </article>

          <aside className="h-fit rounded-lg border border-border bg-card/70 p-5 shadow-black-soft lg:sticky lg:top-24">
            <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
              <div>
                <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
                  Paper Metadata
                </p>
                <p className="mt-1 text-lg font-semibold text-card-foreground">
                  {formatPercent(report.confidence)}
                </p>
              </div>
              <Gauge className="size-5 text-primary" aria-hidden="true" />
            </div>

            <div className="mt-4 space-y-3">
              <MetadataRow label="Published" value={formatDate(report.published_at)} />
              <MetadataRow label="Created" value={formatDateTime(report.created_at)} />
              <MetadataRow label="Status" value={report.status} />
              <MetadataRow label="Surface" value={report.surface} />
              <MetadataRow label="Agent" value={report.agent_id} />
              <MetadataRow label="Role" value={report.agent_role} />
              <MetadataRow label="Run" value={report.run_id || "Unavailable"} />
              <MetadataRow label="Provider" value={report.provider_used || "Unavailable"} />
              <MetadataRow label="Model" value={report.model_used || "Unavailable"} />
              <MetadataRow label="Views" value={report.views ?? 0} />
            </div>

            <div className="mt-5 grid gap-3 rounded-md border border-border bg-background/60 p-3">
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
                <span>{report.status}</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <CalendarClock className="size-4 text-accent" aria-hidden="true" />
                <span>{formatDateTime(report.published_at)}</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <Clock3 className="size-4 text-secondary" aria-hidden="true" />
                <span>{report.findings.length} findings</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <Server className="size-4 text-primary" aria-hidden="true" />
                <span>{report.report_id}</span>
              </div>
            </div>

            {tags.length > 0 ? (
              <div className="mt-5 flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="max-w-full break-words rounded border border-accent/20 bg-accent/10 px-2 py-1 font-mono text-xs text-accent"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </aside>
        </div>
      </section>
    </main>
  );
}
