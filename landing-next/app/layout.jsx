import "./globals.css";
import { ThemeProvider } from "./ThemeProvider";
import { baseUrl } from "../lib/site";

export const metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "Vektor | Deterministic ML Trading Operations Platform",
    template: "%s | Vektor",
  },
  description:
    "Vektor is a deterministic ML trading operations platform for paper-first portfolio automation, market data ingest, risk gates, and decision auditability.",
  applicationName: "Vektor",
  keywords: [
    "deterministic trading platform",
    "ML trading operations",
    "paper trading platform",
    "portfolio risk controls",
    "quant data pipeline",
    "trade decision audit trail",
  ],
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/VektorLogo.png?v=20260422b",
    apple: "/VektorLogo.png?v=20260422b",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: "website",
    title: "Vektor | Deterministic ML Trading Operations Platform",
    description:
      "Paper-first trading operations with market data lineage, deterministic ML decisioning, risk controls, and auditable execution.",
    url: "/",
    siteName: "Vektor",
  },
  twitter: {
    card: "summary_large_image",
    title: "Vektor | Deterministic ML Trading Operations Platform",
    description:
      "A firm-grade operating layer for paper-traded ML portfolios, data ingest, risk gates, and decision auditability.",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
