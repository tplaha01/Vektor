import Link from "next/link";
import {
  Activity,
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileSearch,
  Search,
} from "lucide-react";
import { getResearchReports, reportHref } from "@/lib/research-api";
import type { LiveResearchReport } from "@/lib/types";

type SearchParams = Record<string, string | string[] | undefined>;

function getParam(searchParams: SearchParams | undefined, key: string) {
  const value = searchParams?.[key];
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function normalized(value: string) {
  return value.trim().toLowerCase();
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function matchesSearch(report: LiveResearchReport, params: SearchParams | undefined) {
  const query = normalized(getParam(params, "q"));
  if (!query) return true;

  return [
    report.title,
    report.summary,
    report.agent_role,
    report.agent_id,
    report.asset_universe.join(" "),
    report.findings.join(" "),
  ].some((field) => normalized(String(field || "")).includes(query));
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

export default async function Home({ searchParams }: { searchParams?: SearchParams }) {
  let reports: LiveResearchReport[] = [];
  let apiError = "";

  try {
    const payload = await getResearchReports({ limit: 80, surface: "public" });
    reports = payload.reports;
  } catch (error) {
    apiError = error instanceof Error ? error.message : "Research API request failed";
  }

  const assetFilter = getParam(searchParams, "asset");
  const roleFilter = getParam(searchParams, "agent_role");
  const filteredReports = reports.filter(
    (report) =>
      matchesSearch(report, searchParams) &&
      (!assetFilter || report.asset_universe.includes(assetFilter)) &&
      (!roleFilter || report.agent_role === roleFilter),
  );
  const assets = uniqueSorted(reports.flatMap((report) => report.asset_universe));
  const roles = uniqueSorted(reports.map((report) => report.agent_role));
  const averageConfidence =
    reports.reduce((total, report) => total + Number(report.confidence || 0), 0) /
    Math.max(1, reports.length);
  const latestUpdate = reports
    .map((report) => report.published_at)
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];

  const metrics = [
    { label: "Public reports", value: reports.length, icon: FileSearch },
    { label: "Visible", value: filteredReports.length, icon: CheckCircle2 },
    { label: "Avg confidence", value: `${Math.round(averageConfidence * 100)}%`, icon: Activity },
    {
      label: "Latest update",
      value: latestUpdate ? formatDateTime(latestUpdate) : "No reports",
      icon: CalendarClock,
    },
  ];

  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-8 lg:py-10">
        <div className="flex flex-col gap-6 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Vektor Research
            </p>
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
              Live research archive
            </h1>
            <p className="max-w-2xl font-mono text-sm leading-6 text-muted-foreground">
              Public research reports served from the TradingBot research API and fund
              orchestrator storage.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-border bg-card/70 px-3 py-2 font-mono text-xs text-muted-foreground">
            <Clock3 className="size-4 text-primary" aria-hidden="true" />
            <span>{filteredReports.length} visible</span>
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

        <form
          action="/"
          className="mt-6 rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
        >
          <div className="flex items-center gap-2 border-b border-border pb-4">
            <Search className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold text-card-foreground">Research query</h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_14rem_14rem]">
            <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
              <span>Search</span>
              <input
                name="q"
                defaultValue={getParam(searchParams, "q")}
                placeholder="asset, title, finding, agent..."
                className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <Select name="asset" label="Asset" options={assets} searchParams={searchParams} />
            <Select
              name="agent_role"
              label="Agent Role"
              options={roles}
              searchParams={searchParams}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              className="inline-flex h-10 items-center rounded-md bg-primary px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary-foreground transition hover:bg-primary/90"
            >
              Apply
            </button>
            <Link
              href="/"
              className="inline-flex h-10 items-center rounded-md border border-border px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
            >
              Reset
            </Link>
          </div>
        </form>

        <div className="mt-6 grid gap-3">
          {filteredReports.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card/50 p-8 text-center">
              <FileSearch className="mx-auto mb-4 size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-foreground">No public research found</h2>
              <p className="mx-auto mt-2 max-w-xl font-mono text-sm leading-6 text-muted-foreground">
                Reports appear here only after the backend promotes live research to
                the public research surface.
              </p>
            </div>
          ) : (
            filteredReports.map((report) => (
              <article
                key={report.report_id}
                className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">
                      <span>{report.agent_role}</span>
                      <span className="text-border">/</span>
                      <span>{formatDate(report.published_at)}</span>
                      <span className="text-border">/</span>
                      <span>{Math.round(Number(report.confidence || 0) * 100)}%</span>
                    </div>
                    <h2 className="mt-2 text-xl font-semibold tracking-normal text-card-foreground">
                      {report.title}
                    </h2>
                    <p className="mt-3 max-w-4xl font-mono text-xs leading-6 text-muted-foreground">
                      {report.summary}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {report.asset_universe.map((asset) => (
                        <span
                          key={`${report.report_id}-${asset}`}
                          className="rounded border border-border bg-background px-2 py-1 font-mono text-xs text-foreground"
                        >
                          {asset}
                        </span>
                      ))}
                    </div>
                  </div>
                  <Link
                    href={reportHref(report)}
                    className="inline-flex h-10 shrink-0 items-center rounded-md border border-border px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-foreground transition hover:border-primary/50 hover:text-primary"
                  >
                    Read
                  </Link>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function Select({
  name,
  label,
  options,
  searchParams,
}: {
  name: string;
  label: string;
  options: string[];
  searchParams?: SearchParams;
}) {
  return (
    <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
      <span>{label}</span>
      <select
        name={name}
        defaultValue={getParam(searchParams, name)}
        className="h-10 w-full rounded-md border border-input bg-card px-3 font-mono text-xs normal-case tracking-normal text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
