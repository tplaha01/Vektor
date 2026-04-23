/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/lib/site";

const navItems = [
  { href: "/", label: "All research" },
  { href: "/?tag=Market+Briefs", label: "Market briefs" },
  { href: "/?tag=Research+Notes", label: "Research notes" },
];

export function SiteNav() {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-border/70 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/65">
      <div className="mx-auto flex min-h-20 w-full max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-2xl border border-border bg-card/70 shadow-sm shadow-black/10">
              <img
                src="/VektorLogo.png?v=20260422b"
                alt="Vektor"
                className="size-8 object-contain"
              />
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-semibold uppercase tracking-[0.24em] text-foreground/90">
                {siteConfig.shortName}
              </span>
              <span className="text-sm text-muted-foreground">
                Research archive and market briefs
              </span>
            </span>
          </Link>
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <nav className="flex flex-wrap items-center gap-2" aria-label="Primary">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-full px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="outline" size="sm" className="rounded-full bg-card/60">
              <a href={siteConfig.links.landing}>About Vektor</a>
            </Button>
            <Button asChild variant="outline" size="sm" className="rounded-full bg-card/60">
              <a href={siteConfig.links.product}>Live PnL</a>
            </Button>
            <Button asChild size="sm" className="rounded-full">
              <a href={`${siteConfig.links.product}/admin`}>Admin Console</a>
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}
