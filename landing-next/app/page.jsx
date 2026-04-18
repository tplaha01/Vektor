"use client";

import { useEffect } from "react";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

export default function Page() {
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll("[data-reveal]"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
          }
        });
      },
      { threshold: 0.15 }
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div className="particle-field" aria-hidden="true" />
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand">Viktor <em>Fund OS</em></a>
          <div className="hero-actions">
            <a className="btn ghost" href="#how">How It Works</a>
            <a className="btn ghost" href="#safety">Safety</a>
            <a className="btn primary" href={productUrl}>Open Live Product</a>
          </div>
        </div>
      </header>

      <main className="container">
        <section className="hero" data-reveal>
          <p className="eyebrow">AI-Native Hedge Fund Operating System</p>
          <h1>A calm, transparent trading brain you can actually understand.</h1>
          <p>
            Think of Viktor like a team of specialists in one control room. One part researches,
            one part checks risk, one part executes. Every decision is recorded so you can inspect
            exactly what happened and why.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href={productUrl}>Go To Product Console</a>
            <a className="btn ghost" href="/legacy">Open Legacy Workspace</a>
          </div>
          <div className="hero-stats">
            <span className="pill">Paper-first execution</span>
            <span className="pill">Traceable decisions</span>
            <span className="pill">Role-based orchestration</span>
          </div>
        </section>

        <section className="grid" id="how" data-reveal>
          <article className="card">
            <h3>1. Research</h3>
            <p>Specialist agents read market data and news, then produce reports with source links.</p>
          </article>
          <article className="card">
            <h3>2. Decide</h3>
            <p>The fund manager forms a thesis, sleeve, and execution intent tied to a decision ID.</p>
          </article>
          <article className="card">
            <h3>3. Guard</h3>
            <p>Risk and policy checks must pass before any trade intent reaches execution.</p>
          </article>
          <article className="card">
            <h3>4. Execute</h3>
            <p>Orders execute in paper mode while timelines log every step for audits and review.</p>
          </article>
        </section>

        <section className="section split" id="safety" data-reveal>
          <article className="card">
            <h2>Safety by default</h2>
            <ul>
              <li>Paper mode is the default execution path.</li>
              <li>Strict real-data checks can halt unsafe workflows automatically.</li>
              <li>Runtime controls let operators pause, resume, and clear halts quickly.</li>
            </ul>
          </article>
          <article className="card">
            <h2>Clear mental model</h2>
            <ul>
              <li>Public PnL page for simple daily visibility.</li>
              <li>Admin portal for deep control and audit-level detail.</li>
              <li>Research and blog layers for explainability, not black boxes.</li>
            </ul>
          </article>
        </section>

        <section className="section" data-reveal>
          <div className="warning">
            This system is intentionally paper-first today. Live capital routing should only be enabled
            after formal compliance, controls, and monitoring sign-off.
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">Viktor Fund OS • Orchestrated multi-agent trading • Explainable by design</div>
      </footer>
    </>
  );
}
