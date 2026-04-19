"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ThemeSwitcher from "../ThemeSwitcher";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

// Hard-coded blog posts for client-side rendering
const blogPosts = [
  {
    slug: "intro-to-vektor",
    title: "Introduction to Vektor - AI-Native Hedge Fund OS",
    description: "Learn how Vektor revolutionizes fund management with transparent, AI-driven decision making and complete auditability.",
    date: "2026-04-15",
    tags: ["Getting Started", "AI", "Transparency"],
    featured: true,
    readTime: 8,
    author: "Vektor Team",
  },
  {
    slug: "multi-agent-trading",
    title: "How Multi-Agent Trading Works",
    description: "Understanding how independent specialized agents collaborate to make trading decisions with no single point of failure.",
    date: "2026-04-12",
    tags: ["Technical", "Architecture", "Agents"],
    featured: true,
    readTime: 6,
    author: "Vektor Team",
  },
  {
    slug: "paper-trading-explained",
    title: "Why We Start with Paper Trading",
    description: "The safety-first approach - learn and validate strategies with fake money before risking capital.",
    date: "2026-04-08",
    tags: ["Best Practices", "Safety", "Paper Trading"],
    featured: false,
    readTime: 5,
    author: "Vektor Team",
  },
  {
    slug: "risk-management-deep-dive",
    title: "Risk Management: Our Multi-Layer Approach",
    description: "How Vektor protects your capital through automated and manual risk controls at every layer.",
    date: "2026-04-01",
    tags: ["Technical", "Risk Management", "Safety"],
    featured: false,
    readTime: 7,
    author: "Vektor Team",
  },
];

export default function BlogPage() {
  const [mounted, setMounted] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);

  useEffect(() => {
    setMounted(true);

    // Intersection observer for animations
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

  if (!mounted) return null;

  const allTags = ["All", ...new Set(blogPosts.flatMap(p => p.tags || []))];
  const filteredPosts = selectedCategory && selectedCategory !== "All"
    ? blogPosts.filter(p => p.tags?.includes(selectedCategory))
    : blogPosts;

  const sortedPosts = [...filteredPosts].sort((a, b) => 
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: 32 }} />
            <span>Vektor <em>Blog</em></span>
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
          <h1 style={{ fontSize: 'clamp(40px, 7vw, 64px)', marginBottom: '24px', letterSpacing: '-0.03em' }}>Vektor Research & Insights</h1>
          <p style={{ color: 'var(--muted)', fontSize: 'clamp(18px, 2.5vw, 22px)', maxWidth: '800px', marginBottom: '60px', lineHeight: '1.6' }}>
            Deep dives into AI-driven trading, fund management, risk assessment, and how Vektor is reshaping the future of investing.
          </p>
        </div>

        <div style={{ marginBottom: '60px', display: 'flex', gap: '12px', flexWrap: 'wrap' }} className="cinematic-fade">
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setSelectedCategory(tag === "All" ? null : tag)}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: `1px solid ${selectedCategory === (tag === "All" ? null : tag) || (!selectedCategory && tag === "All") ? 'var(--accent)' : 'var(--line)'}`,
                background: selectedCategory === (tag === "All" ? null : tag) || (!selectedCategory && tag === "All") ? 'var(--surface)' : 'transparent',
                color: selectedCategory === (tag === "All" ? null : tag) || (!selectedCategory && tag === "All") ? 'var(--text)' : 'var(--muted)',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                transition: 'all 0.2s ease'
              }}
            >
              {tag}
            </button>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
          {sortedPosts.map((post) => (
            <article key={post.slug} className="dark-card cinematic-fade" style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '12px', color: 'var(--accent)', textTransform: 'uppercase', fontWeight: '600', letterSpacing: '0.1em' }}>
                  {post.tags?.[0] || 'Blog'}
                </span>
              </div>
              <h3 style={{ margin: '0 0 12px', fontSize: '20px', fontWeight: '500', color: 'var(--text)' }}>
                {post.title}
              </h3>
              <p style={{ margin: '0 0 16px', color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6', flex: 1 }}>
                {post.description}
              </p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {post.tags?.slice(0, 2).map((tag) => (
                  <span key={tag} style={{ fontSize: '12px', color: 'var(--muted)', background: 'var(--surface)', padding: '4px 8px', borderRadius: '4px' }}>
                    {tag}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--muted)', fontSize: '13px', borderTop: '1px solid var(--line)', paddingTop: '16px', marginTop: 'auto' }}>
                <span>{post.author} • {post.readTime} min</span>
                <span>{new Date(post.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              </div>
              <Link href={`/blog/${post.slug}`} className="btn ghost" style={{ marginTop: '16px', width: '100%', textAlign: 'center' }}>
                Read Article
              </Link>
            </article>
          ))}
        </div>

        {sortedPosts.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--muted)' }}>
            <p>No articles found in this category.</p>
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Vektor Fund OS • Research & Insights</span>
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
