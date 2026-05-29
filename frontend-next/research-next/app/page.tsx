import {
  Activity,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileSearch,
  Filter,
  Search,
  SlidersHorizontal,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { researchPapers } from "@/lib/mock-research";
import type { ResearchCategory, ResearchPaper, SignalDirection } from "@/lib/types";

type SearchParams = Record<string, string | string[] | undefined>;

type FilterKey = "category" | "tag" | "signal" | "horizon";
type SearchKey = "title" | "abstract" | "ticker" | "author" | "tagSearch";

const searchFields: { key: SearchKey; label: string; placeholder: string }[] = [
  { key: "title", label: "Title", placeholder: "NVDA, breadth, credit..." },
  { key: "abstract", label: "Abstract", placeholder: "capex, liquidity..." },
  { key: "ticker", label: "Ticker", placeholder: "SPY" },
  { key: "author", label: "Author", placeholder: "Maya Iyer" },
  { key: "tagSearch", label: "Tag search", placeholder: "macro" },
];

const filterLabels: Record<FilterKey, string> = {
  category: "Category",
  tag: "Tag",
  signal: "Signal",
  horizon: "Horizon",
};

const signalTone: Record<SignalDirection, string> = {
  buy: "border-primary/30 bg-primary/10 text-primary",
  hold: "border-secondary/30 bg-secondary/10 text-secondary",
  sell: "border-destructive/40 bg-destructive/10 text-destructive",
};

const signalIcons: Record<SignalDirection, typeof TrendingUp> = {
  buy: TrendingUp,
  hold: Activity,
  sell: TrendingDown,
};

const freshnessTone: Record<ResearchPaper["dataFreshness"], string> = {
  live: "text-primary",
  delayed: "text-accent",
  backtest: "text-secondary",
  degraded: "text-destructive",
};

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

function matchesSearch(paper: ResearchPaper, params: SearchParams | undefined) {
  const title = normalized(getParam(params, "title"));
  const abstract = normalized(getParam(params, "abstract"));
  const ticker = normalized(getParam(params, "ticker"));
  const author = normalized(getParam(params, "author"));
  const tagSearch = normalized(getParam(params, "tagSearch"));

  return (
    (!title || normalized(paper.title).includes(title)) &&
    (!abstract || normalized(paper.abstract).includes(abstract)) &&
    (!ticker || paper.tickers.some((item) => normalized(item).includes(ticker))) &&
    (!author ||
      paper.authors.some((item) =>
        normalized(`${item.name} ${item.role} ${item.desk}`).includes(author),
      )) &&
    (!tagSearch || paper.tags.some((item) => normalized(item).includes(tagSearch)))
  );
}

function matchesFilters(paper: ResearchPaper, params: SearchParams | undefined) {
  const category = getParam(params, "category");
  const tag = getParam(params, "tag");
  const signal = getParam(params, "signal");
  const horizon = getParam(params, "horizon");

  return (
    (!category || paper.category === category) &&
    (!tag || paper.tags.includes(tag)) &&
    (!signal || paper.signalDirection === signal) &&
    (!horizon || paper.horizon === horizon)
  );
}

function uniqueSorted<T extends string>(values: T[]) {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b));
}

function SelectFilter({
  name,
  options,
  searchParams,
}: {
  name: FilterKey;
  options: string[];
  searchParams?: SearchParams;
}) {
  return (
    <label className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
      <span>{filterLabels[name]}</span>
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

export default function Home({ searchParams }: { searchParams?: SearchParams }) {
  const categories = uniqueSorted(
    researchPapers.map((paper) => paper.category as ResearchCategory),
  );
  const tags = uniqueSorted(researchPapers.flatMap((paper) => paper.tags));
  const signals = uniqueSorted(researchPapers.map((paper) => paper.signalDirection));
  const horizons = uniqueSorted(researchPapers.map((paper) => paper.horizon));
  const filteredPapers = researchPapers.filter(
    (paper) => matchesSearch(paper, searchParams) && matchesFilters(paper, searchParams),
  );

  const averageConfidence =
    researchPapers.reduce((total, paper) => total + paper.confidence, 0) /
    researchPapers.length;
  const liveReadyReports = researchPapers.filter(
    (paper) => paper.dataFreshness === "live",
  ).length;
  const latestUpdate = researchPapers
    .map((paper) => paper.updatedAt)
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];

  const metrics = [
    { label: "Total papers", value: researchPapers.length, icon: FileSearch },
    { label: "Live/ready reports", value: liveReadyReports, icon: CheckCircle2 },
    {
      label: "Avg confidence",
      value: `${Math.round(averageConfidence * 100)}%`,
      icon: Activity,
    },
    { label: "Latest update", value: formatDateTime(latestUpdate), icon: CalendarClock },
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
              Institutional research archive
            </h1>
            <p className="max-w-2xl font-mono text-sm leading-6 text-muted-foreground">
              Search model-backed briefs, signal reports, and risk notes by title,
              abstract, ticker, author, or tag.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-border bg-card/70 px-3 py-2 font-mono text-xs text-muted-foreground">
            <Clock3 className="size-4 text-primary" aria-hidden="true" />
            <span>{filteredPapers.length} visible</span>
          </div>
        </div>

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
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <Search className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold text-card-foreground">
                Research query
              </h2>
            </div>
            <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <Filter className="size-4 text-accent" aria-hidden="true" />
              <span>Compound filters</span>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-5">
            {searchFields.map((field) => (
              <label
                key={field.key}
                className="space-y-2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground"
              >
                <span>{field.label}</span>
                <input
                  name={field.key}
                  defaultValue={getParam(searchParams, field.key)}
                  placeholder={field.placeholder}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-xs normal-case tracking-normal text-foreground placeholder:text-muted-foreground/55 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </label>
            ))}
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <SelectFilter name="category" options={categories} searchParams={searchParams} />
            <SelectFilter name="tag" options={tags} searchParams={searchParams} />
            <SelectFilter name="signal" options={signals} searchParams={searchParams} />
            <SelectFilter name="horizon" options={horizons} searchParams={searchParams} />
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-primary-foreground transition hover:bg-primary/90"
            >
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              Apply
            </button>
            <a
              href="/"
              className="inline-flex h-10 items-center rounded-md border border-border px-4 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
            >
              Reset
            </a>
          </div>
        </form>

        <div className="mt-6 grid gap-3">
          {filteredPapers.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card/50 p-8 text-center">
              <FileSearch className="mx-auto mb-4 size-8 text-muted-foreground" aria-hidden="true" />
              <h2 className="text-xl font-semibold text-foreground">No research matched</h2>
              <p className="mx-auto mt-2 max-w-xl font-mono text-sm leading-6 text-muted-foreground">
                Adjust the title, abstract, ticker, author, tag search, or remove one
                of the category, tag, signal, and horizon filters.
              </p>
            </div>
          ) : (
            filteredPapers.map((paper) => {
              const SignalIcon = signalIcons[paper.signalDirection];
              return (
                <article
                  key={paper.slug}
                  className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft"
                >
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">
                        <span>{paper.category}</span>
                        <span className="text-border">/</span>
                        <span>{paper.readingMinutes} min</span>
                        <span className="text-border">/</span>
                        <span className={freshnessTone[paper.dataFreshness]}>
                          {paper.dataFreshness}
                        </span>
                      </div>
                      <h2 className="mt-2 text-xl font-semibold tracking-normal text-card-foreground">
                        {paper.title}
                      </h2>
                      <p className="mt-1 font-mono text-xs text-accent">{paper.subtitle}</p>
                      <p className="mt-3 max-w-4xl font-mono text-xs leading-6 text-muted-foreground">
                        {paper.abstract}
                      </p>

                      <div className="mt-4 grid gap-3 xl:grid-cols-3">
                        <div>
                          <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                            Authors
                          </p>
                          <div className="mt-2 space-y-1">
                            {paper.authors.map((author) => (
                              <p
                                key={`${paper.slug}-${author.name}`}
                                className="font-mono text-xs text-foreground"
                              >
                                {author.name}
                                <span className="text-muted-foreground"> / {author.desk}</span>
                              </p>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                            Tickers
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {paper.tickers.map((ticker) => (
                              <span
                                key={`${paper.slug}-${ticker}`}
                                className="rounded border border-border bg-background px-2 py-1 font-mono text-xs text-foreground"
                              >
                                {ticker}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                            Tags
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {paper.tags.map((tag) => (
                              <span
                                key={`${paper.slug}-${tag}`}
                                className="rounded border border-accent/20 bg-accent/10 px-2 py-1 font-mono text-xs text-accent"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <aside className="grid gap-3 rounded-md border border-border bg-background/60 p-3 font-mono text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Published</span>
                        <span className="text-foreground">{formatDate(paper.publishedAt)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Updated</span>
                        <span className="text-foreground">{formatDate(paper.updatedAt)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Confidence</span>
                        <span className="text-foreground">
                          {Math.round(paper.confidence * 100)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Direction</span>
                        <span
                          className={`inline-flex items-center gap-1 rounded border px-2 py-1 uppercase ${signalTone[paper.signalDirection]}`}
                        >
                          <SignalIcon className="size-3" aria-hidden="true" />
                          {paper.signalDirection}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Horizon</span>
                        <span className="text-foreground">{paper.horizon}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Freshness</span>
                        <span className={freshnessTone[paper.dataFreshness]}>
                          {paper.dataFreshness}
                        </span>
                      </div>
                    </aside>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>
    </main>
  );
}
