"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";
const blogUrl = "http://localhost:3001";

export default function HowItWorksPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const nodes = Array.from(document.querySelectorAll(".cinematic-fade"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand">Viktor <em>Fund OS</em></a>
          <nav className="hero-actions">
            <Link className="btn ghost" href="/">Back to Home</Link>
            <a className="btn primary" href={`${productUrl}/admin`}>Admin Console</a>
          </nav>
        </div>
      </header>

      <main className="container overflow-hidden" style={{ padding: '120px 24px' }}>
        <div className="cinematic-fade">
          <h1 style={{ fontSize: 'clamp(40px, 7vw, 64px)', marginBottom: '24px', letterSpacing: '-0.03em' }}>Architecture & Mechanics</h1>
          <p style={{ color: 'var(--muted)', fontSize: 'clamp(18px, 2.5vw, 22px)', maxWidth: '800px', marginBottom: '80px', lineHeight: '1.6' }}>
            An under-the-hood look at how Viktor orchestrates specialized agents, manages risk limits, and executes trades with full cryptographic traceability.
          </p>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2>The Knowledge Graph (Memory Layer)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '24px', lineHeight: '1.6' }}>
            Viktor does not rely on short-term LLM context windows. Every event—whether it's an ingested news article, a computed RSI value, or a rejected trade—is written to a persistent, namespace-qualified graph database.
          </p>
          <pre style={{ background: '#070a0f', padding: '24px', borderRadius: '8px', overflowX: 'auto', border: '1px solid var(--line)' }}>
            <code style={{ color: 'var(--accent)' }}>
{`// Example Graph Mutation Event
{
  "event_id": "evt_9x8f7a",
  "namespace": "decision_ledger.intent",
  "timestamp": "2026-04-19T14:32:01Z",
  "actor": "fund_manager_agent",
  "action": "PROPOSE_TRADE",
  "payload": {
    "symbol": "AAPL",
    "direction": "LONG",
    "confidence": 0.89,
    "sources": ["doc_112", "doc_843"]
  },
  "parent_run_id": "run_alfa_99"
}`}
            </code>
          </pre>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2>Orchestration Flow</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '24px', lineHeight: '1.6' }}>
            When a new signal is generated, OpenClaw routes it through a strict policy gate pipeline. No single agent can execute a trade without multi-signature approval from the Risk and Audit nodes.
          </p>
          {mounted && (
            <div style={{ background: '#070a0f', padding: '32px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--line)' }}>
              {/* Note: In a real app, we'd use a mermaid component or render server side. 
                  Here we render the raw mermaid text which a markdown/mermaid parser would normally handle. */}
              <pre className="mermaid" style={{ color: 'var(--text)', margin: 0 }}>
{`graph TD
    A[Market Data API] --> B(Ingest Agent)
    B --> C{OpenClaw Router}
    C -->|Technical| D[Tech Analyst]
    C -->|Sentiment| E[Sentiment Analyst]
    D --> F[Fund Manager]
    E --> F
    F -->|Execution Intent| G{Risk Gate}
    G -->|Approved| H[Paper Broker]
    G -->|Rejected| I[Audit Log]
    H --> I`}
              </pre>
            </div>
          )}
          <p style={{ color: 'var(--muted)', marginTop: '24px', fontSize: '14px' }}>
            * Note: Diagram shows standard routing. The graph memory continuously indexes states at every edge.
          </p>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2>Safety Subsystem (Paper-First Constraints)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '24px', lineHeight: '1.6' }}>
            The system is hardcoded to reject live capital routing unless explicitly overridden by the `LIVE_TRADING_ENABLED` flag and a valid hardware-signed compliance token.
          </p>
          <pre style={{ background: '#070a0f', padding: '24px', borderRadius: '8px', overflowX: 'auto', border: '1px solid var(--line)' }}>
            <code style={{ color: 'var(--danger)' }}>
{`function enforceSafetyConstraints(intent) {
  if (config.executionMode !== 'PAPER') {
    if (!verifyComplianceToken(intent.approval_token)) {
      throw new Error("HALT: Invalid compliance token for live execution");
    }
  }
  return executeOrder(intent);
}`}
            </code>
          </pre>
        </div>
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Viktor Fund OS • Technical Documentation</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <Link href="/">Back to Home</Link>
                 <a href={blogUrl}>Blog</a>
                 <a href={productUrl}>PnL</a>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}
