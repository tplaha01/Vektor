import Link from "next/link";
import {
  Activity,
  AlertCircle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  CircleDot,
  FileText,
  Gauge,
  GitBranch,
} from "lucide-react";
import { getResearchReports, reportHref } from "@/lib/research-api";
import type { LiveResearchReport } from "@/lib/types";

type CalendarCell = {
  key: string;
  day: string;
  date: string;
  hasReport: boolean;
};

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Signal Reports",
  description: "Live Vektor market signal briefings from the TradingBot research API.",
};

function dateOrNull(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dateKey(value?: string | null) {
  const date = dateOrNull(value);
  return date ? date.toISOString().slice(0, 10) : "";
}

function formatDate(value?: string | null) {
  const date = dateOrNull(value);
  if (!date) return "Unavailable";

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(date);
}

function formatMonth(value?: string | null) {
  const date = dateOrNull(value);
  if (!date) return "No published dates";

  return new Intl.DateTimeFormat("en", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function average(values: number[]) {
  return values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : 0;
}

function confidenceLabel(value: number) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function hasTrace(report: LiveResearchReport) {
  const trace = isPlainRecord(report.ai_trace) ? report.ai_trace : {};
  const provenance = isPlainRecord(report.provenance) ? report.provenance : {};

  return Object.keys(trace).length > 0 || Object.values(provenance).some((value) => {
    if (Array.isArray(value)) return value.length > 0;
    return Boolean(value);
  });
}

function buildCalendarDays(reports: LiveResearchReport[]): CalendarCell[] {
  const reportDates = new Set(reports.map((report) => dateKey(report.published_at)).filter(Boolean));
  const anchor = reports.map((report) => report.published_at).find((value) => dateKey(value));
  const anchorDate = dateOrNull(anchor);
  if (!anchorDate) return [];

  const monthStart = new Date(Date.UTC(anchorDate.getUTCFullYear(), anchorDate.getUTCMonth(), 1, 12));
  const daysInMonth = new Date(
    Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, 0),
  ).getUTCDate();
  const leadingBlanks = monthStart.getUTCDay();

  return [
    ...Array.from({ length: leadingBlanks }, (_, index) => ({
      key: `blank-${index}`,
      day: "",
      date: "",
      hasReport: false,
    })),
    ...Array.from({ length: daysInMonth }, (_, index) => {
      const day = index + 1;
      const date = `${monthStart.getUTCFullYear()}-${String(
        monthStart.getUTCMonth() + 1,
      ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      return {
        key: date,
        day: String(day),
        date,
        hasReport: reportDates.has(date),
      };
    }),
  ];
}

export default async function SignalsPage() {
  let reports: LiveResearchReport[] = [];
  let apiError = "";

  try {
    const payload = await getResearchReports({ limit: 80, surface: "public" });
    reports = payload.reports.sort(
      (a, b) =>
        (dateOrNull(b.published_at)?.getTime() || 0) -
        (dateOrNull(a.published_at)?.getTime() || 0),
    );
  } catch (error) {
    apiError = error instanceof Error ? error.message : "Research API request failed";
  }

  const latestUpdate = reports[0]?.published_at;
  const averageConfidence = average(reports.map((report) => Number(report.confidence || 0)));
  const tracedReports = reports.filter(hasTrace);
  const calendarDays = buildCalendarDays(reports);
  const reportsByDate = reports.reduce((next, report) => {
    const key = dateKey(report.published_at);
    if (!key) return next;
    const bucket = next.get(key) || [];
    bucket.push(report);
    next.set(key, bucket);
    return next;
  }, new Map<string, LiveResearchReport[]>());

  const metrics = [
    {
      label: "Public reports",
      value: reports.length,
      icon: FileText,
    },
    {
      label: "Published dates",
      value: reportsByDate.size,
      icon: CalendarDays,
    },
    {
      label: "Trace attached",
      value: tracedReports.length,
      icon: CheckCircle2,
    },
    {
      label: "Avg confidence",
      value: confidenceLabel(averageConfidence),
      icon: Gauge,
    },
  ];

  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-8 lg:py-10">
        <div className="flex flex-col gap-6 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Signal Reports
            </p>
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Live research signal stream
            </h1>
            <p className="max-w-2xl font-mono text-sm leading-6 text-muted-foreground">
              Public reports promoted by the TradingBot research API, with confidence,
              provenance, and AI trace fields from the backend research store.
            </p>
          </div>
          <div className="rounded-md border border-border bg-card/70 px-3 py-2 font-mono text-xs text-muted-foreground">
            Last update <span className="text-foreground">{formatDate(latestUpdate)}</span>
          </div>
        </div>

        {apiError ? (
          <div className="mt-6 rounded-lg border border-destructive/40 bg-destructive/10 p-4 font-mono text-sm text-destructive">
            <AlertCircle className="mb-3 size-5" aria-hidden="true" />
            {apiError}
          </div>
        ) : null}

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <article
                key={metric.label}
                className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
              >
                <Icon className="mb-4 size-4 text-primary" aria-hidden="true" />
                <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {metric.label}
                </p>
                <p className="mt-2 text-2xl font-semibold text-card-foreground">
                  {metric.value}
                </p>
              </article>
            );
          })}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <aside className="h-fit rounded-lg border border-border bg-card/70 p-5 shadow-black-soft lg:sticky lg:top-24">
            <div className="flex items-center gap-2 border-b border-border pb-4">
              <CalendarDays className="size-4 text-primary" aria-hidden="true" />
              <div>
                <h2 className="text-base font-semibold text-card-foreground">
                  Signal Calendar
                </h2>
                <p className="font-mono text-xs text-muted-foreground">
                  {formatMonth(latestUpdate)}
                </p>
              </div>
            </div>

            {calendarDays.length > 0 ? (
              <>
                <div className="mt-4 grid grid-cols-7 gap-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">
                  {["S", "M", "T", "W", "T", "F", "S"].map((day, index) => (
                    <span key={`${day}-${index}`} className="text-center">
                      {day}
                    </span>
                  ))}
                </div>
                <div className="mt-2 grid grid-cols-7 gap-1">
                  {calendarDays.map((day) => {
                    const bucket = reportsByDate.get(day.date) || [];
                    return (
                      <div
                        key={day.key}
                        title={bucket.map((report) => report.title).join(" / ")}
                        className={`flex aspect-square items-center justify-center rounded border font-mono text-xs ${
                          day.hasReport
                            ? "border-primary/40 bg-primary/15 text-primary"
                            : day.day
                              ? "border-border bg-background/50 text-muted-foreground"
                              : "border-transparent"
                        }`}
                      >
                        {day.day}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p className="mt-4 font-mono text-xs leading-5 text-muted-foreground">
                No published report dates were returned by the research API.
              </p>
            )}

            <div className="mt-5 space-y-3 border-t border-border pt-4">
              {reports.slice(0, 4).map((report) => (
                <Link
                  key={report.report_id}
                  href={reportHref(report)}
                  className="flex items-start gap-2 rounded-md border border-border bg-background/50 p-3 transition hover:border-primary/40"
                >
                  <CircleDot className="mt-0.5 size-3 text-primary" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
                      {formatDate(report.published_at)}
                    </span>
                    <span className="mt-1 block text-xs font-semibold text-foreground">
                      {report.title}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </aside>

          <section className="grid gap-4">
            {reports.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-card/50 p-8 text-center">
                <FileText className="mx-auto mb-4 size-8 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-xl font-semibold text-foreground">No public signal reports</h2>
                <p className="mx-auto mt-2 max-w-xl font-mono text-sm leading-6 text-muted-foreground">
                  Reports appear here after the backend publishes research records
                  to the public research surface.
                </p>
              </div>
            ) : (
              reports.map((report) => {
                const traced = hasTrace(report);
                return (
                  <article
                    key={report.report_id}
                    className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">
                          <span>{formatDate(report.published_at)}</span>
                          <span className="text-border">/</span>
                          <span>{report.agent_role}</span>
                          {report.asset_universe.length > 0 ? (
                            <>
                              <span className="text-border">/</span>
                              <span>{report.asset_universe.join(" / ")}</span>
                            </>
                          ) : null}
                        </div>
                        <h2 className="mt-3 text-2xl font-semibold tracking-normal text-card-foreground">
                          {report.title}
                        </h2>
                        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
                          {report.summary}
                        </p>
                      </div>

                      <div className="inline-flex h-fit items-center gap-2 rounded border border-primary/30 bg-primary/10 px-3 py-2 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary">
                        <Activity className="size-4" aria-hidden="true" />
                        {confidenceLabel(report.confidence)}
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-3">
                      <div className="rounded-md border border-border bg-background/55 p-3">
                        <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                          Provider
                        </p>
                        <p className="mt-2 break-words font-mono text-xs text-foreground">
                          {report.provider_used || "Unavailable"}
                        </p>
                      </div>
                      <div className="rounded-md border border-border bg-background/55 p-3">
                        <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                          Model
                        </p>
                        <p className="mt-2 break-words font-mono text-xs text-foreground">
                          {report.model_used || "Unavailable"}
                        </p>
                      </div>
                      <div className="rounded-md border border-border bg-background/55 p-3">
                        <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                          Findings
                        </p>
                        <p className="mt-2 text-xl font-semibold text-foreground">
                          {report.findings.length}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-2">
                      {report.asset_universe.map((asset) => (
                        <span
                          key={`${report.report_id}-${asset}`}
                          className="rounded border border-accent/20 bg-accent/10 px-2 py-1 font-mono text-xs text-accent"
                        >
                          {asset}
                        </span>
                      ))}
                    </div>

                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                      <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                        {traced ? (
                          <GitBranch className="size-4 text-primary" aria-hidden="true" />
                        ) : (
                          <BarChart3 className="size-4 text-muted-foreground" aria-hidden="true" />
                        )}
                        <span>{traced ? "Trace attached" : "No trace returned"}</span>
                      </div>
                      <Link
                        href={reportHref(report)}
                        className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-foreground transition hover:border-primary/50 hover:text-primary"
                      >
                        View Full Report
                      </Link>
                    </div>
                  </article>
                );
              })
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
