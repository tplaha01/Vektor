import type {
  BackendOrder,
  BackendPosition,
  LivePnlDashboardData,
  MetricsSummary,
  PerformanceSnapshot,
  PerformanceSummary,
  RiskStatus,
} from "@/lib/types";

const backendBase =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.VITE_BACKEND_URL ||
  "http://localhost:8000";

const apiKey = process.env.NEXT_PUBLIC_API_KEY || process.env.VITE_API_KEY || "";

function headers() {
  return apiKey ? { "X-API-Key": apiKey } : undefined;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${backendBase}${path}`, {
    headers: headers(),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Live PnL API request failed: ${response.status} ${path}`);
  }

  return response.json() as Promise<T>;
}

export function backendWebSocketUrl(path = "/ws") {
  const explicit = process.env.NEXT_PUBLIC_BACKEND_WS_URL || process.env.VITE_BACKEND_WS_URL;
  if (explicit) return explicit;

  return backendBase.replace(/^http/i, "ws") + path;
}

export async function getPositions() {
  return fetchJson<BackendPosition[]>("/paper/positions");
}

export async function getOrders() {
  return fetchJson<BackendOrder[]>("/paper/orders");
}

export async function getPerformanceSummary() {
  return fetchJson<PerformanceSummary>("/fund/performance/summary");
}

export async function getPerformanceSnapshots(limit = 120) {
  return fetchJson<PerformanceSnapshot[]>(
    `/fund/performance/snapshots?limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function getMetricsSummary() {
  return fetchJson<MetricsSummary>("/api/admin/metrics/summary");
}

export async function getRiskStatus() {
  return fetchJson<RiskStatus>("/risk/status");
}

export async function getMarketPrices() {
  return fetchJson<Record<string, number>>("/market/prices");
}

export async function getLivePnlDashboardData(): Promise<LivePnlDashboardData> {
  const [
    positions,
    orders,
    performanceSummary,
    snapshots,
    metrics,
    risk,
    prices,
  ] = await Promise.all([
    getPositions(),
    getOrders(),
    getPerformanceSummary(),
    getPerformanceSnapshots(),
    getMetricsSummary(),
    getRiskStatus(),
    getMarketPrices(),
  ]);

  return {
    positions,
    orders,
    performanceSummary,
    snapshots,
    metrics,
    risk,
    prices,
  };
}
