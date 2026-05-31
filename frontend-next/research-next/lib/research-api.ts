import type { LiveResearchReport, ResearchReportListResponse } from "@/lib/types";

const backendBase =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.VITE_BACKEND_URL ||
  "http://localhost:8000";

const apiKey = process.env.NEXT_PUBLIC_API_KEY || process.env.VITE_API_KEY || "";

export class ResearchApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = "ResearchApiError";
  }
}

function headers() {
  return apiKey ? { "X-API-Key": apiKey } : undefined;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${backendBase}${path}`, {
    headers: headers(),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ResearchApiError(
      `Research API request failed: ${response.status} ${path}`,
      response.status,
      path,
    );
  }

  return response.json() as Promise<T>;
}

export async function getResearchReports({
  limit = 80,
  offset = 0,
  surface = "public",
  status = "published",
}: {
  limit?: number;
  offset?: number;
  surface?: "public" | "kb" | "all";
  status?: "published" | "all";
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    surface,
    status,
  });

  return fetchJson<ResearchReportListResponse>(`/api/research/reports?${params}`);
}

export async function getResearchReport(reportId: string): Promise<LiveResearchReport> {
  return fetchJson<LiveResearchReport>(
    `/api/research/reports/${encodeURIComponent(reportId)}`,
  );
}

export function reportHref(report: Pick<LiveResearchReport, "report_id">) {
  return `/paper/${encodeURIComponent(report.report_id)}`;
}
