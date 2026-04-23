"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ThemeSwitcher from "../ThemeSwitcher";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

export default function HowItWorksPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.title = "Vektor - How It Works";
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
          <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png?v=20260422b" alt="Vektor Logo" style={{ height: "48px", width: "auto", objectFit: "contain" }} />
            <span>Vektor <em>Fund OS</em></span>
          </a>
          <nav className="hero-actions" style={{ alignItems: 'center' }}>
            <Link className="btn ghost" href="/">Back to Home</Link>
            <a className="btn primary" href={`${productUrl}/admin`}>Admin Console</a>
            <div style={{ width: '1px', height: '24px', background: 'var(--line)', margin: '0 8px' }} />
            <ThemeSwitcher />
          </nav>
        </div>
      </header>

      <main className="container overflow-hidden" style={{ padding: '120px 24px' }}>
        <div className="cinematic-fade">
          <h1 style={{ fontSize: 'clamp(40px, 7vw, 64px)', marginBottom: '24px', letterSpacing: '-0.03em' }}>How Vektor Works</h1>
          <p style={{ color: 'var(--muted)', fontSize: 'clamp(18px, 2.5vw, 22px)', maxWidth: '800px', marginBottom: '80px', lineHeight: '1.6' }}>
            Vektor is an AI-native hedge fund operating system. We orchestrate multiple specialized agents, enforce strict safety constraints, and log every decision for complete transparency. No black boxes. No hidden logic. Every trade is explainable.
          </p>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>1. Data Ingestion & Analysis</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '20px', lineHeight: '1.8' }}>
            Vektor continuously reads market data from multiple sources: news feeds, financial statements, technical indicators, and macro events. Our Research Agent processes thousands of data points to identify patterns humans might miss.
          </p>
          <ul style={{ color: 'var(--muted)', paddingLeft: '24px', marginBottom: '0' }}>
            <li style={{ marginBottom: '12px' }}>ðŸ“° News Analysis: Real-time financial news with sentiment scoring</li>
            <li style={{ marginBottom: '12px' }}>ðŸ“Š Technical Signals: Price action, volume, momentum indicators</li>
            <li style={{ marginBottom: '12px' }}>ðŸ’¹ Macro Data: Interest rates, GDP, employment, inflation</li>
            <li style={{ marginBottom: '12px' }}>ðŸ“ˆ Company Fundamentals: Earnings, growth rates, valuations</li>
          </ul>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>2. Decision Making (The Fund Manager Agent)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '20px', lineHeight: '1.8' }}>
            The Fund Manager synthesizes all research into a clear trading thesis. It proposes specific trades with explicit reasoning: why BUY Apple, or why SELL Tesla. Every decision is tied to evidence and sources.
          </p>
          <pre style={{ background: '#070a0f', padding: '20px', borderRadius: '8px', border: '1px solid var(--line)', overflowX: 'auto', marginBottom: '20px' }}>
            <code style={{ color: 'var(--accent)', fontSize: '13px' }}>
{`DECISION PROPOSAL:
Symbol: AAPL
Action: BUY 500 shares
Price Target: $185
Rationale: Q2 earnings beat expectations (+12% revenue), 
strong iPhone demand signals, services growing 20% YoY.
Sources: SEC filing, analyst reports, earnings call.
Confidence: 82%
Risk Level: MODERATE`}
            </code>
          </pre>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>3. Risk Assessment (The Auditor)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '20px', lineHeight: '1.8' }}>
            Before any trade executes, our Risk Auditor runs independent checks. This is a separate agent with its own logicâ€”it doesn't blindly follow the Fund Manager. It validates:
          </p>
          <ul style={{ color: 'var(--muted)', paddingLeft: '24px', marginBottom: '20px' }}>
            <li style={{ marginBottom: '12px' }}>âœ“ Position sizing: Are we risking too much?</li>
            <li style={{ marginBottom: '12px' }}>âœ“ Portfolio concentration: Too much in one sector?</li>
            <li style={{ marginBottom: '12px' }}>âœ“ Volatility limits: Is this trade too risky right now?</li>
            <li style={{ marginBottom: '12px' }}>âœ“ Regulatory compliance: Does this violate fund rules?</li>
            <li style={{ marginBottom: '12px' }}>âœ“ Circuit breakers: Is the market in a stressed state?</li>
          </ul>
          <p style={{ color: 'var(--muted)', lineHeight: '1.8' }}>
            If ANY check fails, the trade is REJECTED. No exceptions. No override without manual approval.
          </p>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>4. Paper Trading First (The Execution Layer)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '20px', lineHeight: '1.8' }}>
            All trades start in PAPER MODEâ€”simulated execution with fake money. This lets us validate our strategies without real capital at risk. You can:
          </p>
          <ul style={{ color: 'var(--muted)', paddingLeft: '24px', marginBottom: '20px' }}>
            <li style={{ marginBottom: '12px' }}>ðŸ“Š Watch performance over time</li>
            <li style={{ marginBottom: '12px' }}>ðŸ” Review decision logic in the admin console</li>
            <li style={{ marginBottom: '12px' }}>â¸ï¸ Pause or override any trade</li>
            <li style={{ marginBottom: '12px' }}>ðŸŽ“ Learn why each decision was made</li>
          </ul>
          <p style={{ color: 'var(--muted)', lineHeight: '1.8' }}>
            Only after you're confident and have explicitly enabled live trading does real capital get deployed.
          </p>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>5. Complete Auditability (The Memory Layer)</h2>
          <p style={{ color: 'var(--muted)', marginBottom: '20px', lineHeight: '1.8' }}>
            Every decision is permanently recorded in our knowledge graph. You can query the entire history:
          </p>
          <pre style={{ background: '#070a0f', padding: '20px', borderRadius: '8px', border: '1px solid var(--line)', overflowX: 'auto', marginBottom: '20px' }}>
            <code style={{ color: 'var(--accent)', fontSize: '13px' }}>
{`EVENT LOG:
2026-04-19 14:32:01 - Research Agent: Detected positive earnings
2026-04-19 14:32:15 - Fund Manager: Proposed BUY signal
2026-04-19 14:32:20 - Risk Auditor: Approved trade
2026-04-19 14:32:21 - Execution Engine: Executed in paper mode
2026-04-19 14:45:00 - User: Reviewed decision, clicked "I understand"
2026-04-19 14:45:05 - System: Ready to execute in live mode`}
            </code>
          </pre>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>Key Features</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', marginTop: '24px' }}>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ” Cryptographic Signatures</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>Every event in the system is signed. No tampering possible. Complete audit trail.</p>
            </div>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ¤– Multi-Agent Orchestration</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>Independent agents with different objectives. No single point of failure.</p>
            </div>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ“ˆ Live Performance Tracking</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>Public PnL page shows exactly how well we're doing. No hidden metrics.</p>
            </div>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ›‘ Hard Safety Stops</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>Circuit breakers automatically pause trading during market stress.</p>
            </div>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ‘¤ Manual Override</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>You can pause, review, or reject any trade at any time.</p>
            </div>
            <div style={{ padding: '20px', background: 'var(--surface)', borderRadius: '8px' }}>
              <h3 style={{ margin: '0 0 12px', color: 'var(--text)', fontSize: '18px' }}>ðŸ“š Explainable AI</h3>
              <p style={{ margin: '0', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6' }}>Every decision linked to sources and reasoning. No black boxes.</p>
            </div>
          </div>
        </div>

        <div className="dark-card cinematic-fade" style={{ marginBottom: '60px', background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.1) 0%, rgba(249, 115, 22, 0.1) 100%)' }}>
          <h2 style={{ fontSize: '32px', marginBottom: '24px', color: 'var(--text)' }}>Getting Started</h2>
          <ol style={{ color: 'var(--muted)', paddingLeft: '24px' }}>
            <li style={{ marginBottom: '16px', lineHeight: '1.8' }}>
              <strong style={{ color: 'var(--text)' }}>Launch Admin Console</strong> - Connect to your broker and set up your strategy
            </li>
            <li style={{ marginBottom: '16px', lineHeight: '1.8' }}>
              <strong style={{ color: 'var(--text)' }}>Start in Paper Mode</strong> - Vektor trades with fake money first so you can learn
            </li>
            <li style={{ marginBottom: '16px', lineHeight: '1.8' }}>
              <strong style={{ color: 'var(--text)' }}>Review Decisions</strong> - Check the admin console to see why each trade was made
            </li>
            <li style={{ marginBottom: '16px', lineHeight: '1.8' }}>
              <strong style={{ color: 'var(--text)' }}>Enable Live Trading</strong> - When you're confident, unlock real capital deployment
            </li>
            <li style={{ marginBottom: '0', lineHeight: '1.8' }}>
              <strong style={{ color: 'var(--text)' }}>Monitor Performance</strong> - Check public PnL page for live results
            </li>
          </ol>
          <div style={{ marginTop: '32px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <a className="btn primary" href={productUrl} style={{ padding: '12px 32px' }}>Open Admin Console</a>
            <Link className="btn ghost" href="/" style={{ padding: '12px 32px' }}>Back to Home</Link>
          </div>
        </div>

      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Vektor Fund OS â€¢ Technical Documentation</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <Link href="/">Back to Home</Link>
                 <Link href="/blog">Blog</Link>
                 <a href={productUrl}>PnL</a>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}


