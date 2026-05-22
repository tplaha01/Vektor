import { Metadata } from "next";
import { Hero3DScene } from "@/components/hero-3d-scene";
import styles from "@/styles/home.module.css";

const baseUrl = "https://vektor-landing.vercel.app";
const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "https://vektor-trading.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: "Vektor | AI-Native Hedge Fund Operating System",
  description:
    "Paper-first capital management with transparent risk controls, decision lineage, and AI-native fund operations.",
  keywords: [
    "hedge fund",
    "AI trading",
    "capital management",
    "risk management",
    "trading platform",
    "fund operations",
  ],
  authors: [{ name: "Vektor" }],
  creator: "Vektor",
  publisher: "Vektor",
  formatDetection: { telephone: false },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: baseUrl,
    title: "Vektor | AI-Native Hedge Fund Operating System",
    description: "Paper-first fund operations with transparent risk controls and AI-native workflows.",
    siteName: "Vektor",
    images: [
      {
        url: `${baseUrl}/og-image.png`,
        width: 1200,
        height: 630,
        alt: "Vektor - AI Hedge Fund OS",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vektor | AI-Native Hedge Fund Operating System",
    description: "Paper-first capital management with transparent risk controls.",
    creator: "@VektorAI",
    images: [`${baseUrl}/og-image.png`],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
    nocache: false,
  },
  alternates: {
    canonical: baseUrl,
  },
};

const operatingLoop = [
  {
    step: "01",
    title: "Research intake",
    description: "Signals, transcripts, macro prints, and price action arrive as structured evidence.",
  },
  {
    step: "02",
    title: "Manager synthesis",
    description: "The fund manager converts raw context into a thesis with sizing and risk assumptions.",
  },
  {
    step: "03",
    title: "Risk gate",
    description: "Independent auditors challenge concentration, liquidity, volatility, and policy fit.",
  },
  {
    step: "04",
    title: "Paper-first execution",
    description: "Every decision remains observable in simulation before live capital is allowed.",
  },
];

const heroSignals = [
  { label: "Mode", value: "Paper first", detail: "Live capital stays gated" },
  { label: "Control", value: "Risk veto", detail: "Independent review before execution" },
  { label: "Memory", value: "Full lineage", detail: "Every thesis, override, and result retained" },
];

const consoleRows = [
  { label: "Research", value: "NVDA momentum thesis queued", status: "evidence mapped" },
  { label: "Risk", value: "Concentration check active", status: "limits enforced" },
  { label: "Execution", value: "Paper book only", status: "capital locked" },
];

const principles = [
  {
    title: "Explainable by default",
    description:
      "Every trade carries its rationale, supporting evidence, and approval trail so investor communication is built into the workflow.",
  },
  {
    title: "Risk owns the tempo",
    description:
      "Vektor optimizes for disciplined pace rather than maximum trade count. The system slows down before uncertainty compounds.",
  },
  {
    title: "Built for operators",
    description:
      "Research, allocation, overrides, and post-trade review live in one operating surface so the system stays governable.",
  },
];

const agents = [
  {
    label: "Research",
    title: "Research agent",
    description: "Turns noisy market context into ranked opportunities with supporting receipts.",
  },
  {
    label: "Manager",
    title: "Fund manager",
    description: "Frames the trade thesis, capital plan, and expected path before execution is considered.",
  },
  {
    label: "Risk",
    title: "Risk auditor",
    description: "Runs independent checks on sizing, liquidity, concentration, and stress scenarios.",
  },
  {
    label: "Control",
    title: "Compliance memory",
    description: "Records the full decision chain for monitoring, review, and investor reporting.",
  },
];

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Organization",
            name: "Vektor",
            url: baseUrl,
            logo: `${baseUrl}/logo.png`,
            description: "AI-native hedge fund operating system with transparent risk controls.",
            sameAs: ["https://twitter.com/VektorAI"],
          }),
        }}
      />

      <main className={styles.main}>
        <header className={styles.header}>
          <div className={styles.container}>
            <a className={styles.logo} href="/" aria-label="Vektor home">
              <span className={styles.logoMark}>V</span>
              <span>
                <strong>Vektor</strong>
                <em>AI-native fund OS</em>
              </span>
            </a>
            <nav className={styles.nav} aria-label="Primary">
              <a href="#features">Principles</a>
              <a href="#agents">Agent Bench</a>
              <a href={productUrl}>Live PnL</a>
            </nav>
          </div>
        </header>

        <section className={styles.hero}>
          <div className={styles.container}>
            <div className={styles.heroGrid}>
              <div className={styles.heroContent}>
                <p className={styles.eyebrow}>AI-native hedge fund operating system</p>
                <h1 className={styles.heroTitle}>Vektor</h1>
                <p className={styles.heroSubtitle}>Capital management that stays legible under pressure.</p>
                <p className={styles.heroDescription}>
                  A paper-first operating stack for research, thesis generation, risk review,
                  and execution oversight. Built to read like an institutional control room,
                  not a black-box trading bot.
                </p>
                <div className={styles.heroCta}>
                  <a className={styles.btnPrimary} href={productUrl}>
                    View live fund performance
                  </a>
                  <a className={styles.btnSecondary} href="#features">
                    Explore the operating model
                  </a>
                </div>
                <div className={styles.heroSignals} aria-label="Vektor operating guarantees">
                  {heroSignals.map((signal) => (
                    <div key={signal.label} className={styles.signalCard}>
                      <span>{signal.label}</span>
                      <strong>{signal.value}</strong>
                      <p>{signal.detail}</p>
                    </div>
                  ))}
                </div>
              </div>

              <aside className={styles.visualColumn} aria-label="Vektor capital topology preview">
                <div className={styles.heroVisual}>
                  <Hero3DScene />
                </div>
                <div className={styles.consolePanel}>
                  <div className={styles.panelTopline}>
                    <span>Operating console</span>
                    <strong>Controlled</strong>
                  </div>
                  <h2>A fund workflow with explicit checkpoints.</h2>
                  <p>
                    The topology maps signal flow, risk feedback, and paper-mode routing before
                    any live order can activate.
                  </p>
                  <div className={styles.consoleRows}>
                    {consoleRows.map((row) => (
                      <div key={row.label} className={styles.consoleRow}>
                        <span>{row.label}</span>
                        <strong>{row.value}</strong>
                        <em>{row.status}</em>
                      </div>
                    ))}
                  </div>
                </div>
              </aside>
            </div>

            <div className={styles.loopGrid}>
              {operatingLoop.map((item) => (
                <article key={item.title} className={styles.loopCard}>
                  <span>{item.step}</span>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className={styles.section}>
          <div className={styles.container}>
            <div className={styles.sectionHead}>
              <p className={styles.eyebrow}>Why it feels different</p>
              <h2>The product is built around trust, not just signal throughput.</h2>
              <p>
                The experience should help an allocator understand what the system is doing,
                why it is doing it, and when it should slow down.
              </p>
            </div>
            <div className={styles.cardGrid}>
              {principles.map((item) => (
                <article key={item.title} className={styles.card}>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="agents" className={styles.section}>
          <div className={styles.container}>
            <div className={styles.sectionHead}>
              <p className={styles.eyebrow}>Agent bench</p>
              <h2>Each role has one job and one point of view.</h2>
              <p>
                Research finds. The manager frames. Risk challenges. Control records.
                Narrow responsibilities keep the system readable.
              </p>
            </div>
            <div className={styles.agentGrid}>
              {agents.map((agent) => (
                <article key={agent.title} className={styles.card}>
                  <span>{agent.label}</span>
                  <h3>{agent.title}</h3>
                  <p>{agent.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.cta}>
          <div className={styles.container}>
            <div className={styles.ctaShell}>
              <p className={styles.eyebrow}>Start here</p>
              <h2>Use paper mode to understand the system before you trust it.</h2>
              <p>
                Monitor the simulated book, review the decision logs, and only then allow
                live capital into the loop.
              </p>
              <div className={styles.heroCta}>
                <a className={styles.btnPrimary} href={`${productUrl}/admin`}>
                  Open the admin console
                </a>
                <a className={styles.btnSecondary} href={productUrl}>
                  View live PnL
                </a>
              </div>
            </div>
          </div>
        </section>

        <footer className={styles.footer}>
          <div className={styles.container}>
            <p>Vektor. Paper-first execution with traceable decisions and explicit risk gates.</p>
            <div className={styles.footerLinks}>
              <a href="#features">Principles</a>
              <a href="#agents">Agent Bench</a>
              <a href={productUrl}>Live PnL</a>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
