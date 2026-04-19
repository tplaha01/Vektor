"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ThemeSwitcher from "../ThemeSwitcher";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

// Blog posts data
const blogPosts = [
  {
    id: 1,
    slug: "intro-to-viktor",
    title: "Introduction to Viktor: AI-Native Hedge Fund OS",
    excerpt: "Learn how Viktor revolutionizes fund management with transparent, AI-driven decision making.",
    date: "2026-04-15",
    author: "Viktor Team",
    readTime: "8 min",
    category: "Getting Started",
    tags: ["AI", "Trading", "Fund Management"],
    content: `
      Viktor is a next-generation hedge fund operating system built on principles of transparency and explainability.
      
      ## The Problem We Solve
      Traditional hedge funds operate as black boxes. You submit capital, wait for quarterly reports, and hope for the best.
      Robo-advisors execute automated strategies with no explanation of why trades were made.
      
      ## The Viktor Solution
      We combine the intelligence of AI with the accountability of human oversight. Every trade is:
      - Explained in plain English
      - Backed by real data and sources
      - Subject to independent risk checks
      - Recorded in an immutable audit log
      
      ## Key Features
      - **Multi-Agent Architecture**: Specialized agents for research, trading, risk assessment, and compliance
      - **Paper Trading First**: Start with simulated execution to learn and validate strategies
      - **Real-Time Monitoring**: Track performance on our public PnL page
      - **Complete Override**: Pause or reject any trade with one click
      - **Cryptographic Audit Trail**: Every decision is signed and verifiable
      
      ## Getting Started
      Head to the admin console to set up your first trading strategy. Start in paper mode and progress to live trading when you're ready.
    `
  },
  {
    id: 2,
    slug: "multi-agent-trading",
    title: "How Multi-Agent Trading Works",
    excerpt: "Understanding how independent specialized agents collaborate to make trading decisions.",
    date: "2026-04-12",
    author: "Viktor Team",
    readTime: "6 min",
    category: "Technical",
    tags: ["Architecture", "Agents", "Trading"],
    content: `
      ## The Multi-Agent Approach
      Viktor doesn't use a single monolithic AI. Instead, we orchestrate multiple specialized agents:
      
      ### 1. Research Director
      Scans thousands of data sources daily:
      - Financial news and market analysis
      - Company earnings reports
      - Macroeconomic indicators
      - Technical price patterns
      
      Outputs: Structured insights and signals
      
      ### 2. Trading Director
      Takes research insights and creates trading theses:
      - Analyzes signals for opportunity
      - Determines position sizing
      - Sets risk parameters
      - Prepares execution orders
      
      Outputs: Trade proposals with clear rationale
      
      ### 3. Risk Auditor
      Independent verification layer:
      - Checks portfolio concentration
      - Validates position sizing
      - Monitors volatility limits
      - Ensures compliance with fund rules
      
      Outputs: Approval or rejection (no override)
      
      ### 4. Compliance Officer
      Maintains regulatory requirements:
      - Monitors fund policies
      - Tracks regulatory changes
      - Maintains audit trail
      - Generates reports
      
      ## Why This Works
      Multiple independent agents reduce systemic risk. If the Trading Director makes a questionable call, the Risk Auditor catches it.
      No single agent can make a trade that violates risk constraints.
    `
  },
  {
    id: 3,
    slug: "paper-trading-explained",
    title: "Why We Start with Paper Trading",
    excerpt: "The safety-first approach: learn and validate strategies with fake money before risking capital.",
    date: "2026-04-08",
    author: "Viktor Team",
    readTime: "5 min",
    category: "Best Practices",
    tags: ["Paper Trading", "Safety", "Learning"],
    content: `
      ## The Paper Trading Philosophy
      ALL trades in Viktor start in paper (simulated) mode. This is not optional—it's our default.
      
      ## Why This Matters
      
      **For You:**
      - Learn how Viktor makes decisions without risk
      - Validate that the strategy matches your goals
      - Understand the system before committing capital
      - Build confidence in the process
      
      **For Us:**
      - Prove the strategy works before taking capital
      - Identify edge cases and failure modes
      - Tune parameters without consequences
      - Build trust through transparency
      
      ## The Workflow
      1. Configure your strategy in the admin console
      2. Viktor begins trading in paper mode
      3. Watch trades execute with simulated capital
      4. Review decision explanations after each trade
      5. When satisfied, explicitly enable live trading
      6. First real trade executes only after confirmation
      
      ## Transitioning to Live Trading
      You control when the system goes live. We recommend:
      - Watching paper mode for at least 30 days
      - Understanding at least 10 trades and their outcomes
      - Reviewing the audit log thoroughly
      - Starting with small live position size
      - Gradually increasing over time
    `
  },
  {
    id: 4,
    slug: "risk-management-deep-dive",
    title: "Risk Management: Our Multi-Layer Approach",
    excerpt: "How Viktor protects your capital through automated and manual risk controls.",
    date: "2026-04-01",
    author: "Viktor Team",
    readTime: "7 min",
    category: "Technical",
    tags: ["Risk Management", "Safety", "Controls"],
    content: `
      ## Layered Risk Architecture
      Viktor implements risk controls at multiple layers:
      
      ### Layer 1: Proposal Constraints
      Before the Trading Director can even propose a trade:
      - Position size limits (% of portfolio)
      - Single-stock concentration limits
      - Sector allocation limits
      - Leverage caps
      
      ### Layer 2: Risk Auditor Gate
      Every trade must pass independent checks:
      - Volatility assessment (reject if market is stressed)
      - Correlation analysis (detect concentration)
      - Stress testing (model worst-case scenarios)
      - Regulatory compliance verification
      
      ### Layer 3: Circuit Breakers
      Automatic trading halts if:
      - Portfolio drops more than 5% in a day
      - Volatility spikes beyond thresholds
      - Liquidity dries up in key markets
      - Regulatory violations detected
      
      ### Layer 4: Manual Intervention
      You can override at any time:
      - Pause all trading
      - Reject specific trades
      - Adjust risk parameters
      - Enable/disable live mode
      
      ## Real Example
      Market crashes 8% overnight (rare event). Circuit breaker triggers automatically:
      ✓ All pending trades rejected
      ✓ Portfolio goes to defensive allocation
      ✓ Notification sent to you
      ✓ Manual review before trading resumes
      
      This prevents panic selling in market stress.
    `
  }
];

export default function BlogPage() {
  const [mounted, setMounted] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);

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

  const categories = ["All", ...new Set(blogPosts.map(p => p.category))];
  const filteredPosts = selectedCategory && selectedCategory !== "All" 
    ? blogPosts.filter(p => p.category === selectedCategory)
    : blogPosts;

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand">Viktor <em>Blog</em></a>
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
          <h1 style={{ fontSize: 'clamp(40px, 7vw, 64px)', marginBottom: '24px', letterSpacing: '-0.03em' }}>Viktor Research & Insights</h1>
          <p style={{ color: 'var(--muted)', fontSize: 'clamp(18px, 2.5vw, 22px)', maxWidth: '800px', marginBottom: '60px', lineHeight: '1.6' }}>
            Deep dives into AI-driven trading, fund management, risk assessment, and how Viktor is reshaping the future of investing.
          </p>
        </div>

        <div style={{ marginBottom: '60px', display: 'flex', gap: '12px', flexWrap: 'wrap' }} className="cinematic-fade">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat === "All" ? null : cat)}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: `1px solid ${selectedCategory === (cat === "All" ? null : cat) || (!selectedCategory && cat === "All") ? 'var(--accent)' : 'var(--line)'}`,
                background: selectedCategory === (cat === "All" ? null : cat) || (!selectedCategory && cat === "All") ? 'var(--surface)' : 'transparent',
                color: selectedCategory === (cat === "All" ? null : cat) || (!selectedCategory && cat === "All") ? 'var(--text)' : 'var(--muted)',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                transition: 'all 0.2s ease'
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
          {filteredPosts.map((post) => (
            <article key={post.id} className="dark-card cinematic-fade" style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '12px', color: 'var(--accent)', textTransform: 'uppercase', fontWeight: '600', letterSpacing: '0.1em' }}>
                  {post.category}
                </span>
              </div>
              <h3 style={{ margin: '0 0 12px', fontSize: '20px', fontWeight: '500', color: 'var(--text)' }}>
                {post.title}
              </h3>
              <p style={{ margin: '0 0 16px', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6', flex: 1 }}>
                {post.excerpt}
              </p>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {post.tags.map((tag) => (
                  <span key={tag} style={{ fontSize: '12px', color: 'var(--muted)', background: 'var(--surface)', padding: '4px 8px', borderRadius: '4px' }}>
                    {tag}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--muted)', fontSize: '13px', borderTop: '1px solid var(--line)', paddingTop: '16px', marginTop: 'auto' }}>
                <span>{post.author} • {post.readTime}</span>
                <span>{new Date(post.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              </div>
              <Link href={`/blog/${post.slug}`} className="btn ghost" style={{ marginTop: '16px', width: '100%', textAlign: 'center' }}>
                Read Article
              </Link>
            </article>
          ))}
        </div>
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Viktor Fund OS • Research & Insights</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <Link href="/">Home</Link>
                 <a href={productUrl}>PnL</a>
                 <Link href="/how-it-works">How It Works</Link>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}
