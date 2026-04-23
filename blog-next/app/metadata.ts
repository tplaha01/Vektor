import { Metadata } from "next";
import { siteConfig } from "@/lib/site";

export const metadataKeywords = [
  "Vektor Research",
  "Trading",
  "Market Briefs",
  "AI Trading",
  "Multi-Agent Systems",
  "Algorithmic Trading",
  "Financial Technology",
  "Trading Strategies",
  "Risk Management",
  "Research Notes",
];

export const metadata: Metadata = {
  title: siteConfig.name,
  description: siteConfig.description,
  keywords: metadataKeywords,
  authors: [
    {
      name: "Vektor",
      url: siteConfig.url,
    },
  ],
  creator: "Vektor",
  publisher: "Vektor",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteConfig.url,
    title: siteConfig.name,
    description: siteConfig.description,
    siteName: siteConfig.name,
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.name,
    description: siteConfig.description,
    creator: "@vektortrading",
    site: "@vektortrading",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};
