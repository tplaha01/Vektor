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
  underlier_symbol?: string | null;
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
  underlier_symbol?: string | null;
  contract_multiplier?: number | null;
  metadata?: Record<string, unknown>;
}

export interface PerformanceBenchmark {
  symbol: string;
  price: number;
  baseline_price: number;
  baseline_at: string;
  return_pct: number;
}

export interface PerformanceSnapshot {
  snapshot_id: string;
  snapshot_kind: string;
  recorded_at: string;
  broker_mode: string;
  equity: number;
  cash: number;
  market_value: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_trades: number;
  closed_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  max_drawdown: number;
  positions: BackendPosition[];
  benchmarks: PerformanceBenchmark[];
  metadata?: Record<string, unknown>;
}

export interface PerformanceSummary {
  enabled: boolean;
  snapshot_count: number;
  daily_snapshot_count: number;
  latest_snapshot?: PerformanceSnapshot | null;
  inception_snapshot?: PerformanceSnapshot | null;
  track_record?: {
    total_return_pct?: number;
    max_drawdown_pct?: number;
    sharpe_ratio?: number;
    alpha_vs_primary_benchmark_pct?: number;
    primary_benchmark_return_pct?: number;
    sample_days?: number;
  };
  baselines?: Record<string, unknown>;
}

export interface MetricsSummary {
  total_equity: number;
  equity_change: number;
  account_equity: number;
  external_capital_flow_usd: number;
  baseline_equity: number;
  realized_pnl: number;
  pnl_change: number;
  unrealized_pnl: number;
  current_drawdown: number;
  drawdown_change: number;
  max_drawdown_ytd: number;
  max_drawdown_threshold: number;
  active_positions: number;
  win_rate: number;
  win_rate_change: number;
  sharpe_ratio: number;
  sharpe_change: number;
}

export interface RiskStatus {
  equity?: number;
  drawdown_breaker?: {
    halted?: boolean;
    peak_equity?: number;
    current_drawdown?: number;
    max_drawdown_threshold?: number;
    halt_timestamp?: string | null;
  };
  open_stops?: unknown[];
}

export interface LivePnlDashboardData {
  positions: BackendPosition[];
  orders: BackendOrder[];
  performanceSummary: PerformanceSummary;
  snapshots: PerformanceSnapshot[];
  metrics: MetricsSummary;
  risk: RiskStatus;
  prices: Record<string, number>;
}

export interface PortfolioChartPoint {
  date: string;
  equity: number;
  benchmark: number | null;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}
