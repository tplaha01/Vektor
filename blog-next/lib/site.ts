export const siteConfig = {
  name: "Vektor Research",
  shortName: "Vektor",
  url: "https://vektor-trading-blog.vercel.app",
  description:
    "Market briefs, research notes, and operating context from Vektor's AI-native trading stack.",
  links: {
    landing:
      process.env.NEXT_PUBLIC_MARKETING_SITE_URL || "http://localhost:3000",
    product:
      process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000",
  },
};

export type SiteConfig = typeof siteConfig;
