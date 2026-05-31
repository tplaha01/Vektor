import { AlertTriangle } from "lucide-react";
import { LivePnlDashboard } from "@/app/live-pnl-dashboard";
import { backendWebSocketUrl, getLivePnlDashboardData } from "@/lib/live-api";

export const dynamic = "force-dynamic";

export default async function Home() {
  try {
    const data = await getLivePnlDashboardData();
    return <LivePnlDashboard data={data} wsUrl={backendWebSocketUrl()} />;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Live PnL API request failed";

    return (
      <main className="min-h-[calc(100vh-10rem)]">
        <section className="vektor-section py-8 lg:py-10">
          <div className="rounded-lg border border-destructive/40 bg-card/70 p-6 shadow-black-soft">
            <AlertTriangle className="mb-4 size-5 text-destructive" aria-hidden="true" />
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-destructive">
              Backend data unavailable
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-foreground">
              Live PnL could not load
            </h1>
            <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
              {message}
            </p>
          </div>
        </section>
      </main>
    );
  }
}
