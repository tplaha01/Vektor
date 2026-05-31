import { Gauge } from "lucide-react";
import { Bar, EndpointError, JsonPanel, StatCard } from "@/components/backend-panels";
import {
  arrayValue,
  dataOr,
  money,
  numberValue,
  recordValue,
  safeFetchJson,
  stringValue,
  type JsonRecord,
} from "@/lib/admin-api";

export const dynamic = "force-dynamic";

export default async function MarketWatchPage() {
  const [pricesResult, marketWatchResult, streamStatusResult, spyNewsResult, nvdaNewsResult] =
    await Promise.all([
      safeFetchJson<Record<string, number>>("/market/prices"),
      safeFetchJson<JsonRecord>("/api/admin/ceo/market-watch"),
      safeFetchJson<JsonRecord>("/fund/stream/status"),
      safeFetchJson<JsonRecord[]>("/news/SPY"),
      safeFetchJson<JsonRecord[]>("/news/NVDA"),
    ]);

  const prices = dataOr(pricesResult, {});
  const entries = Object.entries(prices).sort(([a], [b]) => a.localeCompare(b));
  const marketWatch = dataOr(marketWatchResult, {});
  const streamStatus = dataOr(streamStatusResult, {});
  const news = [...dataOr(spyNewsResult, []), ...dataOr(nvdaNewsResult, [])];
  const maxPrice = entries.reduce((max, [, value]) => Math.max(max, Number(value || 0)), 0);

  return (
    <main className="min-h-screen p-5 lg:p-8">
      <div className="border-b border-border pb-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          /market-watch
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground md:text-5xl">
          Market Watch
        </h1>
        <p className="mt-3 max-w-3xl font-mono text-sm leading-6 text-muted-foreground">
          Watchlist prices, market intelligence, stream state, and live news from
          TradingBot backend routes.
        </p>
      </div>

      <section className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Symbols" value={entries.length} />
        <StatCard label="Stream" value={stringValue(recordValue(streamStatus).status)} />
        <StatCard label="News Items" value={news.length} />
        <StatCard label="Highest Price" value={money(maxPrice)} />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
          <div className="mb-4 flex items-center gap-2">
            <Gauge className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-card-foreground">Backend Watchlist</h2>
          </div>
          <div className="space-y-3">
            {entries.map(([symbol, price]) => (
              <div key={symbol} className="rounded-md border border-border bg-background/50 p-3">
                <div className="mb-2 flex justify-between gap-3 font-mono text-xs">
                  <span className="font-semibold text-foreground">{symbol}</span>
                  <span className="text-muted-foreground">{money(price)}</span>
                </div>
                <Bar value={maxPrice > 0 ? (Number(price) / maxPrice) * 100 : 0} />
              </div>
            ))}
          </div>
          {entries.length === 0 ? (
            <p className="font-mono text-sm text-muted-foreground">
              `/market/prices` returned no symbols.
            </p>
          ) : null}
          <EndpointError result={pricesResult} />
        </aside>

        <div className="space-y-4">
          <JsonPanel title="CEO Market Watch" data={marketWatch} />

          <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
            <h2 className="text-xl font-semibold text-card-foreground">SPY / NVDA News</h2>
            <div className="mt-4 space-y-3">
              {news.map((item, index) => (
                <article key={`${stringValue(item.url, String(index))}-${index}`} className="rounded-md border border-border bg-background/50 p-3">
                  <p className="font-semibold text-foreground">{stringValue(item.headline)}</p>
                  <p className="mt-2 font-mono text-xs text-muted-foreground">
                    {stringValue(item.symbol)} / {stringValue(item.source)} / {stringValue(item.published_at)}
                  </p>
                  {typeof item.url === "string" && item.url ? (
                    <a className="mt-2 inline-flex font-mono text-xs text-primary" href={item.url}>
                      Source
                    </a>
                  ) : null}
                </article>
              ))}
            </div>
            {news.length === 0 ? (
              <p className="font-mono text-sm text-muted-foreground">
                `/news/SPY` and `/news/NVDA` returned no news items.
              </p>
            ) : null}
            <EndpointError result={spyNewsResult} />
            <EndpointError result={nvdaNewsResult} />
          </article>

          <JsonPanel title="Stream Status" data={streamStatus} />
        </div>
      </section>
      <EndpointError result={marketWatchResult} />
      <EndpointError result={streamStatusResult} />
    </main>
  );
}
