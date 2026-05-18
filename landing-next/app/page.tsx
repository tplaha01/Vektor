import { Metadata } from 'next';
import { Hero3DScene } from '@/components/hero-3d-scene';
import { FeatureCard } from '@/components/feature-card';
import styles from '@/styles/home.module.css';

const baseUrl = 'https://vektor-landing.vercel.app';

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: 'Vektor | AI-Native Hedge Fund Operating System',
  description: 'Enterprise-grade capital management platform with transparent risk controls, paper-first workflows, and AI-native decision infrastructure.',
  keywords: [
    'hedge fund',
    'AI trading',
    'capital management',
    'risk management',
    'trading platform',
    'fund operations',
  ],
  authors: [{ name: 'Vektor' }],
  creator: 'Vektor',
  publisher: 'Vektor',
  formatDetection: { telephone: false },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: baseUrl,
    title: 'Vektor | AI-Native Hedge Fund Operating System',
    description: 'Enterprise capital management platform with transparent risk controls and AI-native workflows.',
    siteName: 'Vektor',
    images: [
      {
        url: `${baseUrl}/og-image.png`,
        width: 1200,
        height: 630,
        alt: 'Vektor - AI Hedge Fund OS',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Vektor | AI-Native Hedge Fund Operating System',
    description: 'Enterprise capital management with transparent risk controls.',
    creator: '@VektorAI',
    images: [`${baseUrl}/og-image.png`],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
    nocache: false,
  },
  verification: {
    google: 'YOUR_GOOGLE_SITE_VERIFICATION_CODE',
  },
  alternates: {
    canonical: baseUrl,
  },
};

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: 'Vektor',
            url: baseUrl,
            logo: `${baseUrl}/logo.png`,
            description: 'AI-native hedge fund operating system with transparent risk controls.',
            sameAs: [
              'https://twitter.com/VektorAI',
            ],
            contactPoint: {
              '@type': 'ContactPoint',
              contactType: 'Sales',
              email: 'contact@vektor.ai',
            },
          }),
        }}
      />

      <main className={styles.main}>
        <header className={styles.header}>
          <div className={styles.container}>
            <div className={styles.logo}>
              <h1>Vektor</h1>
              <span className={styles.tagline}>AI-Native Hedge Fund OS</span>
            </div>
            <nav className={styles.nav}>
              <a href="#features">Features</a>
              <a href="#principles">Principles</a>
              <a href="#cta">Get Started</a>
            </nav>
          </div>
        </header>

        <section className={styles.hero}>
          <div className={styles.container}>
            <div className={styles.heroContent}>
              <h2 className={styles.heroTitle}>
                Capital Management That Stays Legible Under Pressure
              </h2>
              <p className={styles.heroDescription}>
                Vektor is a paper-first operating stack for research, thesis generation, risk review, and execution oversight. 
                Designed to feel closer to an institutional control room than a black-box trading bot.
              </p>
              <div className={styles.heroCta}>
                <button className={styles.btnPrimary}>View Live Fund Performance</button>
                <button className={styles.btnSecondary}>Explore the Operating Model</button>
              </div>
            </div>
            <div className={styles.heroVisual}>
              <Hero3DScene />
            </div>
          </div>
        </section>

        <section id="features" className={styles.features}>
          <div className={styles.container}>
            <h2 className={styles.sectionTitle}>Why It Feels Different</h2>
            <p className={styles.sectionDescription}>
              Built around trust, signal quality, and operational clarity.
            </p>
            <div className={styles.featureGrid}>
              <FeatureCard
                title="Explainable by Default"
                description="Every trade carries its rationale, supporting evidence, and approval trail. Investor communication is built into the workflow."
                icon="📋"
              />
              <FeatureCard
                title="Risk Owns the Tempo"
                description="Vektor optimizes for disciplined pace rather than maximum trade count. The system slows down before it lets uncertainty compound."
                icon="⚖️"
              />
              <FeatureCard
                title="Built for Operators"
                description="Research, allocation, overrides, and post-trade review live in one operating surface so the system feels governable under pressure."
                icon="🎛️"
              />
              <FeatureCard
                title="Paper-First Execution"
                description="Every strategy proves itself in simulation before real capital is allowed to touch the market."
                icon="📊"
              />
            </div>
          </div>
        </section>

        <section id="principles" className={styles.principles}>
          <div className={styles.container}>
            <h2 className={styles.sectionTitle}>The Agent Bench</h2>
            <p className={styles.sectionDescription}>
              Each role has one job and one point of view.
            </p>
            <div className={styles.principleGrid}>
              <div className={styles.principleCard}>
                <h3>Research Agent</h3>
                <p>Collects market context and turns noisy information flow into ranked opportunities with supporting receipts.</p>
              </div>
              <div className={styles.principleCard}>
                <h3>Fund Manager</h3>
                <p>Frames the trade thesis, capital plan, and expected path before any execution route is considered.</p>
              </div>
              <div className={styles.principleCard}>
                <h3>Risk Auditor</h3>
                <p>Runs independent checks on sizing, liquidity, concentration, and stress scenarios with veto power.</p>
              </div>
              <div className={styles.principleCard}>
                <h3>Compliance Memory</h3>
                <p>Logs the full decision chain so monitoring, review, and investor reporting stay consistent after the trade.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="cta" className={styles.cta}>
          <div className={styles.container}>
            <h2 className={styles.ctaTitle}>Ready to Transform Your Operations?</h2>
            <p className={styles.ctaDescription}>
              Join leading hedge funds using Vektor for transparent, disciplined capital management.
            </p>
            <button className={styles.btnPrimary + ' ' + styles.ctaBtn}>
              Start Your Free Trial
            </button>
          </div>
        </section>

        <footer className={styles.footer}>
          <div className={styles.container}>
            <p>&copy; 2026 Vektor. All rights reserved.</p>
            <div className={styles.footerLinks}>
              <a href="#">Privacy Policy</a>
              <a href="#">Terms of Service</a>
              <a href="#">Contact</a>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}