export const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://vektor-landing.vercel.app";
export const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "https://vektor-trading.vercel.app";

export const navItems = [
  { href: "/", label: "Overview", key: "home" },
  { href: "/platform", label: "Platform", key: "platform" },
  { href: "/operating-model", label: "Operating Model", key: "operating" },
  { href: "/data", label: "Data", key: "data" },
  { href: "/risk", label: "Risk", key: "risk" },
  { href: "/performance", label: "Performance", key: "performance" },
  { href: "/blog", label: "Research", key: "blog" },
];

export const operatingFacts = [
  ["Current mode", "Deterministic ML + paper execution"],
  ["Execution venue", "Paper broker; live trading disabled by default"],
  ["Primary controls", "Risk gate, data-integrity guard, operator override"],
  ["Evidence layer", "Market stream, daily bars, news, fundamentals, feature vectors"],
  ["Audit surface", "Decision ledger, runtime controls, lineage, performance snapshots"],
];

export const operatingStages = [
  {
    step: "01",
    title: "Universe and evidence intake",
    description:
      "Market data, quotes, news, fundamentals, and prior portfolio state are normalized before a trade can exist.",
  },
  {
    step: "02",
    title: "Feature and signal construction",
    description:
      "Technical, fundamental, sentiment, and ML alpha features are composed into a deterministic decision frame.",
  },
  {
    step: "03",
    title: "Portfolio and risk gate",
    description:
      "Exposure, liquidity, concentration, market session, and drawdown controls decide whether a proposal can proceed.",
  },
  {
    step: "04",
    title: "Paper execution and ledger",
    description:
      "Approved orders route to the paper broker first, with every state transition written back for review.",
  },
];

export const platformPillars = [
  {
    title: "Data warehouse",
    label: "Ingest",
    description:
      "Raw provider payloads, normalized prices, quotes, bars, text events, fundamentals, quality events, snapshots, and feature vectors.",
  },
  {
    title: "Signal engine",
    label: "Model",
    description:
      "Hybrid scoring combines deterministic technical, fundamental, sentiment, and LightGBM alpha components when the model is ready.",
  },
  {
    title: "Risk and policy",
    label: "Control",
    description:
      "Pre-trade checks, budget policy, strict/paper runtime modes, and drawdown protection keep the workflow governable.",
  },
  {
    title: "Operator console",
    label: "Admin",
    description:
      "Status, paper positions, runtime controls, lineage, approvals, and recovery actions are visible in one work surface.",
  },
];

export const dataAssets = [
  ["Raw events", "Provider payloads and request context"],
  ["Market prices", "Latest trade and poll-derived prices"],
  ["Market quotes", "Bid/ask, spread, and NBBO snapshots"],
  ["Market bars", "Daily OHLCV windows for ML and trend features"],
  ["Text events", "News items with quality and sentiment metadata"],
  ["Fundamentals", "TTM ratios and company profile metrics"],
  ["Feature vectors", "Execution, alpha, and monitoring features"],
  ["Provider health", "Success, stale, failure, and freshness counters"],
];

export const riskControls = [
  "Paper-only execution as the default production posture",
  "Live trading disabled unless explicitly configured",
  "Data-integrity guard with deterministic recovery controls",
  "Pre-trade risk check before paper order placement",
  "Allocation policy with reserve cash and asset-class budgets",
  "Decision ledger and audit events for every approval or block",
];

export const performanceDisclosures = [
  "Performance shown in the product app is paper-mode performance, not an audited live fund return.",
  "Track record views are intended for system validation, operator review, and workflow QA.",
  "No page on this site should be read as an offer to buy securities or investment advice.",
];
