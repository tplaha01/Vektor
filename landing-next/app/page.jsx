"use client";

import { useEffect } from "react";
import Link from "next/link";
import ThemeSwitcher from "./ThemeSwitcher";
import PlasmaBackground from "../components/plasma-background";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

export default function Page() {
  useEffect(() => {
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
      <PlasmaBackground />
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: "48px", width: "auto", objectFit: "contain" }} />
            <span>Vektor <em>Fund OS</em></span>
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
          <p className="eyebrow">The Future of Investing</p>
          <h1>A smart, transparent trading assistant you can actually understand.</h1>
          <p>
            Think of Vektor like a team of world-class specialists working together in one room. One reads the news,
            one analyzes the market, one checks the risks, and one executes the trade. Every decision is clearly explained, 
            so you never have to guess why a trade was made.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href={productUrl}>View Public PnL</a>
            <Link className="btn ghost" href="/how-it-works">See How It Works</Link>
            <Link className="btn ghost" href="/blog">Read Our Research</Link>
          </div>
          <div className="hero-stats">
            <span className="pill">Fully Traceable</span>
            <span className="pill">Human-Readable Decisions</span>
            <span className="pill">Safe & Controlled</span>
          </div>
        </section>

        <section className="grid cinematic-fade" id="how">
          <article className="dark-card">
            <h3>1. Read & Research</h3>
            <p>Our specialists read thousands of news articles, earnings reports, and market charts instantly. They find the most important information for you.</p>
          </article>
          <article className="dark-card">
            <h3>2. Make a Plan</h3>
            <p>The system creates a clear, easy-to-understand plan. It explains exactly what it wants to buy or sell, and points out the exact reasons why.</p>
          </article>
          <article className="dark-card">
            <h3>3. Check for Safety</h3>
            <p>Before doing anything, independent risk checkers review the plan. If it's too risky or breaks the rules, it's stopped immediately.</p>
          </article>
          <article className="dark-card">
            <h3>4. Act & Record</h3>
            <p>Once approved, the action is taken. Everything is written down permanently, so you can always go back and review the exact decision process.</p>
          </article>
        </section>

        <section className="section split cinematic-fade" id="safety">
          <article className="dark-card">
            <h2>Safety You Can Trust</h2>
            <ul>
              <li><strong>Practice Mode First:</strong> Vektor practices with fake money by default until you are perfectly comfortable.</li>
              <li><strong>Automatic Brakes:</strong> If the market gets too crazy, Vektor automatically pauses to keep your investments safe.</li>
              <li><strong>You Are the Boss:</strong> You can pause, review, or stop any action with the click of a button.</li>
            </ul>
          </article>
          <article className="dark-card">
            <h2>No Black Boxes</h2>
            <ul>
              <li><strong>Public Scoreboard:</strong> See exactly how well Vektor is doing on our Public PnL page.</li>
              <li><strong>Full Access:</strong> The Admin Console lets you look under the hood whenever you want.</li>
              <li><strong>Plain English:</strong> We explain our strategies in our Blog, not in complicated math equations.</li>
            </ul>
          </article>
        </section>

        <section className="section cinematic-fade" id="agents">
          <h2 className="section-title">Specialized Agents Working for You</h2>
          <div className="agents-grid">
            <article className="dark-card">
              <div className="agent-icon">📰</div>
              <h3>Research Director</h3>
              <p>Scans thousands of sources daily. Market news, earnings reports, macroeconomic data. Synthesizes into clear, actionable insights.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon">📊</div>
              <h3>Trading Director</h3>
              <p>Analyzes trends and patterns. Identifies opportunities that fit your strategy. Creates detailed trading plans with clear rationale.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon">🛡️</div>
              <h3>Risk Auditor</h3>
              <p>Independent verification layer. Checks every trade against your rules and risk limits. Never lets bad decisions slip through.</p>
            </article>
            <article className="dark-card">
              <div className="agent-icon">⚖️</div>
              <h3>Compliance Officer</h3>
              <p>Ensures regulatory requirements are met. Monitors fund policies. Maintains audit trail for every decision and trade.</p>
            </article>
          </div>
        </section>

        <section className="section cinematic-fade" id="features">
          <h2 className="section-title">Built for Modern Investing</h2>
          <div className="features-grid">
            <div className="feature-item dark-card">
              <h3>Real-Time Intelligence</h3>
              <p>AI agents process market data 24/7. Get insights faster than traditional research teams. Stay ahead of market moves.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Complete Transparency</h3>
              <p>Every decision is logged and explained. No black boxes. Understand exactly why Vektor made each trade. Full audit trail included.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Risk First Architecture</h3>
              <p>Multiple independent risk checks before any trade executes. Paper trading by default. Live capital only when you're ready.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Always Learning</h3>
              <p>Reviews past decisions to improve. Adapts to changing market conditions. Continuously optimizes strategy performance.</p>
            </div>
            <div className="feature-item dark-card">
              <h3>Your Control, Always</h3>
              <p>Pause trades anytime. Override decisions manually. Adjust strategies on the fly. You remain in complete control.</p>
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
              <div className="comparison-header">Feature</div>
              <div className="comparison-cell">Traditional Fund</div>
              <div className="comparison-cell">Automated Bots</div>
              <div className="comparison-cell" style={{ borderColor: 'var(--accent)' }}>Vektor</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Transparent Decisions</div>
              <div className="comparison-cell">❌</div>
              <div className="comparison-cell">❌</div>
              <div className="comparison-cell accent">✅</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">24/7 Monitoring</div>
              <div className="comparison-cell">❌</div>
              <div className="comparison-cell">✅</div>
              <div className="comparison-cell accent">✅</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Risk Management</div>
              <div className="comparison-cell">Manual</div>
              <div className="comparison-cell">Limited</div>
              <div className="comparison-cell accent">Autonomous</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Explainability</div>
              <div className="comparison-cell">Low</div>
              <div className="comparison-cell">None</div>
              <div className="comparison-cell accent">Full</div>
            </div>
            <div className="comparison-row">
              <div className="comparison-header">Access to Decisions</div>
              <div className="comparison-cell">Quarterly Reports</div>
              <div className="comparison-cell">Real-time API</div>
              <div className="comparison-cell accent">Admin Console</div>
            </div>
          </div>
        </section>

        <section className="section cinematic-fade" id="faq">
          <h2 className="section-title">Frequently Asked Questions</h2>
          <div className="faq-grid">
            <details className="dark-card faq-item">
              <summary><strong>Is Vektor suitable for beginners?</strong></summary>
              <p>Yes. Vektor starts in paper trading mode with detailed explanations of every decision. You can learn at your own pace before risking real capital.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>How much capital is required to start?</strong></summary>
              <p>You can start with paper trading for free. For live trading, check our Admin Console for minimum requirements and current offerings.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>What exchanges does Vektor support?</strong></summary>
              <p>Vektor integrates with major brokerages. See our Blog for current integrations or contact us via the Admin Console.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>Can I customize Vektor's strategy?</strong></summary>
              <p>Yes. You can adjust risk parameters, set custom constraints, and define your investment universe. Check the How It Works section for details.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>What if I disagree with a trade decision?</strong></summary>
              <p>You can pause or override any trade at any time. Every override is logged for analysis and learning.</p>
            </details>
            <details className="dark-card faq-item">
              <summary><strong>How is Vektor different from robo-advisors?</strong></summary>
              <p>Vektor uses multi-agent orchestration with transparent decision reasoning. We explain our logic, not just execute trades.</p>
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
