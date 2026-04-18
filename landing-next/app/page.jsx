const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:5173";

export default function Page() {
  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand">
            Vektor <em>Capital</em>
          </a>
          <div className="hero-actions">
            <a className="btn ghost" href="#architecture">
              Architecture
            </a>
            <a className="btn primary" href={productUrl}>
              Open Product App
            </a>
          </div>
        </div>
      </header>

      <main className="container">
        <section className="hero">
          <div className="eyebrow">AI-Native Hedge Fund OS</div>
          <h1>Build Vektor as a real operating firm, paper-first.</h1>
          <p>
            Vektor separates marketing/SEO from trading operations: this Next.js SSR site is
            optimized for indexing, while the React product app runs the fund workflows,
            orchestration APIs, risk gates, and audit timelines.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href={productUrl}>
              Enter Trader Workspace
            </a>
            <a className="btn ghost" href="#ops">
              See Operating Model
            </a>
          </div>
          <div className="hero-stats">
            <span className="pill">Paper Trading Only</span>
            <span className="pill">Decision IDs End-to-End</span>
            <span className="pill">Risk Gate Before Execution</span>
          </div>
        </section>

        <section className="grid" id="architecture">
          <article className="card">
            <h3>Research Layer</h3>
            <p>
              Research and sentiment agents gather market/news inputs and create source-backed
              reports with provenance.
            </p>
          </article>
          <article className="card">
            <h3>Decision Layer</h3>
            <p>
              Fund manager and sleeve allocator transform theses into execution intents with
              immutable IDs and full lineage.
            </p>
          </article>
          <article className="card">
            <h3>Control Layer</h3>
            <p>
              Risk and audit agents enforce policy gates, block invalid actions, and maintain
              inspectable timelines for every order.
            </p>
          </article>
        </section>

        <section className="section split" id="ops">
          <article className="card">
            <h2>Operating sleeves</h2>
            <ul>
              <li>Long-term allocation sleeve for multi-month theses.</li>
              <li>Recurring investment sleeve for scheduled accumulation.</li>
              <li>Tactical sleeve for day/swing opportunities under strict limits.</li>
            </ul>
          </article>
          <article className="card">
            <h2>What runs where</h2>
            <ul>
              <li>Landing site: Next.js SSR (`landing-next`) for SEO and conversion.</li>
              <li>Product app: React/Vite (`frontend`) for dashboards and ops UI.</li>
              <li>Backend: FastAPI (`backend`) for orchestration, risk, execution, and audit.</li>
            </ul>
          </article>
        </section>

        <section className="section">
          <div className="warning">
            Live trading remains disabled by design. All execution flows are paper-first until you
            explicitly add a compliant live-trading program later.
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
          Vektor Capital OS • AI-native hedge fund architecture • paper-first mode
        </div>
      </footer>
    </>
  );
}
