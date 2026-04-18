import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata = {
  metadataBase: new URL(siteUrl),
  title: "Vektor | AI-Native Hedge Fund OS",
  description:
    "Vektor is a paper-first AI-native hedge fund operating system with multi-agent orchestration, decision traceability, and sleeve-level capital allocation.",
  applicationName: "Vektor",
  openGraph: {
    type: "website",
    title: "Vektor | AI-Native Hedge Fund OS",
    description:
      "Build and operate an AI-native hedge fund stack with institutional controls and auditability.",
    url: "/",
    siteName: "Vektor",
  },
  twitter: {
    card: "summary_large_image",
    title: "Vektor | AI-Native Hedge Fund OS",
    description:
      "Paper-first multi-agent hedge fund operations with full decision lineage.",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
