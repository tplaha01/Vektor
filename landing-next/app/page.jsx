"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Activity, ArrowRight, FileText, LineChart, ShieldCheck } from "lucide-react";
import LiquidBackground from "../components/liquid-background";
import { SiteFooter, SiteHeader } from "../components/site-chrome";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

const operatingLoop = [
  {
    title: "Research intake",
    description: "Signals, transcripts, macro prints, and price action arrive as structured evidence rather than loose prompts.",
  },
  {
    title: "Manager synthesis",
    description: "The fund manager converts raw context into a thesis with explicit sizing, time horizon, and risk assumptions.",
  },
  {
    title: "Risk gate",
    description: "Independent auditors challenge concentration, liquidity, volatility, and policy fit before anything moves forward.",
  },
  {
    title: "Paper-first execution",
    description: "Every decision is observable in simulation before real capital is allowed to touch the market.",
  },
];

const heroSignals = [
  { label: "Mode", value: "Paper first", detail: "Live capital stays gated" },
  { label: "Control", value: "Risk veto", detail: "Independent review before execution" },
  { label: "Memory", value: "Full lineage", detail: "Every thesis, override, and result retained" },
];

const consoleRows = [
  { label: "Research", value: "NVDA momentum thesis queued", status: "evidence mapped" },
  { label: "Risk", value: "Concentration check active", status: "limits enforced" },
  { label: "Execution", value: "Paper book only", status: "capital locked" },
];

const principles = [
  {
    title: "Explainable by default",
    description: "Every trade carries its rationale, supporting evidence, and approval trail. Investor communication is built into the workflow, not bolted on afterward.",
  },
  {
    title: "Risk owns the tempo",
    description: "Vektor is optimized for disciplined pace rather than maximum trade count. The system slows down before it lets uncertainty compound.",
  },
  {
    title: "Built for operators",
    description: "Research, allocation, overrides, and post-trade review live in one operating surface so the system feels governable under pressure.",
  },
];

const team = [
  {
    label: "Research",
    title: "Research agent",
    description: "Collects market context and turns noisy information flow into ranked opportunities with supporting receipts.",
  },
  {
    label: "Manager",
    title: "Fund manager",
    description: "Frames the trade thesis, capital plan, and expected path before any execution route is considered.",
  },
  {
    label: "Risk",
    title: "Risk auditor",
    description: "Runs independent checks on sizing, liquidity, concentration, and stress scenarios with veto power.",
  },
  {
    label: "Control",
    title: "Compliance memory",
    description: "Logs the full decision chain so monitoring, review, and investor reporting stay consistent after the trade is live.",
  },
];

const proofPoints = [
  {
    title: "Public visibility",
    items: [
      "Live PnL is visible without asking for a quarterly update.",
      "Research notes and operating decisions are readable by humans.",
      "Paper trading stays available as the default proving ground.",
    ],
  },
  {
    title: "Capital controls",
    items: [
      "No trade ships without a separate risk opinion.",
      "Hard limits govern concentration and stress events.",
      "Manual review can pause or override the machine layer at any point.",
    ],
  },
];

export default function Page() {
  useEffect(() => {
    document.title = "Vektor | AI-Native Fund OS";

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
      <LiquidBackground />
      <SiteHeader active="home" />

      <main className="overflow-hidden">
        <section className="container hero cinematic-fade revealed">
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="eyebrow">AI-native hedge fund operating system</p>
              <h1 className="hero-title">
                Vektor
              </h1>
              <p className="hero-subtitle">Capital management that stays legible under pressure.</p>
              <p className="hero-text">
                A paper-first operating stack for research, thesis generation, risk review,
                and execution oversight. Built to read like an institutional control room,
                not a black-box trading bot.
              </p>
              <div className="hero-actions">
                <a className="btn primary" href={productUrl}>
                  <LineChart size={18} aria-hidden="true" />
                  View live fund performance
                </a>
                <Link className="btn ghost" href="/how-it-works">
                  <FileText size={18} aria-hidden="true" />
                  Explore the operating model
                </Link>
              </div>

              <div className="hero-stats" aria-label="Vektor operating guarantees">
                {heroSignals.map((signal) => (
                  <div key={signal.label} className="hero-stat">
                    <span>{signal.label}</span>
                    <strong>{signal.value}</strong>
                    <p>{signal.detail}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside className="hero-panel" aria-label="Vektor live operating console preview">
              <div className="panel-topline">
                <span className="panel-label">Operating console</span>
                <span className="panel-status">
                  <Activity size={14} aria-hidden="true" />
                  Controlled
                </span>
              </div>
              <h2 className="panel-title">A fund workflow with explicit checkpoints.</h2>
              <p className="panel-copy">
                Vektor separates research, decisioning, review, and execution so one fast answer
                does not become one unchecked position.
              </p>

              <div className="console-display">
                {consoleRows.map((row) => (
                  <div key={row.label} className="console-row">
                    <span className="console-label">{row.label}</span>
                    <strong>{row.value}</strong>
                    <span className="console-status">{row.status}</span>
                  </div>
                ))}
              </div>

              <ol className="panel-stack">
                {operatingLoop.map((step, index) => (
                  <li key={step.title} className="loop-step">
                    <span className="loop-index">0{index + 1}</span>
                    <span>
                      <strong>{step.title}</strong>
                      <em>{step.description}</em>
                    </span>
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </section>

        <section className="section cinematic-fade revealed">
          <div className="container">
            <div className="section-head">
              <p className="section-kicker">Why it feels different</p>
              <h2 className="section-title">The product is built around trust, not just signal throughput.</h2>
              <p className="section-copy">
                The experience should help an allocator understand what the system is doing,
                why it is doing it, and when it should slow down.
              </p>
            </div>

            <div className="grid principle-grid">
              {principles.map((item) => (
                <article key={item.title} className="dark-card">
                  <ShieldCheck className="card-icon" size={22} aria-hidden="true" />
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container two-up">
            {proofPoints.map((block) => (
              <article key={block.title} className="dark-card">
                <p className="section-kicker">Control layer</p>
                <h2>{block.title}</h2>
                <ul className="detail-list">
                  {block.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container">
            <div className="section-head">
              <p className="section-kicker">Agent bench</p>
              <h2 className="section-title">Each role has one job and one point of view.</h2>
              <p className="section-copy">
                The system stays readable because the responsibilities stay narrow. Research finds.
                The manager frames. Risk challenges. Control records.
              </p>
            </div>

            <div className="grid agent-grid">
              {team.map((member) => (
                <article key={member.title} className="dark-card">
                  <p className="post-eyebrow">{member.label}</p>
                  <h3>{member.title}</h3>
                  <p>{member.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section cinematic-fade">
          <div className="container">
            <div className="article-shell">
              <div className="article-header">
                <p className="section-kicker">Start here</p>
                <h2 className="section-title">Use paper mode to understand the system before you trust it.</h2>
                <p className="section-copy">
                  Vektor is intentionally opinionated about rollout. You monitor the simulated book,
                  review the decision logs, and only then allow live capital into the loop.
                </p>
              </div>
              <div className="article-nav">
                <a className="btn primary" href={`${productUrl}/admin`}>
                  <ShieldCheck size={18} aria-hidden="true" />
                  Open the admin console
                </a>
                <Link className="btn ghost" href="/how-it-works">
                  <ArrowRight size={18} aria-hidden="true" />
                  Read the technical walkthrough
                </Link>
                <Link className="btn ghost" href="/blog">
                  <FileText size={18} aria-hidden="true" />
                  Review recent research
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}
