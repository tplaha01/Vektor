import Link from "next/link";
import { siteConfig } from "@/lib/site";

export default function Footer() {
  return (
    <footer className="border-t border-border/70 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            {siteConfig.shortName}
          </p>
          <p className="text-sm text-muted-foreground">
            Research, market briefs, and operating notes from the same stack that powers
            Vektor&apos;s paper-first trading workflow.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <Link href="/">Research</Link>
          <Link href="/?tag=Market+Briefs">Market Briefs</Link>
          <a href={siteConfig.links.landing}>About Vektor</a>
          <a href={siteConfig.links.product}>Live PnL</a>
          <a href={`${siteConfig.links.product}/admin`}>Admin Console</a>
        </div>
      </div>
    </footer>
  );
}
