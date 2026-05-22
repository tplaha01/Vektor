import Link from "next/link";
import { SiteFooter, SiteHeader } from "../components/site-chrome";
import {
  baseUrl,
  dataAssets,
  operatingFacts,
  operatingStages,
  platformPillars,
  productUrl,
  riskControls,
} from "../lib/site";

export const metadata = {
  title: "Deterministic ML Trading Operations Platform",
  description:
    "Vektor is a paper-first trading operations platform for deterministic ML signals, data lineage, risk gates, paper execution, and decision auditability.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Vektor | Deterministic ML Trading Operations Platform",
    description:
      "Paper-first trading operations with deterministic ML signals, market data lineage, risk gates, and auditable execution.",
    url: "/",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Vektor",
  applicationCategory: "FinanceApplication",
  operatingSystem: "Web",
  url: baseUrl,
  description:
    "A deterministic ML trading operations platform for paper-first portfolio automation, market data ingest, risk controls, and decision auditability.",
  offers: {
    "@type": "Offer",
    availability: "https://schema.org/InStock",
    price: "0",
    priceCurrency: "USD",
  },
  featureList: [
    "Paper-first trading operations",
    "Market data ingest and lineage",
    "Deterministic ML signal workflow",
    "Pre-trade risk gates",
    "Decision and execution audit trail",
  ],
};

export default function Home() {
  const systemState = [
    ["Posture", "Paper execution, live trading disabled by default"],
    ["Signal mode", "Deterministic ML features and rule-based fallback"],
    ["AI layer", "Deferred; adapters remain policy-gated"],
    ["Evidence", "Prices, quotes, bars, news, fundamentals, feature vectors"],
    ["Audit", "Decision ledger, risk gate, operator controls"],
  ];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <SiteHeader active="home" />
      <main className="firm-main">
        <section className="firm-hero">
          <div className="container firm-hero-grid">
            <div className="firm-hero-copy">
              <p className="firm-kicker">Trading operations, not trading theater</p>
              <h1>Deterministic ML infrastructure for paper-traded portfolios.</h1>
              <p className="firm-lede">
                Vektor connects market data ingest, feature generation, signal policy,
                portfolio risk checks, paper execution, and operator audit into one
                governed operating surface.
              </p>
              <div className="firm-actions">
                <a className="btn primary" href={`${productUrl}/admin`}>
                  Open console
                </a>
                <Link className="btn ghost" href="/operating-model">
                  Review operating model
                </Link>
              </div>
            </div>

            <aside className="firm-panel" aria-label="Current operating posture">
              <div className="firm-panel-head">
                <p>Current posture</p>
                <span>Paper mode</span>
              </div>
              <div className="firm-state-table">
                {systemState.map(([label, value]) => (
                  <div className="firm-state-row" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Definition</p>
              <h2>Vektor is an operating layer for systematic trading workflows.</h2>
            </div>
            <div className="firm-definition-grid">
              <div className="firm-callout">
                <h3>What it is</h3>
                <p>
                  A deterministic, paper-first platform for proving data coverage,
                  signal behavior, risk policy, execution routing, and portfolio
                  observability before live capital is considered.
                </p>
              </div>
              <div className="firm-callout muted">
                <h3>What it is not</h3>
                <p>
                  It is not an audited fund track record, not an investment adviser,
                  and not a promise that AI will discover alpha. The current system is
                  built to validate operations first.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container">
            <div className="firm-section-head">
              <p className="firm-kicker">Platform</p>
              <h2>Built around the controls a trading system actually needs.</h2>
              <p>
                Each layer has a job: collect evidence, construct deterministic
                features, approve or block risk, route paper orders, and preserve the
                record.
              </p>
            </div>
            <div className="firm-card-grid">
              {platformPillars.map((pillar) => (
                <Link className="firm-card" href="/platform" key={pillar.title}>
                  <span>{pillar.label}</span>
                  <h3>{pillar.title}</h3>
                  <p>{pillar.description}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section">
          <div className="container">
            <div className="firm-section-head">
              <p className="firm-kicker">Operating model</p>
              <h2>The workflow is intentionally sequential and reviewable.</h2>
            </div>
            <div className="firm-timeline">
              {operatingStages.map((stage) => (
                <div className="firm-step" key={stage.step}>
                  <span>{stage.step}</span>
                  <h3>{stage.title}</h3>
                  <p>{stage.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Data and ML readiness</p>
              <h2>The ingest layer exists so ML work can be measured, replayed, and audited.</h2>
              <p className="firm-section-copy">
                Current model behavior is deterministic. The data section is the
                foundation for future training, backtests, feature replay, and
                production-grade model monitoring.
              </p>
              <Link className="firm-text-link" href="/data">
                Inspect data model
              </Link>
            </div>
            <div className="firm-asset-list">
              {dataAssets.slice(0, 6).map(([name, description]) => (
                <div className="firm-asset-row" key={name}>
                  <strong>{name}</strong>
                  <span>{description}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-feature-row">
            <Link className="firm-link-block" href="/risk">
              <span>Risk</span>
              <h2>Paper-first by default, gated before execution.</h2>
              <p>{riskControls.slice(0, 3).join(". ")}.</p>
            </Link>
            <Link className="firm-link-block" href="/performance">
              <span>Performance</span>
              <h2>Paper record, disclosed as paper record.</h2>
              <p>
                The product surface tracks paper PnL, open positions, decision
                history, and runtime state. It is not marketed as audited live returns.
              </p>
            </Link>
          </div>
        </section>

        <section className="firm-section firm-cta-section">
          <div className="container firm-cta">
            <div>
              <p className="firm-kicker">Operating facts</p>
              <h2>Transparent enough to inspect before you trust it.</h2>
            </div>
            <div className="firm-facts">
              {operatingFacts.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
