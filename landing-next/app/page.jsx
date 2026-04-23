"use client";

import { useEffect } from "react";
import Link from "next/link";
import ThemeSwitcher from "./ThemeSwitcher";
import LiquidBackground from "../components/liquid-background";
import { Typewriter } from "../components/typewriter";
import { TextHighlighter } from "../components/text-highlighter";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

export default function Page() {
  useEffect(() => {
    document.title = "Vektor - Landing";
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
      <LiquidBackground />
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Vektor <em>AI Native Hedge Fund</em></span>
          </a>
          <nav className="hero-actions" style={{ alignItems: 'center' }}>
            <Link className="btn ghost" href="/how-it-works">How It Works</Link>
            <Link className="btn ghost" href="/blog">Blog</Link>
            <a className="btn ghost" href={productUrl}>Live PnL</a>
            <a className="btn primary" href={`${productUrl}/admin`}>Admin Console</a>
            <div style={{ width: '1px', height: '24px', background: 'var(--line)', margin: '0 8px' }} />
            <ThemeSwitcher />
          </nav>
        </div>
      </header>

      <main className="container overflow-hidden">
        <section className="hero cinematic-fade">
          <p className="eyebrow">The World's First Agentic AI Native Hedge Fund</p>
          <h1>
            <Typewriter 
              text="Intelligent capital management through autonomous AI agents."
              speed={30}
              delay={200}
            />
          </h1>
          <p>
            Vektor is a hedge fund powered by specialized AI agents that work in concert. Our research team identifies opportunities. Our analysts create strategies. Our risk auditors verify safety. Our compliance team ensures adherence. Every decision is transparent, every trade is explainable, and every investment is managed with institutional-grade rigor.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href={productUrl}>View Fund Performance</a>
            <Link className="btn ghost" href="/blog">Read Research</Link>
            <a className="btn ghost" href="/how-it-works">How We Invest</a>
          </div>
          <div className="hero-stats">
            <span className="pill">Institutional Transparency</span>
            <span className="pill">Autonomous AI Agents</span>
            <span className="pill">Explainable Decisions</span>
          </div>
        </section>

        <section className="grid cinematic-fade" id="how">
          <article className="dark-card">
            <h3>Research & Analysis</h3>
            <p>Our research agent processes market data, earnings reports, and economic indicators continuously. Identifies investment opportunities aligned with fund strategy and market conditions.</p>
          </article>
          <article className="dark-card">
            <h3>Strategy Development</h3>
            <p>The trading agent develops detailed investment strategies with clear entry/exit points, position sizing, and expected outcomes. Each strategy is thoroughly documented and explained.</p>
          </article>
          <article className="dark-card">
            <h3>Risk Verification</h3>
            <p>Independent risk agents audit every proposed position against fund parameters, market conditions, and regulatory requirements. Only compliant trades proceed to execution.</p>
          </article>
          <article className="dark-card">
            <h3>Execution & Recording</h3>
            <p>Verified trades are executed and permanently recorded. Full transaction history, rationale, and outcomes are tracked in our immutable audit trail.</p>
          </article>
        </section>

        <section className="section split cinematic-fade" id="safety">
          <article className="dark-card">
            <h2>Institutional Risk Management</h2>
            <ul>
              <li><strong>Multi-Layer Risk Review:</strong> Every position passes through independent risk auditors before execution.</li>
              <li><strong>Circuit Breakers:</strong> Automated safeguards halt trading during extreme market conditions to protect capital.</li>
              <li><strong>Investor Control:</strong> Monitor and adjust fund settings in real-time through your dashboard.</li>
            </ul>
          </article>
          <article className="dark-card">
            <h2>Complete Transparency</h2>
            <ul>
              <li><strong>Live Performance Tracking:</strong> View real-time fund performance, positions, and P&L on our public dashboard.</li>
              <li><strong>Decision Audit Trail:</strong> Access detailed logs of every trade with full rationale and supporting analysis.</li>
              <li><strong>Research Publication:</strong> Read detailed research reports from our team on market trends and strategy decisions.</li>
            </ul>
          </article>
        </section>

        <section className="section cinematic-fade" id="agents">
          <div className="section-intro">
            <h2 className="section-title">Our Autonomous Agent Team</h2>
            <p className="section-subtitle">A specialized team of AI agents working in concert to manage investments with transparency, rigor, and institutional-grade oversight.</p>
          </div>
          <div className="agents-grid">
            <article className="dark-card">
              <div className="agent-icon agent-label">Research</div>
              <h3>Research Agent</h3>
              <p>Continuously monitors market data, economic indicators, and news sources. Synthesizes information into actionable investment theses.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon agent-label">Strategy</div>
              <h3>Trading Agent</h3>
              <p>Develops position strategies based on research findings. Creates entry/exit plans with detailed position architecture and expected outcomes.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon agent-label">Risk</div>
              <h3>Risk Auditor</h3>
              <p>Independently verifies all proposed positions. Ensures compliance with fund parameters and risk limits before execution.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon agent-label">Compliance</div>
              <h3>Compliance Officer</h3>
              <p>Maintains regulatory adherence. Monitors fund operations against policy requirements and creates immutable decision audit trails.</p>
            </article>
          </div>
        </section>

        <section className="section cinematic-fade" id="features">
          <h2 className="section-title">Built for Institutional-Grade Management</h2>
          <div className="features-grid">
            <div className="feature-item dark-card">
              <h3>24/7 Market Surveillance</h3>
              <p>Our agents continuously monitor markets and execute trades. Response times unmatched by traditional hedge funds.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Transparent Decision Making</h3>
              <p>Every trade, every decision, every rationale is logged and documented. Investors understand exactly what we're doing and why.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Risk-Driven Architecture</h3>
              <p>Multi-layer risk verification before execution. Independent agents review position sizing, correlation, and scenario analysis.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Continuous Optimization</h3>
              <p>Our strategies adapt to market regimes while maintaining core investment thesis. Performance is continuously reviewed and refined.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Investor Dashboard</h3>
              <p>Real-time view of fund performance, positions, P&L, and decision history. Monitor your investment anytime, anywhere.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Production Ready</h3>
              <p>Runs on professional infrastructure. High availability and reliability. API integrations with major brokerages.</p>
            </div>
          </div>
        </section>

        <section className="section cinematic-fade" id="comparison">
          <h2 className="section-title">How Vektor Compares</h2>
          <div className="comparison-table">
            <div className="comparison-row dark-card">
              <div className="comparison-header">Capability</div>
              <div className="comparison-cell">Traditional Hedge Fund</div>
              <div className="comparison-cell">Algorithmic Trading Bot</div>
              <div className="comparison-cell" style={{ borderColor: 'var(--accent)' }}>Vektor</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Decision Transparency</div>
              <div className="comparison-cell">Quarterly Letters</div>
              <div className="comparison-cell">Black Box</div>
              <div className="comparison-cell accent">Full Audit Trail</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Trading Frequency</div>
              <div className="comparison-cell">Manual</div>
              <div className="comparison-cell">High-Frequency</div>
              <div className="comparison-cell accent">Adaptive</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Risk Management</div>
              <div className="comparison-cell">Human Review</div>
              <div className="comparison-cell">Rule-Based</div>
              <div className="comparison-cell accent">Multi-Agent Verification</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Strategy Explainability</div>
              <div className="comparison-cell">Narrative</div>
              <div className="comparison-cell">None</div>
              <div className="comparison-cell accent">Autonomous Reasoning</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Investor Access</div>
              <div className="comparison-cell">Annual Reports</div>
              <div className="comparison-cell">API Only</div>
              <div className="comparison-cell accent">Real-Time Dashboard</div>
            </div>
          </div>
        </section>

        <section className="section cinematic-fade" id="faq">
          <h2 className="section-title">Frequently Asked Questions</h2>
          <div className="faq-grid">
            <details className="dark-card faq-item">
              <summary><strong>How does Vektor invest my capital?</strong></summary>
              <p>Vektor employs our proprietary multi-agent AI system to identify, analyze, and execute trades. Your capital is invested according to our fund strategy while maintaining strict risk controls.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>What is the minimum investment?</strong></summary>
              <p>Check our Admin Console for current minimums. Paper trading is free for all users to understand our process before committing capital.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>Can I withdraw my investment?</strong></summary>
              <p>Yes. Withdrawals follow standard hedge fund practices with specified windows. Check our documentation for details.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>How are fees structured?</strong></summary>
              <p>Vektor follows a standard hedge fund model: management fee on AUM and performance fee on gains. See Admin Console for details.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>Can I customize the fund strategy?</strong></summary>
              <p>Vektor runs as a unified fund strategy. You can set risk parameters and constraints within the framework in your investor dashboard.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>How is Vektor regulated?</strong></summary>
              <p>Vektor operates as a registered investment fund with appropriate regulatory oversight. See our documentation for regulatory details.</p>
            </details>
          </div>
        </section>

        <section className="section cinematic-fade" id="cta-final">
          <div className="dark-card" style={{ textAlign: "center", padding: "80px 40px" }}>
             <h2 style={{ marginBottom: "16px", fontSize: "clamp(28px, 5vw, 48px)" }}>Ready to Experience AI-Driven Investing?</h2>
             <p style={{ margin: "0 auto 40px", maxWidth: "700px", color: "var(--muted)", fontSize: "18px" }}>Start with paper trading to see how Vektor works. Progress to live trading when you're confident. Always transparent, always in control.</p>
             <div className="hero-actions" style={{ justifyContent: 'center', gap: "16px" }}>
                <a className="btn primary" href={productUrl}>Launch Admin Console</a>
                <Link className="btn ghost" href="/how-it-works">View Full Architecture</Link>
                <Link className="btn ghost" href="/blog">Read Latest Research</Link>
             </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Vektor Fund OS • Smart, Safe, Explainable</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <Link href="/blog">Blog</Link>
                 <a href={productUrl}>PnL</a>
                 <Link href="/how-it-works">Tech Specs</Link>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}
