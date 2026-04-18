import { Metadata } from "next";
import { siteConfig } from "@/lib/site";

export const metadataKeywords = [
    "Blog",
    "Trading",
    "Viktor Trading Blog",
    "Viktor Blog Template",
    "AI Trading",
    "Multi-Agent Systems",
    "Algorithmic Trading",
    "Next.js Blog",
    "React Blog",
    "Financial Technology",
    "Trading Strategies",
    "MDX Blog",
    "Modern Blog Template",
]

export const metadata: Metadata = {
    title: siteConfig.name,
    description: siteConfig.description,
    keywords: metadataKeywords,
    authors: [
        {
            name: "MagicUI Team",
            url: "https://magicui.design",
        },
    ],
    creator: "MagicUI",
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
        creator: "@magicui_design",
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