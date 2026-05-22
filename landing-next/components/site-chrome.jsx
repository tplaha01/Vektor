"use client";

import Link from "next/link";
import ThemeSwitcher from "../app/ThemeSwitcher";
import { navItems, productUrl } from "../lib/site";

export function SiteHeader({ active = "home" }) {
  return (
    <header className="topbar">
      <div className="container topbar-inner">
        <Link href="/" className="brand" aria-label="Vektor home">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/VektorLogo.png?v=20260422b"
              alt=""
              className="brand-logo"
            />
            <span className="brand-copy">
              <span className="brand-title">Vektor</span>
              <span className="brand-subtitle">Fund operating system</span>
            </span>
        </Link>

        <div className="topbar-nav">
          <nav className="topbar-links" aria-label="Primary">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`topbar-link${active === item.key ? " is-active" : ""}`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="topbar-actions">
            <a className="btn ghost" href="/performance">
              Paper record
            </a>
            <a className="btn primary" href={`${productUrl}/admin`}>
              Open console
            </a>
            <span className="topbar-divider" aria-hidden="true" />
            <ThemeSwitcher />
          </div>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter({
  eyebrow = "Vektor",
  description = "Paper-first execution with traceable decisions, explicit risk gates, and investor-visible operations.",
}) {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <div className="footer-copy">
          <p className="footer-eyebrow">{eyebrow}</p>
          <p className="footer-description">{description}</p>
        </div>

        <div className="footer-links">
          <Link href="/">Overview</Link>
          <Link href="/platform">Platform</Link>
          <Link href="/operating-model">Operating Model</Link>
          <Link href="/data">Data</Link>
          <Link href="/risk">Risk</Link>
          <Link href="/performance">Performance</Link>
          <Link href="/blog">Research</Link>
          <a href={productUrl}>Live PnL</a>
          <a href={`${productUrl}/admin`}>Admin Console</a>
        </div>
      </div>
    </footer>
  );
}
