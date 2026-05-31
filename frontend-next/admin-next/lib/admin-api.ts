export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonRecord = Record<string, JsonValue>;

export type ApiResult<T = JsonValue> =
  | { ok: true; data: T; path: string }
  | { ok: false; error: string; path: string };

export interface BackendPosition {
  symbol: string;
  qty: number;
  avg_price: number;
  market_price: number;
  market_value: number;
  unrealized_pnl: number;
  asset_class?: string | null;
  instrument_type?: string | null;
  routing_mode?: string | null;
}

export interface BackendOrder {
  id: string;
  symbol: string;
  side: string;
  qty?: number | null;
  quantity?: number | null;
  avg_price?: number | null;
  price?: number | null;
  status: string;
  created_at?: string | null;
  timestamp?: string | null;
  asset_class?: string | null;
  instrument_type?: string | null;
  routing_mode?: string | null;
}

const backendBase =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.VITE_BACKEND_URL ||
  "http://localhost:8000";

const apiKey = process.env.NEXT_PUBLIC_API_KEY || process.env.VITE_API_KEY || "";

function headers(method = "GET") {
  const base: Record<string, string> = {};
  if (apiKey) base["X-API-Key"] = apiKey;
  if (method !== "GET") base["Content-Type"] = "application/json";
  return base;
}

export async function fetchJson<T = JsonValue>(path: string): Promise<T> {
  const response = await fetch(`${backendBase}${path}`, {
    headers: headers(),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText || "API error"} at ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function safeFetchJson<T = JsonValue>(path: string): Promise<ApiResult<T>> {
  try {
    return { ok: true, data: await fetchJson<T>(path), path };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "API request failed",
      path,
    };
  }
}

export async function postJson<T = JsonValue>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${backendBase}${path}`, {
    method: "POST",
    headers: headers("POST"),
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText || "API error"} at ${path}`);
  }

  return response.json() as Promise<T>;
}

export function dataOr<T>(result: ApiResult<T>, fallback: T): T {
  return result.ok ? result.data : fallback;
}

export function recordValue(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

export function arrayValue<T = JsonValue>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function stringValue(value: unknown, fallback = "Unavailable") {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

export function numberValue(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function boolValue(value: unknown, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
}

export function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

export function percent(value: number) {
  return `${Number(value || 0).toFixed(2)}%`;
}

export function formatDateTime(value: unknown) {
  if (typeof value !== "string" || !value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function endpointError(result: ApiResult<unknown>) {
  return result.ok ? null : `${result.path}: ${result.error}`;
}
