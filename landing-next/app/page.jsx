"use client";

import { useEffect } from "react";
import Link from "next/link";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";
const blogUrl = "http://localhost:3001";

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
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand">Viktor <em>Fund OS</em></a>
          <nav className="hero-actions">
            <Link className="btn ghost" href="/how-it-works">How It Works</Link>
            <a className="btn ghost" href={blogUrl}>Blog</a>
            <a className="btn ghost" href={productUrl}>Live PnL</a>
            <a className="btn primary" href={`${productUrl}/admin`}>Admin Console</a>
          </nav>
        </div>
      </header>

      <main className="container overflow-hidden">
        <section className="hero cinematic-fade">
          <p className="eyebrow">The Future of Investing</p>
          <h1>A smart, transparent trading assistant you can actually understand.</h1>
          <p>
            Think of Viktor like a team of world-class specialists working together in one room. One reads the news,
            one analyzes the market, one checks the risks, and one executes the trade. Every decision is clearly explained, 
            so you never have to guess why a trade was made.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href={productUrl}>View Public PnL</a>
            <Link className="btn ghost" href="/how-it-works">See How It Works</Link>
            <a className="btn ghost" href={blogUrl}>Read Our Research</a>
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
              <li><strong>Practice Mode First:</strong> Viktor practices with fake money by default until you are perfectly comfortable.</li>
              <li><strong>Automatic Brakes:</strong> If the market gets too crazy, Viktor automatically pauses to keep your investments safe.</li>
              <li><strong>You Are the Boss:</strong> You can pause, review, or stop any action with the click of a button.</li>
            </ul>
          </article>
          <article className="dark-card">
            <h2>No Black Boxes</h2>
            <ul>
              <li><strong>Public Scoreboard:</strong> See exactly how well Viktor is doing on our Public PnL page.</li>
              <li><strong>Full Access:</strong> The Admin Console lets you look under the hood whenever you want.</li>
              <li><strong>Plain English:</strong> We explain our strategies in our Blog, not in complicated math equations.</li>
            </ul>
          </article>
        </section>

        <section className="section cinematic-fade">
          <div className="dark-card" style={{ textAlign: "center" }}>
             <h2 style={{ marginBottom: "16px" }}>Ready to see it in action?</h2>
             <p style={{ margin: "0 auto 32px", maxWidth: "600px" }}>Explore the live Public PnL or dive into our detailed technical walkthrough.</p>
             <div className="hero-actions" style={{ justifyContent: 'center' }}>
                <a className="btn primary" href={productUrl}>Open Live PnL</a>
                <Link className="btn ghost" href="/how-it-works">Technical Walkthrough</Link>
             </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Viktor Fund OS • Smart, Safe, Explainable</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <a href={blogUrl}>Blog</a>
                 <a href={productUrl}>PnL</a>
                 <Link href="/how-it-works">Tech Specs</Link>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}
