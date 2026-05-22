import { SiteFooter, SiteHeader } from "../../components/site-chrome";
import { performanceDisclosures, productUrl } from "../../lib/site";

export const metadata = {
  title: "Performance",
  description:
    "Vektor performance views are paper-mode operating records for system validation, not audited live fund returns or investment advice.",
  alternates: {
    canonical: "/performance",
  },
};

const records = [
  ["Paper PnL", "Used to validate order lifecycle, holdings state, and strategy behavior in simulated execution."],
  ["Positions", "Shows current paper holdings and broker-synchronized state for operational review."],
  ["Decision history", "Links outcomes back to the inputs, checks, and controls that were present at decision time."],
  ["Benchmarks", "Provides context for paper results without treating them as audited performance."],
];

export default function PerformancePage() {
  return (
    <>
      <SiteHeader active="performance" />
      <main className="firm-main">
        <section className="firm-page-hero">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Performance</p>
              <h1>Paper performance is an operating record, not a sales claim.</h1>
            </div>
            <p className="firm-lede">
              Vektor tracks paper PnL, positions, benchmarks, and decision history
              so the system can be evaluated before live trading is considered.
            </p>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-card-grid">
            {records.map(([name, description]) => (
              <article className="firm-card" key={name}>
                <span>Record</span>
                <h2>{name}</h2>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Disclosure</p>
              <h2>The site should be clear about what is being measured.</h2>
              <a className="btn primary" href={productUrl}>
                Open paper PnL
              </a>
            </div>
            <div className="firm-disclosure-list">
              {performanceDisclosures.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
