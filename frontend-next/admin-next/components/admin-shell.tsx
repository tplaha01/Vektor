import Link from "next/link";
import {
  Brain,
  Database,
  Gauge,
  Home,
  MemoryStick,
  RadioTower,
  Scale,
  Settings,
  Shield,
  Target,
} from "lucide-react";
import { siteConfig } from "@/lib/site";

const navItems = [
  { href: "/war-room", label: "War Room", icon: Home },
  { href: "/core-engine", label: "Core Engine", icon: Brain },
  { href: "/agents", label: "Agents", icon: RadioTower },
  { href: "/positions", label: "Positions", icon: Target },
  { href: "/market-watch", label: "Market Watch", icon: Gauge },
  { href: "/data-pipeline", label: "Data Pipeline", icon: Database },
  { href: "/compliance", label: "Compliance", icon: Scale },
  { href: "/memory", label: "Memory", icon: MemoryStick },
  { href: "/settings", label: "Settings", icon: Settings },
];

const siteLinks = [
  { href: siteConfig.links.landing, label: "Landing" },
  { href: siteConfig.links.blog, label: "Blog" },
  { href: siteConfig.links.research, label: "Research" },
  { href: siteConfig.links.livePnl, label: "Live PnL" },
  { href: siteConfig.links.admin, label: "Admin" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-border bg-card/80 p-5 backdrop-blur-xl lg:block">
        <Link href="/war-room" className="flex items-center gap-3 border-b border-border pb-5">
          <span className="flex size-11 items-center justify-center rounded-lg border border-primary/30 bg-primary/10">
            <Shield className="size-5 text-primary" aria-hidden="true" />
          </span>
          <span>
            <span className="block font-mono text-sm font-semibold uppercase tracking-[0.24em]">
              Vektor
            </span>
            <span className="block font-mono text-xs text-muted-foreground">
              Admin command center
            </span>
          </span>
        </Link>

        <nav className="mt-5 space-y-1" aria-label="Admin tabs">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 rounded-md px-3 py-2.5 font-mono text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                <Icon className="size-4 text-primary" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute inset-x-5 bottom-5 border-t border-border pt-4">
          <p className="mb-2 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
            Cross Links
          </p>
          <div className="flex flex-wrap gap-2">
            {siteLinks.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded border border-border bg-background/60 px-2 py-1 font-mono text-[0.65rem] text-muted-foreground hover:text-primary"
              >
                {item.label}
              </a>
            ))}
          </div>
        </div>
      </aside>

      <div className="lg:ml-72">
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 px-5 py-4 backdrop-blur-xl lg:hidden">
          <p className="font-mono text-sm font-semibold uppercase tracking-[0.24em]">
            Vektor Admin
          </p>
        </header>
        {children}
      </div>
    </div>
  );
}
