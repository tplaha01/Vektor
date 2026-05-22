import { SiteFooter, SiteHeader } from "../../components/site-chrome";
import { operatingStages, productUrl } from "../../lib/site";

export const metadata = {
  title: "Operating Model",
  description:
    "How Vektor moves from market evidence to deterministic ML features, risk approval, paper execution, ledgering, and operator review.",
  alternates: {
    canonical: "/operating-model",
  },
};

const responsibilities = [
  ["Data pipeline", "Normalize provider payloads and track freshness before features are trusted."],
  ["Signal engine", "Build deterministic technical, fundamental, sentiment, and ML-ready feature frames."],
  ["Risk gate", "Approve, size, reduce, or block proposals before any broker action."],
  ["Paper broker", "Execute only approved paper orders and return fills to the ledger."],
  ["Operator", "Review posture, override runtime mode, recover halted systems, and inspect the record."],
];

export default function OperatingModelPage() {
  return (
    <>
      <SiteHeader active="operating" />
      <main className="firm-main">
        <section className="firm-page-hero">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Operating model</p>
              <h1>A deterministic path from evidence to paper execution.</h1>
            </div>
            <p className="firm-lede">
              Vektor should make every trading decision reconstructable. The
              workflow is designed so an operator can see which inputs existed,
              which checks ran, and why a proposal was approved or blocked.
            </p>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-timeline">
            {operatingStages.map((stage) => (
              <article className="firm-step" key={stage.step}>
                <span>{stage.step}</span>
                <h2>{stage.title}</h2>
                <p>{stage.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container">
            <div className="firm-section-head">
              <p className="firm-kicker">Responsibilities</p>
              <h2>Each layer owns a narrow operating responsibility.</h2>
            </div>
            <div className="firm-matrix wide">
              {responsibilities.map(([owner, responsibility]) => (
                <div key={owner}>
                  <span>{owner}</span>
                  <strong>{responsibility}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Execution posture</p>
              <h2>Paper first is the production posture.</h2>
            </div>
            <div>
              <p className="firm-section-copy">
                The current operating model prioritizes proving data quality,
                feature behavior, risk policy, and order lifecycle integrity before
                AI-assisted allocation or live trading is introduced.
              </p>
              <a className="btn primary" href={`${productUrl}/admin`}>
                Open admin console
              </a>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
