import Link from "next/link";
import { siteConfig } from "@/lib/site";

const siteLinks = [
  { href: siteConfig.links.landing, label: "Landing" },
  { href: siteConfig.links.blog, label: "Blog" },
  { href: siteConfig.links.research, label: "Research" },
  { href: siteConfig.links.livePnl, label: "Live PnL" },
  { href: siteConfig.links.admin, label: "Admin" },
];

export default function Footer() {
  return (
    <footer className="border-t border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl space-y-2">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            {siteConfig.shortName}
          </p>
          <p className="font-mono text-sm text-muted-foreground">
            Academic papers, signal reports, and operating notes from the same
            stack that powers Vektor&apos;s paper-first trading workflow.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-sm text-muted-foreground">
          <Link href="/">Research Index</Link>
          <Link href="/signals">Signal Reports</Link>
          {siteLinks.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}
