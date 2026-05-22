import Link from "next/link";
import { SiteFooter, SiteHeader } from "../../components/site-chrome";
import { operatingFacts, platformPillars, productUrl } from "../../lib/site";

export const metadata = {
  title: "Platform",
  description:
    "Vektor platform overview: data warehouse, deterministic signal engine, risk policy, paper execution, and operator console.",
  alternates: {
    canonical: "/platform",
  },
};

export default function PlatformPage() {
  return (
    <>
      <SiteHeader active="platform" />
      <main className="firm-main">
        <section className="firm-page-hero">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Platform</p>
              <h1>One operating surface for data, signals, risk, and paper execution.</h1>
            </div>
            <p className="firm-lede">
              Vektor is organized as an operating platform, not a single strategy
              page. The product connects provider ingest, feature construction,
              decision policy, portfolio checks, paper broker routing, and admin
              recovery tools.
            </p>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-card-grid">
            {platformPillars.map((pillar) => (
              <article className="firm-card" key={pillar.title}>
                <span>{pillar.label}</span>
                <h2>{pillar.title}</h2>
                <p>{pillar.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Admin console</p>
              <h2>The admin section is the control room.</h2>
              <p className="firm-section-copy">
                The console should show runtime posture, system health, portfolio
                state, data pipeline status, risk controls, recovery actions, and
                paper-broker state. A halted system is an operating condition to
                resolve, not a dead end.
              </p>
              <a className="btn primary" href={`${productUrl}/admin`}>
                Open console
              </a>
            </div>
            <div className="firm-matrix">
              {operatingFacts.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-feature-row">
            <Link className="firm-link-block" href="/operating-model">
              <span>Workflow</span>
              <h2>See how orders are supposed to move through the system.</h2>
              <p>Universe, evidence, features, risk gate, paper broker, ledger.</p>
            </Link>
            <Link className="firm-link-block" href="/data">
              <span>Data</span>
              <h2>Inspect the ingest and feature foundation.</h2>
              <p>Raw events, market data, text events, fundamentals, features, health.</p>
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
