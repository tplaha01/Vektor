import { ArrowRight, FileText, Search, SlidersHorizontal } from "lucide-react";

const scaffoldCards = [
  {
    title: "Research index",
    body: "R1 will attach the filterable publication archive to this shell.",
    icon: Search,
  },
  {
    title: "Paper viewer",
    body: "R2 will add paper detail pages with signal lineage traces.",
    icon: FileText,
  },
  {
    title: "Signal reports",
    body: "R3 will add the signal report calendar and generated research queue.",
    icon: SlidersHorizontal,
  },
];

export default function Home() {
  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <section className="vektor-section py-16 lg:py-24">
        <div className="max-w-4xl space-y-6">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            Vektor Research
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-normal text-foreground md:text-6xl">
            Research archive scaffold for the AI-native fund.
          </h1>
          <p className="max-w-2xl font-mono text-sm leading-7 text-muted-foreground">
            This deployment is initialized with shared Vektor chrome, dark
            research typography, Tailwind tokens, and typed contracts for papers
            and signal reports.
          </p>
        </div>

        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {scaffoldCards.map((card) => {
            const Icon = card.icon;
            return (
              <article
                key={card.title}
                className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft"
              >
                <Icon className="mb-5 size-5 text-primary" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  {card.title}
                </h2>
                <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
                  {card.body}
                </p>
              </article>
            );
          })}
        </div>

        <div className="mt-10 flex flex-wrap items-center gap-3 font-mono text-xs text-muted-foreground">
          <span>Session R0 scaffold complete</span>
          <ArrowRight className="size-4 text-primary" aria-hidden="true" />
          <span>Next target: R1 research index page</span>
        </div>
      </section>
    </main>
  );
}
