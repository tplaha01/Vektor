/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { siteConfig } from "@/lib/site";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/trades", label: "Trade log" },
];

const siteLinks = [
  { href: siteConfig.links.landing, label: "Landing" },
  { href: siteConfig.links.blog, label: "Blog" },
  { href: siteConfig.links.research, label: "Research" },
  { href: siteConfig.links.livePnl, label: "Live PnL" },
  { href: siteConfig.links.admin, label: "Admin" },
];

export function SiteNav() {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-border bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/65">
      <div className="mx-auto flex min-h-20 w-full max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-lg border border-border bg-card/70 shadow-sm shadow-black/10">
            <img
              src="/VektorLogo.png?v=20260422b"
              alt="Vektor"
              className="size-8 object-contain"
            />
          </span>
          <span className="flex flex-col">
            <span className="font-mono text-sm font-semibold uppercase tracking-[0.24em] text-foreground/90">
              {siteConfig.shortName}
            </span>
            <span className="font-mono text-sm text-muted-foreground">
              Live paper-trading performance
            </span>
          </span>
        </Link>

        <div className="flex flex-col gap-3 lg:items-end">
          <nav className="flex flex-wrap items-center gap-2" aria-label="Primary">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-full px-3 py-2 font-mono text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex flex-wrap items-center gap-2">
            {siteLinks.map((item) => (
              <Button
                key={item.href}
                asChild
                variant={item.label === "Live PnL" ? "default" : "outline"}
                size="sm"
                className="rounded-full bg-card/60"
              >
                <a href={item.href}>{item.label}</a>
              </Button>
            ))}
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}
