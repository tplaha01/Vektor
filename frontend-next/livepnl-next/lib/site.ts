export const siteConfig = {
  name: "Vektor Live PnL",
  shortName: "Vektor",
  url: process.env.NEXT_PUBLIC_LIVE_PNL_SITE_URL || "https://pnl.vektor.ai",
  description:
    "Public performance dashboard for Vektor's AI-native paper trading portfolio.",
  links: {
    landing: process.env.NEXT_PUBLIC_MARKETING_SITE_URL || "https://vektor.ai",
    blog: process.env.NEXT_PUBLIC_BLOG_SITE_URL || "https://blog.vektor.ai",
    research: process.env.NEXT_PUBLIC_RESEARCH_SITE_URL || "https://research.vektor.ai",
    livePnl: process.env.NEXT_PUBLIC_LIVE_PNL_SITE_URL || "https://pnl.vektor.ai",
    admin: process.env.NEXT_PUBLIC_ADMIN_SITE_URL || "https://admin.vektor.ai",
  },
};

export type SiteConfig = typeof siteConfig;
