export interface LiveResearchReport {
  report_id: string;
  agent_id: string;
  agent_role: string;
  surface: "public" | "kb" | string;
  run_id?: string | null;
  title: string;
  summary: string;
  findings: string[];
  asset_universe: string[];
  confidence: number;
  created_at: string;
  published_at: string;
  status: string;
  views?: number | null;
  provider_used?: string | null;
  model_used?: string | null;
  ai_trace: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

export interface ResearchReportListResponse {
  reports: LiveResearchReport[];
  total: number;
  limit: number;
  offset: number;
}
