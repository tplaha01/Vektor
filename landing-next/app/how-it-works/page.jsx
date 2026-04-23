"use client";

import { useEffect } from "react";
import Link from "next/link";
import { SiteFooter, SiteHeader } from "../../components/site-chrome";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

const workflow = [
  {
    step: "01",
    title: "Ingest and rank market evidence",
    description:
      "News flow, fundamentals, macro releases, and technical state enter the system as structured context. Research is stored with sources so later review is possible.",
    bullets: [
      "Real-time market and macro feeds",
      "Fundamental updates and earnings context",
      "Signal ranking before trade construction begins",
    ],
  },
  {
    step: "02",
    title: "Build a trade thesis",
    description:
      "The fund manager agent converts raw evidence into a position proposal with direction, sizing, confidence, and exit assumptions.",
    bullets: [
      "Clear thesis with time horizon and sizing",
      "Named catalysts and expected failure modes",
      "Readable rationale instead of opaque output",
    ],
  },
  {
    step: "03",
    title: "Challenge the idea with risk",
    description:
      "A separate risk layer checks volatility, correlation, liquidity, portfolio concentration, and policy constraints before the trade can move ahead.",
    bullets: [
      "Independent risk opinion before execution",
      "Circuit breakers for stressed conditions",
      "Hard stops on concentration and exposure",
    ],
  },
  {
    step: "04",
    title: "Execute in paper mode first",
    description:
      "Strategies prove themselves in simulation while operators review the logic, fills, and controls. Live trading stays an explicit unlock, not the default state.",
    bullets: [
      "Simulated fills for workflow validation",
      "Operator review before live capital is enabled",
      "Continuous monitoring in the admin surface",
    ],
  },
  {
    step: "05",
    title: "Keep the memory layer intact",
    description:
      "Every decision is stored with supporting context so you can inspect the full history of a position after it is opened, closed, or overridden.",
    bullets: [
      "Decision lineage tied to each trade",
      "Reviewable overrides and operator actions",
      "Audit-friendly history for post-trade analysis",
    ],
  },
];

const guarantees = [
  {
    title: "Paper-first rollout",
    description: "The system begins in simulation so operators can learn the workflow, validate assumptions, and inspect controls before any live capital is at risk.",
  },
  {
    title: "Readable decisions",
    description: "Each proposal includes why the trade exists, what data supported it, and what conditions would invalidate it.",
  },
  {
    title: "Manual control",
    description: "Humans can pause, review, reject, or tighten constraints whenever the environment no longer matches the system's assumptions.",
  },
  {
    title: "Persistent memory",
    description: "Research, approvals, trade events, and overrides remain queryable so performance review is grounded in evidence.",
  },
];

export default function HowItWorksPage() {
  useEffect(() => {
    document.title = "How It Works | Vektor";

    const nodes = Array.from(document.querySelectorAll(".cinematic-fade"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <SiteHeader active="how" />

      <main className="page-shell overflow-hidden">
        <section className="container page-masthead cinematic-fade">
          <p className="page-kicker">System walkthrough</p>
          <h1>How Vektor turns research into governed execution.</h1>
          <p>
            The platform is designed to show its work. Research enters first, the manager frames a
            trade, risk challenges the idea, and paper-mode execution proves the workflow before real
            capital gets involved.
          </p>
          <div className="hero-actions" style={{ marginTop: "28px" }}>
            <a className="btn primary" href={`${productUrl}/admin`}>
              Open admin console
            </a>
            <a className="btn ghost" href={productUrl}>
              Watch live PnL
            </a>
            <Link className="btn ghost" href="/blog">
              Read research notes
            </Link>
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container">
            <div className="section-head">
              <p className="section-kicker">Workflow</p>
              <h2 className="section-title">Five stages keep speed from outrunning controls.</h2>
            </div>
            <div className="process-grid">
              {workflow.map((item) => (
                <article key={item.step} className="dark-card" style={{ gridColumn: "span 12" }}>
                  <div className="meta-strip">
                    <span className="tag">Step {item.step}</span>
                  </div>
                  <h2 style={{ marginTop: "16px" }}>{item.title}</h2>
                  <p style={{ marginTop: "14px" }}>{item.description}</p>
                  <ul className="detail-list" style={{ marginTop: "18px" }}>
                    {item.bullets.map((bullet) => (
                      <li key={bullet}>{bullet}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container two-up">
            <article className="article-shell">
              <div className="article-header">
                <p className="section-kicker">Example decision frame</p>
                <h2 className="section-title">A proposal is expected to read like an investment memo.</h2>
              </div>
              <div className="article-content">
                <pre>
                  <code>{`Trade proposal
Symbol: AAPL
Action: Buy
Thesis: Earnings strength and improving services mix support upside.
Sizing: 2.5% starter allocation
Risk gate: Pass only if concentration and volatility remain inside limits.
Execution mode: Paper until operator approval for live deployment.`}</code>
                </pre>
              </div>
            </article>

            <article className="article-shell">
              <div className="article-header">
                <p className="section-kicker">Memory layer</p>
                <h2 className="section-title">Every trade keeps its receipts.</h2>
              </div>
              <div className="article-content">
                <pre>
                  <code>{`Event log
14:32:01 Research agent flagged earnings momentum
14:32:15 Fund manager proposed long thesis
14:32:20 Risk auditor approved paper-mode execution
14:32:21 Execution engine routed simulated order
14:45:00 Operator reviewed rationale in admin console`}</code>
                </pre>
              </div>
            </article>
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container">
            <div className="section-head">
              <p className="section-kicker">System guarantees</p>
              <h2 className="section-title">The UI should reinforce discipline, not hide it.</h2>
            </div>
            <div className="grid">
              {guarantees.map((item) => (
                <article key={item.title} className="dark-card">
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>

      <SiteFooter
        eyebrow="Vektor architecture"
        description="Research, risk, and execution stay separated so the operator always has a clear control surface."
      />
    </>
  );
}
