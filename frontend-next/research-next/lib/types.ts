export type ResearchCategory =
  | "Market Brief"
  | "Research Note"
  | "Signal Report"
  | "Model Memo"
  | "Risk Review";

export type SignalDirection = "buy" | "sell" | "hold";

export interface ResearchAuthor {
  name: string;
  role: string;
  desk: string;
}

export interface ResearchPaper {
  slug: string;
  title: string;
  subtitle: string;
  abstract: string;
  category: ResearchCategory;
  authors: ResearchAuthor[];
  publishedAt: string;
  updatedAt: string;
  tickers: string[];
  tags: string[];
  readingMinutes: number;
  confidence: number;
  signalDirection: SignalDirection;
  horizon: "intraday" | "swing" | "position" | "strategic";
  dataFreshness: "live" | "delayed" | "backtest" | "degraded";
}

export interface SignalReport {
  id: string;
  paperSlug: string;
  generatedAt: string;
  symbol: string;
  direction: SignalDirection;
  confidence: number;
  expectedHorizon: string;
  thesis: string;
  technicalScore: number;
  fundamentalScore: number;
  sentimentScore: number;
  modelScore: number;
  policyStatus: "approved" | "blocked" | "review";
  traceIds: {
    runId: string;
    decisionId: string;
    modelVersion: string;
  };
}
