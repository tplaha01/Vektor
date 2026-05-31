import { AlertTriangle } from "lucide-react";
import type { ApiResult } from "@/lib/admin-api";

export function EndpointError({ result }: { result: ApiResult<unknown> }) {
  if (result.ok) return null;

  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 font-mono text-xs text-destructive">
      <AlertTriangle className="mb-2 size-4" aria-hidden="true" />
      {result.path}: {result.error}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  tone = "text-foreground",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: string;
}) {
  return (
    <article className="rounded-lg border border-border bg-card/70 p-4 shadow-black-soft">
      <p className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <p className={`mt-3 text-2xl font-semibold ${tone}`}>{value}</p>
      {sub ? <p className="mt-1 font-mono text-xs text-muted-foreground">{sub}</p> : null}
    </article>
  );
}

export function JsonPanel({
  title,
  data,
}: {
  title: string;
  data: unknown;
}) {
  return (
    <article className="rounded-lg border border-border bg-card/70 p-5 shadow-black-soft">
      <h2 className="text-lg font-semibold text-card-foreground">{title}</h2>
      <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-background/70 p-3 font-mono text-xs leading-6 text-muted-foreground">
        {JSON.stringify(data, null, 2)}
      </pre>
    </article>
  );
}

export function Bar({
  value,
  tone = "bg-primary",
}: {
  value: number;
  tone?: string;
}) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div className="h-2 rounded-full bg-muted">
      <div className={`h-2 rounded-full ${tone}`} style={{ width: `${width}%` }} />
    </div>
  );
}
