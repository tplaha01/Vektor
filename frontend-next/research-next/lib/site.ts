export const siteConfig = {
  name: "Vektor Research",
  shortName: "Vektor",
  url: process.env.NEXT_PUBLIC_RESEARCH_SITE_URL || "https://research.vektor.ai",
  description:
    "Academic papers, signal reports, and AI-generated market research from Vektor's AI-native trading stack.",
  links: {
    landing: process.env.NEXT_PUBLIC_MARKETING_SITE_URL || "https://vektor.ai",
    blog: process.env.NEXT_PUBLIC_BLOG_SITE_URL || "https://blog.vektor.ai",
    research: process.env.NEXT_PUBLIC_RESEARCH_SITE_URL || "https://research.vektor.ai",
    livePnl: process.env.NEXT_PUBLIC_LIVE_PNL_SITE_URL || "https://pnl.vektor.ai",
    admin: process.env.NEXT_PUBLIC_ADMIN_SITE_URL || "https://admin.vektor.ai",
  },
};

export type SiteConfig = typeof siteConfig;
