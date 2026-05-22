import { SiteFooter, SiteHeader } from "../../components/site-chrome";
import { dataAssets } from "../../lib/site";

export const metadata = {
  title: "Data Pipeline",
  description:
    "Vektor data pipeline overview: market data ingest, news and fundamentals, feature vectors, provider health, lineage, and ML readiness.",
  alternates: {
    canonical: "/data",
  },
};

const qualityGates = [
  ["Freshness", "Provider timestamps and last successful ingest are tracked before downstream use."],
  ["Completeness", "Symbols, bars, quotes, news, fundamentals, and feature vectors are separated so gaps are visible."],
  ["Lineage", "Raw provider events are preserved alongside normalized entities and monitoring snapshots."],
  ["Replayability", "The warehouse is structured for backtests, model evaluation, and production incident review."],
];

export default function DataPage() {
  return (
    <>
      <SiteHeader active="data" />
      <main className="firm-main">
        <section className="firm-page-hero">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Data pipeline</p>
              <h1>The ML stack starts with traceable market evidence.</h1>
            </div>
            <p className="firm-lede">
              Vektor ingests market prices, quotes, bars, text events,
              fundamentals, provider health, and feature vectors so future model
              work can be trained and evaluated against reconstructable inputs.
            </p>
          </div>
        </section>

        <section className="firm-section">
          <div className="container">
            <div className="firm-section-head">
              <p className="firm-kicker">Warehouse model</p>
              <h2>Data is split by operating purpose.</h2>
              <p>
                The current trading loop still uses deterministic feature logic.
                The warehouse gives the ML path the raw material for replay,
                training, monitoring, and audit once model work becomes the focus.
              </p>
            </div>
            <div className="firm-card-grid compact">
              {dataAssets.map(([name, description]) => (
                <article className="firm-card" key={name}>
                  <span>Data asset</span>
                  <h2>{name}</h2>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="firm-section firm-section-alt">
          <div className="container firm-two-col">
            <div>
              <p className="firm-kicker">Quality gates</p>
              <h2>Data quality has to be visible before models are trusted.</h2>
            </div>
            <div className="firm-matrix">
              {qualityGates.map(([gate, detail]) => (
                <div key={gate}>
                  <span>{gate}</span>
                  <strong>{detail}</strong>
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
