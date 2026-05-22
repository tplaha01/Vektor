import { SiteFooter, SiteHeader } from "../../components/site-chrome";
import { riskControls } from "../../lib/site";

export const metadata = {
  title: "Risk Controls",
  description:
    "Vektor risk controls for paper-first trading operations: runtime posture, pre-trade gates, drawdown controls, audit events, and operator override.",
  alternates: {
    canonical: "/risk",
  },
};

export default function RiskPage() {
  return (
    <>
      <SiteHeader active="risk" />
      <main className="firm-main">
        <section className="firm-page-hero">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Risk</p>
              <h1>Risk policy sits before execution, not after performance.</h1>
            </div>
            <p className="firm-lede">
              Vektor treats risk as an operating constraint. Runtime mode,
              exposure limits, data integrity, allocation policy, pre-trade gates,
              and operator overrides determine whether a trade can move forward.
            </p>
          </div>
        </section>

        <section className="firm-section">
          <div className="container firm-card-grid compact">
            {riskControls.map((control) => (
              <article className="firm-card" key={control}>
                <span>Control</span>
                <h2>{control}</h2>
              </article>
            ))}
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Runtime posture</p>
              <h2>A halt is a recoverable system state.</h2>
            </div>
            <p className="firm-section-copy">
              The admin console should distinguish between halted, paper, strict,
              and live-capable modes. For the current product posture, paper mode is
              the correct default and live execution remains disabled unless
              explicitly configured outside the landing site.
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
