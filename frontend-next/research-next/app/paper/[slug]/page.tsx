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
  Tag,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { researchPapers } from "@/lib/mock-research";
import { siteConfig } from "@/lib/site";
import type { ResearchPaper, SignalDirection } from "@/lib/types";

interface PaperPageProps {
  params: {
    slug: string;
  };
}

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

const horizonWeight: Record<ResearchPaper["horizon"], string> = {
  intraday: "Execution window",
  swing: "Tactical window",
  position: "Portfolio window",
  strategic: "Allocation window",
};

export function generateStaticParams() {
  return researchPapers.map((paper) => ({
    slug: paper.slug,
  }));
}

function getPaperBySlug(slug: string) {
  return researchPapers.find((paper) => paper.slug === slug);
}

export function generateMetadata({ params }: PaperPageProps): Metadata {
  const paper = getPaperBySlug(params.slug);

  if (!paper) {
    return {
      title: "Paper not found",
    };
  }

  return {
    title: paper.title,
    description: paper.abstract,
    authors: paper.authors.map((author) => ({
      name: author.name,
    })),
    keywords: [
      paper.category,
      paper.signalDirection,
      paper.horizon,
      ...paper.tickers,
      ...paper.tags,
    ],
    openGraph: {
      title: paper.title,
      description: paper.abstract,
      type: "article",
      url: `${siteConfig.url}/paper/${paper.slug}`,
      publishedTime: paper.publishedAt,
      modifiedTime: paper.updatedAt,
      authors: paper.authors.map((author) => author.name),
      tags: paper.tags,
    },
  };
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
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function buildPaperBody(paper: ResearchPaper) {
  const leadTicker = paper.tickers[0];
  const secondaryTickers = paper.tickers.slice(1).join(", ");
  const tagPhrase = paper.tags.join(", ");
  const authorDesk = paper.authors.map((author) => author.desk).join(" / ");

  return [
    {
      heading: "Investment Thesis",
      body: `${paper.subtitle} The ${paper.category.toLowerCase()} combines ${tagPhrase} signals across ${leadTicker}${
        secondaryTickers ? ` and the related ${secondaryTickers} complex` : ""
      }, with a ${paper.horizon} holding framework and ${formatPercent(
        paper.confidence,
      )} model confidence.`,
    },
    {
      heading: "Evidence Stack",
      body: `The research stack weights desk inputs from ${authorDesk}, current data freshness marked ${paper.dataFreshness}, and cross-asset confirmation from ticker, tag, and horizon factors. The abstract remains the controlling summary for the current publication state.`,
    },
    {
      heading: "Portfolio Read-Through",
      body: `The system classifies the signal as ${paper.signalDirection.toUpperCase()} with a ${horizonWeight[
        paper.horizon
      ].toLowerCase()}. Operators should treat this page as a concise viewer for the archive record until live signal reports are attached in the next rollout.`,
    },
  ];
}

function buildSignalTrace(paper: ResearchPaper) {
  const directionScore =
    paper.signalDirection === "buy" ? 0.82 : paper.signalDirection === "sell" ? 0.34 : 0.55;
  const freshnessScore =
    paper.dataFreshness === "live"
      ? 0.91
      : paper.dataFreshness === "delayed"
        ? 0.72
        : paper.dataFreshness === "backtest"
          ? 0.64
          : 0.48;
  const breadthScore = Math.min(0.94, 0.52 + paper.tickers.length * 0.09 + paper.tags.length * 0.03);

  return [
    {
      stage: "Universe match",
      input: paper.tickers.join(" / "),
      score: breadthScore,
      output: `${paper.tickers.length} symbols mapped`,
    },
    {
      stage: "Feature blend",
      input: paper.tags.join(" / "),
      score: paper.confidence,
      output: `${paper.tags.length} research factors active`,
    },
    {
      stage: "Freshness gate",
      input: paper.dataFreshness,
      score: freshnessScore,
      output: paper.dataFreshness === "degraded" ? "operator review" : "ready",
    },
    {
      stage: "Signal policy",
      input: paper.horizon,
      score: directionScore,
      output: paper.signalDirection.toUpperCase(),
    },
  ];
}

function relatedPapersFor(paper: ResearchPaper) {
  return researchPapers
    .filter((candidate) => candidate.slug !== paper.slug)
    .map((candidate) => {
      const sharedTags = candidate.tags.filter((tag) => paper.tags.includes(tag)).length;
      const sharedTickers = candidate.tickers.filter((ticker) =>
        paper.tickers.includes(ticker),
      ).length;
      const categoryMatch = candidate.category === paper.category ? 1 : 0;
      return {
        paper: candidate,
        score: sharedTags * 2 + sharedTickers * 3 + categoryMatch,
      };
    })
    .filter((candidate) => candidate.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map((candidate) => candidate.paper);
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
      <span className="max-w-[11rem] text-right font-mono text-xs text-foreground">{value}</span>
    </div>
  );
}

export default function PaperPage({ params }: PaperPageProps) {
  const paper = getPaperBySlug(params.slug);

  if (!paper) {
    notFound();
  }

  const SignalIcon = signalIcons[paper.signalDirection];
  const paperBody = buildPaperBody(paper);
  const signalTrace = buildSignalTrace(paper);
  const relatedPapers = relatedPapersFor(paper);

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
                <span>{paper.category}</span>
                <span className="text-border">/</span>
                <span>{paper.readingMinutes} min read</span>
                <span className="text-border">/</span>
                <span className={freshnessTone[paper.dataFreshness]}>
                  {paper.dataFreshness}
                </span>
              </div>

              <h1 className="mt-3 max-w-4xl text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
                {paper.title}
              </h1>
              <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-accent">
                {paper.subtitle}
              </p>

              <div className="mt-5 flex flex-wrap gap-2">
                {paper.tickers.map((ticker) => (
                  <span
                    key={ticker}
                    className="rounded border border-border bg-card px-2 py-1 font-mono text-xs text-foreground"
                  >
                    {ticker}
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
                {paper.abstract}
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
              <div className="flex items-center gap-2">
                <Database className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-card-foreground">Research Body</h2>
              </div>
              <div className="mt-5 grid gap-5">
                {paperBody.map((section) => (
                  <div key={section.heading}>
                    <h3 className="font-mono text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
                      {section.heading}
                    </h3>
                    <p className="mt-2 font-mono text-sm leading-7 text-muted-foreground">
                      {section.body}
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
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[44rem] border-collapse font-mono text-xs">
                  <thead>
                    <tr className="border-b border-border text-left uppercase tracking-[0.14em] text-muted-foreground">
                      <th className="py-3 pr-4 font-medium">Stage</th>
                      <th className="py-3 pr-4 font-medium">Input</th>
                      <th className="py-3 pr-4 font-medium">Score</th>
                      <th className="py-3 font-medium">Output</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalTrace.map((row) => (
                      <tr key={row.stage} className="border-b border-border last:border-b-0">
                        <td className="py-3 pr-4 text-foreground">{row.stage}</td>
                        <td className="py-3 pr-4 text-muted-foreground">{row.input}</td>
                        <td className="py-3 pr-4 text-foreground">{formatPercent(row.score)}</td>
                        <td className="py-3 text-accent">{row.output}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {relatedPapers.length > 0 ? (
              <section className="mt-4">
                <div className="mb-3 flex items-center gap-2">
                  <Tag className="size-4 text-primary" aria-hidden="true" />
                  <h2 className="text-lg font-semibold text-foreground">Related Papers</h2>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {relatedPapers.map((related) => (
                    <Link
                      key={related.slug}
                      href={`/paper/${related.slug}`}
                      className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft transition hover:border-primary/40"
                    >
                      <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
                        {related.category}
                      </p>
                      <h3 className="mt-2 text-base font-semibold text-card-foreground">
                        {related.title}
                      </h3>
                      <p className="mt-2 font-mono text-xs leading-5 text-muted-foreground">
                        {related.subtitle}
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
                  {formatPercent(paper.confidence)}
                </p>
              </div>
              <Gauge className="size-5 text-primary" aria-hidden="true" />
            </div>

            <div className="mt-4 space-y-3">
              <MetadataRow label="Published" value={formatDate(paper.publishedAt)} />
              <MetadataRow label="Updated" value={formatDateTime(paper.updatedAt)} />
              <MetadataRow
                label="Signal"
                value={
                  <span
                    className={`inline-flex items-center gap-1 rounded border px-2 py-1 uppercase ${signalTone[paper.signalDirection]}`}
                  >
                    <SignalIcon className="size-3" aria-hidden="true" />
                    {paper.signalDirection}
                  </span>
                }
              />
              <MetadataRow label="Horizon" value={paper.horizon} />
              <MetadataRow
                label="Freshness"
                value={
                  <span className={freshnessTone[paper.dataFreshness]}>
                    {paper.dataFreshness}
                  </span>
                }
              />
              <MetadataRow
                label="Authors"
                value={paper.authors.map((author) => author.name).join(", ")}
              />
            </div>

            <div className="mt-5 grid gap-3 rounded-md border border-border bg-background/60 p-3">
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
                <span>Archive record ready</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <CalendarClock className="size-4 text-accent" aria-hidden="true" />
                <span>{horizonWeight[paper.horizon]}</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <Clock3 className="size-4 text-secondary" aria-hidden="true" />
                <span>{paper.readingMinutes} minute operator review</span>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {paper.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded border border-accent/20 bg-accent/10 px-2 py-1 font-mono text-xs text-accent"
                >
                  {tag}
                </span>
              ))}
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
