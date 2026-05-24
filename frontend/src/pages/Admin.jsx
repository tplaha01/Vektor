import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Bot,
  Database,
  Globe,
  LineChart,
  Pause,
  Play,
  RefreshCw,
  Settings,
  Shield,
  Sigma,
  TrendingUp,
  Workflow,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import '../styles/admin-portal.css';
import { adminAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ToastContainer from '../components/common/Toast';

const backendTarget = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const POLL_INTERVAL_MS = 20000;
const RETRY_INTERVAL_MS = 60000;

const navigationItems = [
  {
    id: 'overview',
    label: 'Overview',
    icon: Sigma,
    description: 'Fund state, deterministic profile, and live book context',
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    icon: Database,
    description: 'Data freshness, provider posture, and signal candidates',
  },
  {
    id: 'portfolio',
    label: 'Portfolio',
    icon: LineChart,
    description: 'Positions, allocation usage, and benchmark context',
  },
  {
    id: 'market',
    label: 'Market',
    icon: Globe,
    description: 'Tape board, headline feed, and coverage universe',
  },
  {
    id: 'controls',
    label: 'Controls',
    icon: Settings,
    description: 'Runtime actions, policy boundaries, and lineage state',
  },
];

const safeArray = (value) => (Array.isArray(value) ? value : []);

const titleize = (value) =>
  String(value || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const toneClassName = (tone) => {
  if (tone === 'good') return 'ops-tone-good';
  if (tone === 'caution') return 'ops-tone-caution';
  if (tone === 'bad') return 'ops-tone-bad';
  return 'ops-tone-neutral';
};

const statusTone = (value, { neutralDisabled = false } = {}) => {
  const normalized = String(value || '').trim().toLowerCase();

  if (!normalized) return 'neutral';
  if (neutralDisabled && ['disabled', 'standby', 'paused'].includes(normalized)) return 'neutral';
  if (['healthy', 'provider', 'paper only', 'running', 'clear', 'connected', 'ready', 'active', 'ok'].includes(normalized)) {
    return 'good';
  }
  if (['fallback', 'degraded', 'warning', 'caution'].includes(normalized)) return 'caution';
  if (['blocked', 'error', 'failed', 'down', 'halted'].includes(normalized)) return 'bad';
  if (['disabled', 'standby', 'paused'].includes(normalized)) return 'neutral';
  return 'neutral';
};

const currency = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });

const number = (value) => Number(value || 0).toLocaleString();

const plainPercent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

const signedPlainPercent = (value, digits = 2) => {
  const numeric = Number(value || 0);
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(digits)}%`;
};

const ratioPercent = (value, digits = 0) => `${(Number(value || 0) * 100).toFixed(digits)}%`;

const summarize = (value, max = 180) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return 'No live detail published yet.';
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const formatDateTime = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleString();
};

const formatRelative = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.round(diffMs / 60000);
  if (Math.abs(diffMinutes) < 1) return 'just now';
  if (Math.abs(diffMinutes) < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
};

const providerNotice = (reason) => {
  const normalized = String(reason || '').trim();
  if (!normalized) return 'No stream warning published.';
  if (normalized === 'parallel_alpaca_ws_disabled') {
    return 'News websocket is parked while the market stream owns the Alpaca connection budget.';
  }
  return titleize(normalized);
};

function Panel({ eyebrow, title, description, actions, className = '', children }) {
  return (
    <section className={`ops-panel ${className}`.trim()}>
      <div className="ops-panel-header">
        <div>
          {eyebrow ? <p className="ops-panel-eyebrow">{eyebrow}</p> : null}
          <h2 className="ops-panel-title">{title}</h2>
          {description ? <p className="ops-panel-description">{description}</p> : null}
        </div>
        {actions ? <div className="ops-panel-actions">{actions}</div> : null}
      </div>
      <div className="ops-panel-body">{children}</div>
    </section>
  );
}

function NavItem({ active, item, onSelect }) {
  const Icon = item.icon;

  return (
    <button
      type="button"
      className={`ops-nav-item ${active ? 'is-active' : ''}`}
      onClick={() => onSelect(item.id)}
    >
      <span className="ops-nav-icon">
        <Icon size={16} />
      </span>
      <span className="ops-nav-copy">
        <strong>{item.label}</strong>
        <small>{item.description}</small>
      </span>
    </button>
  );
}

function TonePill({ tone, children }) {
  return <span className={`ops-pill ${toneClassName(tone)}`}>{children}</span>;
}

function MetricTile({ icon: Icon, label, value, detail, tone = 'neutral' }) {
  return (
    <article className={`ops-metric ${toneClassName(tone)}`}>
      <div className="ops-metric-head">
        <div>
          <span className="ops-metric-label">{label}</span>
          <strong className="ops-metric-value">{value}</strong>
        </div>
        <span className="ops-metric-icon">
          <Icon size={16} />
        </span>
      </div>
      <p className="ops-metric-detail">{detail}</p>
    </article>
  );
}

export default function Admin() {
  const { success, error: showError } = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [metrics, setMetrics] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [mlStatus, setMlStatus] = useState(null);
  const [riskStatus, setRiskStatus] = useState(null);
  const [runtimeControl, setRuntimeControl] = useState(null);
  const [workersStatus, setWorkersStatus] = useState(null);
  const [performanceSummary, setPerformanceSummary] = useState(null);
  const [performanceSnapshots, setPerformanceSnapshots] = useState([]);
  const [paperPositions, setPaperPositions] = useState([]);
  const [marketWatch, setMarketWatch] = useState(null);
  const [knowledgeStats, setKnowledgeStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [busyAction, setBusyAction] = useState('');
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  const fetchAdminState = useCallback(
    async ({ manual = false } = {}) => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;
      if (manual) setRefreshing(true);

      try {
        setConnectionStatus((previous) => (previous === 'connected' ? 'connected' : 'connecting'));

        const results = await Promise.allSettled([
          adminAPI.getMetricsSummary(),
          adminAPI.getSystemStatusBadges(),
          adminAPI.getDataPipelineStatus(),
          adminAPI.getMlStatus(),
          adminAPI.getRiskStatus(),
          adminAPI.getRuntimeControlStatus(),
          adminAPI.getFundWorkersStatus(),
          adminAPI.getPerformanceSummary(),
          adminAPI.getPerformanceSnapshots({ limit: 32 }),
          adminAPI.getPaperPositions(),
          adminAPI.getMarketWatch(),
          adminAPI.getKnowledgeStats(),
        ]);

        if (!isMounted.current) return;

        const coreResults = [results[0], results[1], results[2], results[7], results[9], results[10]];
        if (coreResults.every((result) => result.status === 'rejected')) {
          throw new Error(String(coreResults[0]?.reason?.message || 'backend_unreachable'));
        }

        const [
          metricsResult,
          systemStatusResult,
          pipelineStatusResult,
          mlStatusResult,
          riskStatusResult,
          runtimeControlResult,
          workersStatusResult,
          performanceSummaryResult,
          performanceSnapshotsResult,
          paperPositionsResult,
          marketWatchResult,
          knowledgeStatsResult,
        ] = results;

        if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value);
        if (systemStatusResult.status === 'fulfilled') setSystemStatus(systemStatusResult.value);
        if (pipelineStatusResult.status === 'fulfilled') setPipelineStatus(pipelineStatusResult.value);
        if (mlStatusResult.status === 'fulfilled') setMlStatus(mlStatusResult.value);
        if (riskStatusResult.status === 'fulfilled') setRiskStatus(riskStatusResult.value);
        if (runtimeControlResult.status === 'fulfilled') setRuntimeControl(runtimeControlResult.value);
        if (workersStatusResult.status === 'fulfilled') setWorkersStatus(workersStatusResult.value);
        if (performanceSummaryResult.status === 'fulfilled') setPerformanceSummary(performanceSummaryResult.value);
        if (performanceSnapshotsResult.status === 'fulfilled') {
          setPerformanceSnapshots(adminAPI.normalizeArray(performanceSnapshotsResult.value, 'snapshots'));
        }
        if (paperPositionsResult.status === 'fulfilled') {
          setPaperPositions(adminAPI.normalizeArray(paperPositionsResult.value, 'positions'));
        }
        if (marketWatchResult.status === 'fulfilled') setMarketWatch(marketWatchResult.value);
        if (knowledgeStatsResult.status === 'fulfilled') setKnowledgeStats(knowledgeStatsResult.value);

        setConnectionStatus('connected');
        setLastUpdate(new Date().toISOString());
        if (manual) success('Admin snapshot refreshed');
      } catch (err) {
        if (!isMounted.current) return;
        console.error('Failed to load admin snapshot:', err);
        setConnectionStatus('error');
        if (manual) showError(`Refresh failed: ${err.message}`);
      } finally {
        if (isMounted.current) {
          setLoading(false);
          setRefreshing(false);
        }
        fetchInProgress.current = false;
      }
    },
    [showError, success]
  );

  useEffect(() => {
    isMounted.current = true;
    fetchAdminState();

    const interval = window.setInterval(() => {
      fetchAdminState();
    }, connectionStatus === 'error' ? RETRY_INTERVAL_MS : POLL_INTERVAL_MS);

    return () => {
      isMounted.current = false;
      window.clearInterval(interval);
    };
  }, [connectionStatus, fetchAdminState]);

  const handleRuntimeAction = useCallback(
    async (actionKey) => {
      try {
        setBusyAction(actionKey);

        switch (actionKey) {
          case 'resume':
            await adminAPI.resumeRuntime();
            success('Runtime resume requested');
            break;
          case 'pause':
            await adminAPI.pauseRuntime();
            success('Runtime pause requested');
            break;
          case 'recover':
            await adminAPI.recoverDeterministicMlRuntime();
            success('Deterministic runtime recovery requested');
            break;
          case 'clear-halt':
            await adminAPI.clearSystemHalt();
            success('System halt clear requested');
            break;
          case 'capture':
            await adminAPI.capturePerformanceSnapshot({
              snapshotKind: 'manual',
              reason: 'manual_admin_capture',
            });
            success('Performance snapshot captured');
            break;
          default:
            return;
        }
      } catch (err) {
        showError(`${titleize(actionKey)} failed: ${err.message}`);
      } finally {
        setBusyAction('');
        fetchAdminState();
      }
    },
    [fetchAdminState, showError, success]
  );

  const activeProfile = useMemo(() => {
    const profiles = safeArray(mlStatus?.core_engine?.available_profiles);
    return profiles.find((profile) => profile?.name === mlStatus?.core_engine?.active_profile) || null;
  }, [mlStatus]);

  const packWeights = activeProfile?.stack_weights || {};
  const latestRun = pipelineStatus?.last_run || null;
  const latestSnapshot = performanceSummary?.latest_snapshot || null;

  const positions = useMemo(
    () =>
      safeArray(paperPositions)
        .map((position) => {
          const quantity = Number(position.qty ?? position.quantity ?? 0);
          const avgPrice = Number(position.avg_price ?? 0);
          const marketPrice = Number(position.market_price ?? avgPrice);
          const marketValue = Number(position.market_value ?? quantity * marketPrice);
          const unrealizedPnl = Number(position.unrealized_pnl ?? marketValue - quantity * avgPrice);
          const costBasis = Math.abs(quantity * avgPrice);
          const returnPct = costBasis > 0 ? (unrealizedPnl / costBasis) * 100 : 0;

          return {
            ...position,
            quantity,
            avgPrice,
            marketPrice,
            marketValue,
            unrealizedPnl,
            returnPct,
          };
        })
        .sort((left, right) => right.unrealizedPnl - left.unrealizedPnl),
    [paperPositions]
  );

  const strongestPosition = positions[0] || null;
  const weakestPosition = useMemo(() => {
    if (!positions.length) return null;
    return positions.reduce(
      (currentWorst, row) =>
        row.unrealizedPnl < (currentWorst?.unrealizedPnl ?? Number.POSITIVE_INFINITY) ? row : currentWorst,
      null
    );
  }, [positions]);

  const allocationRows = useMemo(
    () =>
      Object.entries(systemStatus?.allocation_policy?.asset_classes || {})
        .map(([assetClass, row]) => {
          const allocatedUsd = Number(row?.allocated_usd || 0);
          const usedUsd = Number(row?.used_usd || 0);

          return {
            assetClass,
            weight: Number(row?.weight || 0),
            allocatedUsd,
            usedUsd,
            remainingUsd: Number(row?.remaining_usd || 0),
            liveExposureUsd: Number(row?.live_exposure_usd || 0),
            utilization: allocatedUsd > 0 ? usedUsd / allocatedUsd : 0,
          };
        })
        .sort((left, right) => right.allocatedUsd - left.allocatedUsd),
    [systemStatus]
  );

  const candidateRows = useMemo(
    () =>
      Object.entries(latestRun?.quality || {})
        .map(([symbol, row]) => ({
          symbol,
          category: row?.features?.category || 'unknown',
          score: Number(row?.features?.score || 0),
          textEvents: Number(row?.text?.events || 0),
          textScore: Number(row?.text?.avg_score || 0),
          priceScore: Number(row?.price?.score || 0),
          priceFlags: safeArray(row?.price?.flags),
          barsStatus: row?.bars?.skipped || row?.bars?.status || 'ready',
          fundamentalsStatus: row?.fundamentals?.skipped || row?.fundamentals?.status || 'ready',
        }))
        .sort((left, right) => right.score - left.score),
    [latestRun]
  );

  const tradeCandidates = candidateRows.filter((row) => row.category === 'trade_candidate');

  const candidateBuckets = useMemo(
    () =>
      candidateRows.reduce((bucket, row) => {
        bucket[row.category] = Number(bucket[row.category] || 0) + 1;
        return bucket;
      }, {}),
    [candidateRows]
  );

  const performanceSeries = useMemo(
    () =>
      safeArray(performanceSnapshots).map((snapshot) => ({
        label: new Date(snapshot.recorded_at).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }),
        equity: Number(snapshot.equity || 0),
        totalPnl: Number(snapshot.total_pnl || 0),
      })),
    [performanceSnapshots]
  );

  const headerBadges = useMemo(
    () => [
      {
        label: 'Orchestration',
        value: systemStatus?.orchestration?.status || 'Unknown',
        tone: statusTone(systemStatus?.orchestration?.status),
      },
      {
        label: 'Data Source',
        value: systemStatus?.data_source?.status || 'Unknown',
        tone: statusTone(systemStatus?.data_source?.status),
      },
      {
        label: 'Execution',
        value: systemStatus?.execution_mode?.status || 'Unknown',
        tone: statusTone(systemStatus?.execution_mode?.status),
      },
      {
        label: 'AI Support',
        value: workersStatus?.ai_role_adapter?.enabled ? 'Ready' : 'Standby',
        tone: workersStatus?.ai_role_adapter?.enabled ? 'good' : 'neutral',
      },
    ],
    [systemStatus, workersStatus]
  );

  const topNamespaceRows = useMemo(
    () =>
      Object.entries(knowledgeStats?.namespace_counts || {})
        .map(([key, count]) => ({ key, count: Number(count || 0) }))
        .sort((left, right) => right.count - left.count)
        .slice(0, 8),
    [knowledgeStats]
  );

  const stageCards = useMemo(
    () => [
      {
        key: 'data',
        icon: Database,
        title: 'Data Integrity',
        tone: statusTone(systemStatus?.data_source?.status),
        status: systemStatus?.data_source?.status || 'Unknown',
        detail: pipelineStatus?.enabled
          ? `${safeArray(pipelineStatus?.configured_symbols).length} symbols · ${number(latestRun?.counts?.prices)} prices · ${number(latestRun?.counts?.text_events)} text events`
          : 'Pipeline disabled',
      },
      {
        key: 'model',
        icon: Sigma,
        title: 'Model Routing',
        tone: activeProfile ? 'good' : 'neutral',
        status: activeProfile?.name || 'No profile',
        detail: activeProfile
          ? `Tech ${ratioPercent(packWeights.technical)} · Fund ${ratioPercent(packWeights.fundamental)} · Sent ${ratioPercent(packWeights.sentiment)}`
          : 'Weights are not available yet.',
      },
      {
        key: 'policy',
        icon: Shield,
        title: 'Policy Gate',
        tone: systemStatus?.halt?.halted ? 'bad' : 'good',
        status: systemStatus?.halt?.halted ? 'Halted' : 'Clear',
        detail: `Conf ${ratioPercent(activeProfile?.min_confidence)} · Utility ${ratioPercent(activeProfile?.min_expected_utility)} · DD ${plainPercent(metrics?.current_drawdown)}/${plainPercent(metrics?.max_drawdown_threshold, 0)}`,
      },
      {
        key: 'execution',
        icon: LineChart,
        title: 'Paper Executor',
        tone: statusTone(systemStatus?.execution_mode?.status),
        status: systemStatus?.execution_mode?.status || 'Unknown',
        detail: `${positions.length} positions · ${currency(latestSnapshot?.market_value)} deployed · runtime ${runtimeControl?.runtime_started ? 'running' : 'paused'}`,
      },
      {
        key: 'support',
        icon: Bot,
        title: 'AI Support',
        tone: workersStatus?.ai_role_adapter?.enabled ? 'good' : 'neutral',
        status: workersStatus?.ai_role_adapter?.enabled ? 'Ready' : 'Standby',
        detail: workersStatus?.ai_role_adapter?.enabled
          ? `${workersStatus.ai_role_adapter.default_model || 'model'} via ${workersStatus.ai_role_adapter.provider || 'router'}`
          : 'Research and editorial only. Kept off the deterministic trade path.',
      },
    ],
    [activeProfile, latestRun, latestSnapshot, metrics, packWeights, pipelineStatus, positions.length, runtimeControl, systemStatus, workersStatus]
  );

  const initialLoading = loading && !metrics && !systemStatus && !pipelineStatus;
  const fallbackProvider = safeArray(systemStatus?.data_source?.providers).find(
    (provider) => String(provider?.mode || '').toLowerCase() === 'fallback'
  );
  const recoveryChecklist = safeArray(systemStatus?.halt?.recovery_checklist || runtimeControl?.recovery_checklist);
  const supportRoleModels = Object.entries(workersStatus?.ai_role_adapter?.role_models || {}).slice(0, 6);

  const renderOverview = () => (
    <>
      <div className="ops-metric-grid">
        <MetricTile
          icon={Activity}
          label="Total Equity"
          value={currency(metrics?.total_equity)}
          detail={`Baseline ${currency(metrics?.baseline_equity)} · ${signedPlainPercent(metrics?.equity_change)}`}
          tone="good"
        />
        <MetricTile
          icon={TrendingUp}
          label="Unrealized P&L"
          value={currency(metrics?.unrealized_pnl)}
          detail={`Market value ${currency(latestSnapshot?.market_value)} · ${positions.length} live positions`}
          tone={Number(metrics?.unrealized_pnl || 0) >= 0 ? 'good' : 'bad'}
        />
        <MetricTile
          icon={Workflow}
          label="Active Positions"
          value={number(metrics?.active_positions)}
          detail={`Paper executor only · cash ${currency(latestSnapshot?.cash)}`}
          tone="neutral"
        />
        <MetricTile
          icon={LineChart}
          label="Sharpe Ratio"
          value={Number(metrics?.sharpe_ratio || 0).toFixed(2)}
          detail={`${performanceSummary?.track_record?.sample_days || 0} sample days`}
          tone={Number(metrics?.sharpe_ratio || 0) >= 1 ? 'good' : 'caution'}
        />
        <MetricTile
          icon={Sigma}
          label="Track Return"
          value={plainPercent(performanceSummary?.track_record?.total_return_pct, 2)}
          detail={`Alpha vs SPY ${signedPlainPercent(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct, 2)}`}
          tone={Number(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct || 0) >= 0 ? 'good' : 'caution'}
        />
        <MetricTile
          icon={Shield}
          label="Current Drawdown"
          value={plainPercent(metrics?.current_drawdown, 2)}
          detail={`Breaker at ${plainPercent(metrics?.max_drawdown_threshold, 0)}`}
          tone={Number(metrics?.current_drawdown || 0) >= Number(metrics?.max_drawdown_threshold || 0) ? 'bad' : 'good'}
        />
      </div>

      <div className="ops-stage-grid">
        {stageCards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.key} className="ops-stage-card">
              <div className="ops-stage-head">
                <span className="ops-stage-icon">
                  <Icon size={16} />
                </span>
                <TonePill tone={card.tone}>{card.status}</TonePill>
              </div>
              <h3 className="ops-stage-title">{card.title}</h3>
              <p className="ops-stage-detail">{card.detail}</p>
            </article>
          );
        })}
      </div>

      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Performance"
          title="Equity Curve"
          description="Latest paper snapshots from the live backend. The chart stays lightweight and avoids embedded market widgets."
        >
          {performanceSeries.length ? (
            <>
              <div className="ops-chart-wrap">
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={performanceSeries} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="opsEquityFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgba(0, 201, 167, 0.45)" />
                        <stop offset="100%" stopColor="rgba(0, 201, 167, 0)" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="label" stroke="rgba(221,225,234,0.5)" tickLine={false} axisLine={false} />
                    <YAxis
                      stroke="rgba(221,225,234,0.5)"
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `$${Math.round(value / 1000)}k`}
                      domain={[
                        (dataMin) => Math.max(0, dataMin - 50),
                        (dataMax) => dataMax + 50,
                      ]}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 12,
                        border: '1px solid rgba(255,255,255,0.08)',
                        backgroundColor: '#0f141c',
                      }}
                      formatter={(value) => currency(value)}
                    />
                    <Area
                      type="monotone"
                      dataKey="equity"
                      stroke="#00c9a7"
                      strokeWidth={2}
                      fill="url(#opsEquityFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="ops-kv-grid ops-kv-grid-tight">
                <div className="ops-kv">
                  <span className="ops-kv-label">Latest snapshot</span>
                  <strong className="ops-kv-value">{formatDateTime(latestSnapshot?.recorded_at)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Primary benchmark</span>
                  <strong className="ops-kv-value">
                    {plainPercent(performanceSummary?.track_record?.primary_benchmark_return_pct, 2)}
                  </strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Alpha vs primary benchmark</span>
                  <strong className="ops-kv-value">
                    {signedPlainPercent(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct, 2)}
                  </strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Snapshot count</span>
                  <strong className="ops-kv-value">{number(performanceSummary?.snapshot_count)}</strong>
                </div>
              </div>
            </>
          ) : (
            <div className="ops-empty">Performance snapshots have not loaded yet.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Model Contract"
          title="Active Deterministic Profile"
          description="The frontend now surfaces the actual backend profile contract instead of placeholder AI roles."
        >
          <div className="ops-profile-summary">
            <div>
              <TonePill tone={activeProfile ? 'good' : 'neutral'}>
                {activeProfile?.name || 'Profile unavailable'}
              </TonePill>
              <p className="ops-note">
                LightGBM is {mlStatus?.lgbm?.ready ? 'ready' : 'not ready'} with {number(mlStatus?.lgbm?.features)} tracked
                features. Technical, fundamental, and sentiment packs route through the deterministic policy gate.
              </p>
            </div>
            <div className="ops-inline-chips">
              <span className="ops-chip">
                Fundamentals {activeProfile?.require_fundamentals ? 'required' : 'optional'}
              </span>
              <span className="ops-chip">
                Sentiment {activeProfile?.require_sentiment ? 'required' : 'optional'}
              </span>
            </div>
          </div>

          <div className="ops-weight-list">
            {[
              ['Technical pack', packWeights.technical],
              ['Fundamental pack', packWeights.fundamental],
              ['Sentiment pack', packWeights.sentiment],
            ].map(([label, value]) => (
              <div key={label} className="ops-weight-row">
                <div className="ops-weight-copy">
                  <span>{label}</span>
                  <strong>{ratioPercent(value)}</strong>
                </div>
                <div className="ops-weight-bar">
                  <span className="ops-weight-fill" style={{ width: ratioPercent(value) }} />
                </div>
              </div>
            ))}
          </div>

          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Min confidence</span>
              <strong className="ops-kv-value">{ratioPercent(activeProfile?.min_confidence)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Min expected utility</span>
              <strong className="ops-kv-value">{ratioPercent(activeProfile?.min_expected_utility)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Max uncertainty</span>
              <strong className="ops-kv-value">{ratioPercent(activeProfile?.max_aggregate_uncertainty)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Volatility multiplier</span>
              <strong className="ops-kv-value">{Number(activeProfile?.volatility_multiplier || 0).toFixed(2)}x</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Sentiment freshness</span>
              <strong className="ops-kv-value">{number(activeProfile?.max_sentiment_age_minutes)}m</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Fundamental freshness</span>
              <strong className="ops-kv-value">{number(activeProfile?.max_fundamentals_age_hours)}h</strong>
            </div>
          </div>
        </Panel>
      </div>

      <div className="ops-grid ops-grid-overview-bottom">
        <Panel
          eyebrow="Candidate Board"
          title="Latest Trade Candidates"
          description="Derived directly from `data-pipeline/status` quality buckets. This replaces empty discovery theater."
        >
          {tradeCandidates.length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Category</th>
                    <th>Model score</th>
                    <th>Text events</th>
                    <th>Price integrity</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeCandidates.slice(0, 8).map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">{row.symbol}</td>
                      <td>{titleize(row.category)}</td>
                      <td>
                        <div className="ops-score-cell">
                          <span>{ratioPercent(row.score, 1)}</span>
                          <div className="ops-scorebar">
                            <span className="ops-scorebar-fill" style={{ width: ratioPercent(row.score) }} />
                          </div>
                        </div>
                      </td>
                      <td>{number(row.textEvents)}</td>
                      <td>{ratioPercent(row.priceScore)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">No trade candidates are currently being published by the pipeline.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Book Context"
          title="Live Book Snapshot"
          description="Current paper holdings, strongest and weakest names, and benchmark drift from the same backend snapshot."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Cash</span>
              <strong className="ops-kv-value">{currency(latestSnapshot?.cash)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Market value</span>
              <strong className="ops-kv-value">{currency(latestSnapshot?.market_value)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Strongest name</span>
              <strong className="ops-kv-value">
                {strongestPosition ? `${strongestPosition.symbol} · ${currency(strongestPosition.unrealizedPnl)}` : 'n/a'}
              </strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Weakest name</span>
              <strong className="ops-kv-value">
                {weakestPosition ? `${weakestPosition.symbol} · ${currency(weakestPosition.unrealizedPnl)}` : 'n/a'}
              </strong>
            </div>
          </div>

          {positions.length ? (
            <div className="ops-mini-list">
              {positions.slice(0, 5).map((row) => (
                <div key={row.symbol} className="ops-mini-row">
                  <div>
                    <strong>{row.symbol}</strong>
                    <small>{number(row.quantity)} sh</small>
                  </div>
                  <div className="ops-mini-value">
                    <strong>{currency(row.marketValue)}</strong>
                    <small className={Number(row.unrealizedPnl || 0) >= 0 ? 'ops-positive' : 'ops-negative'}>
                      {signedPlainPercent(row.returnPct, 2)}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No paper positions are currently open.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderPipeline = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Runtime"
          title="Pipeline Status"
          description="Grounded in the live scheduler and latest completed run."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Scheduler</span>
              <strong className="ops-kv-value">{pipelineStatus?.running ? 'Running' : 'Idle'}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Universe</span>
              <strong className="ops-kv-value">{number(safeArray(pipelineStatus?.configured_symbols).length)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Prices</span>
              <strong className="ops-kv-value">{number(latestRun?.counts?.prices)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Features</span>
              <strong className="ops-kv-value">{number(latestRun?.counts?.features)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Text events</span>
              <strong className="ops-kv-value">{number(latestRun?.counts?.text_events)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Fundamentals refresh</span>
              <strong className="ops-kv-value">{number(latestRun?.counts?.fundamentals)}</strong>
            </div>
          </div>

          <div className="ops-inline-chips">
            {Object.entries(candidateBuckets).map(([key, value]) => (
              <span key={key} className="ops-chip">
                {titleize(key)} {number(value)}
              </span>
            ))}
          </div>

          <p className="ops-note">
            Warehouse flow: {latestRun?.metadata?.flow || 'unknown'} · {latestRun?.metadata?.warehouse || 'unknown'}
          </p>
        </Panel>

        <Panel
          eyebrow="Profile"
          title="Model Pack Contract"
          description="The deterministic layer the UI is designed around."
        >
          <div className="ops-weight-list">
            {[
              ['Technical pack', packWeights.technical],
              ['Fundamental pack', packWeights.fundamental],
              ['Sentiment pack', packWeights.sentiment],
            ].map(([label, value]) => (
              <div key={label} className="ops-weight-row">
                <div className="ops-weight-copy">
                  <span>{label}</span>
                  <strong>{ratioPercent(value)}</strong>
                </div>
                <div className="ops-weight-bar">
                  <span className="ops-weight-fill" style={{ width: ratioPercent(value) }} />
                </div>
              </div>
            ))}
          </div>

          <div className="ops-kv-grid ops-kv-grid-tight">
            <div className="ops-kv">
              <span className="ops-kv-label">LGBM model</span>
              <strong className="ops-kv-value">{mlStatus?.lgbm?.ready ? 'Ready' : 'Unavailable'}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Feature count</span>
              <strong className="ops-kv-value">{number(mlStatus?.lgbm?.features)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Sentiment policy</span>
              <strong className="ops-kv-value">{activeProfile?.require_sentiment ? 'Required' : 'Optional'}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Fundamental policy</span>
              <strong className="ops-kv-value">{activeProfile?.require_fundamentals ? 'Required' : 'Optional'}</strong>
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        eyebrow="Signal Board"
        title="Pipeline Candidate Table"
        description="Everything here is sourced from the latest pipeline quality payload. No empty approval queues, no decorative swarm trees."
      >
        {candidateRows.length ? (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Bucket</th>
                  <th>Score</th>
                  <th>Text events</th>
                  <th>Bars</th>
                  <th>Fundamentals</th>
                  <th>Price flags</th>
                </tr>
              </thead>
              <tbody>
                {candidateRows.map((row) => (
                  <tr key={row.symbol}>
                    <td className="ops-symbol-cell">{row.symbol}</td>
                    <td>{titleize(row.category)}</td>
                    <td>
                      <div className="ops-score-cell">
                        <span>{ratioPercent(row.score, 1)}</span>
                        <div className="ops-scorebar">
                          <span className="ops-scorebar-fill" style={{ width: ratioPercent(row.score) }} />
                        </div>
                      </div>
                    </td>
                    <td>
                      {number(row.textEvents)} <small className="ops-inline-note">{ratioPercent(row.textScore)}</small>
                    </td>
                    <td>{titleize(row.barsStatus)}</td>
                    <td>{titleize(row.fundamentalsStatus)}</td>
                    <td>{row.priceFlags.length ? row.priceFlags.join(', ') : 'Clear'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="ops-empty">No pipeline quality rows are available yet.</div>
        )}
      </Panel>

      <div className="ops-grid ops-grid-overview-bottom">
        <Panel
          eyebrow="Providers"
          title="Source Posture"
          description="The current data-source truth, including fallback usage."
        >
          {safeArray(systemStatus?.data_source?.providers).length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Mode</th>
                    <th>Last event</th>
                    <th>Symbol</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {safeArray(systemStatus?.data_source?.providers).map((provider) => (
                    <tr key={`${provider.provider}-${provider.symbol || 'none'}`}>
                      <td>{provider.provider}</td>
                      <td>
                        <TonePill tone={statusTone(provider.mode)}>{titleize(provider.mode)}</TonePill>
                      </td>
                      <td>{formatRelative(provider.last_at)}</td>
                      <td>{provider.symbol || 'n/a'}</td>
                      <td>{provider.detail || 'n/a'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">Provider posture has not been published yet.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Streams"
          title="Market and News Feed State"
          description="Explicit stream posture and storage guidance from the backend."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Market stream</span>
              <strong className="ops-kv-value">{pipelineStatus?.stream?.subscribed ? 'Subscribed' : 'Idle'}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Feed</span>
              <strong className="ops-kv-value">{String(pipelineStatus?.stream?.feed || 'n/a').toUpperCase()}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">News stream</span>
              <strong className="ops-kv-value">{pipelineStatus?.news_stream?.started ? 'Running' : 'Parked'}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Health rows</span>
              <strong className="ops-kv-value">{number(safeArray(pipelineStatus?.provider_health).length)}</strong>
            </div>
          </div>

          <p className="ops-note">{providerNotice(pipelineStatus?.news_stream?.disable_reason)}</p>
          <p className="ops-note">{summarize(pipelineStatus?.storage_guidance?.recommendation, 260)}</p>
        </Panel>
      </div>
    </>
  );

  const renderPortfolio = () => (
    <>
      <div className="ops-metric-grid ops-metric-grid-portfolio">
        <MetricTile
          icon={LineChart}
          label="Cash"
          value={currency(latestSnapshot?.cash)}
          detail={`Broker mode ${latestSnapshot?.broker_mode || 'paper'}`}
          tone="neutral"
        />
        <MetricTile
          icon={Activity}
          label="Market Value"
          value={currency(latestSnapshot?.market_value)}
          detail={`${positions.length} active holdings`}
          tone="good"
        />
        <MetricTile
          icon={TrendingUp}
          label="Total P&L"
          value={currency(latestSnapshot?.total_pnl)}
          detail={`${latestSnapshot?.total_trades || 0} total trades`}
          tone={Number(latestSnapshot?.total_pnl || 0) >= 0 ? 'good' : 'bad'}
        />
        <MetricTile
          icon={Shield}
          label="Alpha vs SPY"
          value={signedPlainPercent(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct, 2)}
          detail={`SPY return ${plainPercent(performanceSummary?.track_record?.primary_benchmark_return_pct, 2)}`}
          tone={Number(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct || 0) >= 0 ? 'good' : 'caution'}
        />
      </div>

      <div className="ops-grid ops-grid-portfolio">
        <Panel
          eyebrow="Positions"
          title="Paper Book"
          description="A compact position sheet tied directly to `/paper/positions`."
        >
          {positions.length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Avg price</th>
                    <th>Market</th>
                    <th>Value</th>
                    <th>Unrealized P&L</th>
                    <th>Return</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">{row.symbol}</td>
                      <td>{number(row.quantity)}</td>
                      <td>{currency(row.avgPrice)}</td>
                      <td>{currency(row.marketPrice)}</td>
                      <td>{currency(row.marketValue)}</td>
                      <td className={row.unrealizedPnl >= 0 ? 'ops-positive' : 'ops-negative'}>
                        {currency(row.unrealizedPnl)}
                      </td>
                      <td className={row.returnPct >= 0 ? 'ops-positive' : 'ops-negative'}>
                        {signedPlainPercent(row.returnPct, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">The paper executor is currently flat.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Allocation"
          title="Capital Usage"
          description="Asset-class weights and current deployed usage from the active allocation policy."
        >
          {allocationRows.length ? (
            <div className="ops-allocation-list">
              {allocationRows.map((row) => (
                <div key={row.assetClass} className="ops-allocation-row">
                  <div className="ops-allocation-head">
                    <div>
                      <strong>{titleize(row.assetClass)}</strong>
                      <small>
                        Weight {ratioPercent(row.weight)} · Allocated {currency(row.allocatedUsd)}
                      </small>
                    </div>
                    <div className="ops-allocation-values">
                      <strong>{currency(row.usedUsd)}</strong>
                      <small>{ratioPercent(row.utilization)}</small>
                    </div>
                  </div>
                  <div className="ops-allocation-meter">
                    <span className="ops-allocation-fill" style={{ width: ratioPercent(row.utilization) }} />
                  </div>
                  <div className="ops-allocation-foot">
                    <span>Remaining {currency(row.remainingUsd)}</span>
                    <span>Live exposure {currency(row.liveExposureUsd)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Allocation policy rows are not available.</div>
          )}
        </Panel>
      </div>

      <div className="ops-grid ops-grid-overview-bottom">
        <Panel
          eyebrow="Benchmarks"
          title="Reference Returns"
          description="Latest benchmark baselines captured alongside the paper book."
        >
          {safeArray(latestSnapshot?.benchmarks).length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Price</th>
                    <th>Baseline</th>
                    <th>Return</th>
                  </tr>
                </thead>
                <tbody>
                  {safeArray(latestSnapshot?.benchmarks).map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">{row.symbol}</td>
                      <td>{currency(row.price)}</td>
                      <td>{currency(row.baseline_price)}</td>
                      <td className={Number(row.return_pct || 0) >= 0 ? 'ops-positive' : 'ops-negative'}>
                        {signedPlainPercent(row.return_pct, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">Benchmark snapshots are not available.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Contributors"
          title="Position Contribution"
          description="PnL contribution ordered by the live position sheet."
        >
          {positions.length ? (
            <div className="ops-mini-list">
              {positions.map((row) => (
                <div key={row.symbol} className="ops-mini-row">
                  <div>
                    <strong>{row.symbol}</strong>
                    <small>{currency(row.marketValue)}</small>
                  </div>
                  <div className="ops-mini-value">
                    <strong className={row.unrealizedPnl >= 0 ? 'ops-positive' : 'ops-negative'}>
                      {currency(row.unrealizedPnl)}
                    </strong>
                    <small>{signedPlainPercent(row.returnPct, 2)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No live positions to rank.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderMarket = () => (
    <>
      <Panel
        eyebrow="Tape"
        title="Snapshot Board"
        description="Fast, text-first market context without embedded widgets."
      >
        {safeArray(marketWatch?.ticker_snapshots).length ? (
          <div className="ops-ticker-grid">
            {safeArray(marketWatch?.ticker_snapshots).map((row) => (
              <article key={row.symbol} className="ops-ticker-card">
                <div className="ops-ticker-head">
                  <strong>{row.symbol}</strong>
                  <span>{row.name || row.symbol}</span>
                </div>
                <div className="ops-ticker-price">{currency(row.price)}</div>
                <div className={`ops-ticker-delta ${Number(row.change || 0) >= 0 ? 'ops-positive' : 'ops-negative'}`}>
                  {signedPlainPercent(row.change_pct, 2)} · {currency(row.change)}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="ops-empty">Market snapshots are not loaded.</div>
        )}
      </Panel>

      <div className="ops-grid ops-grid-market">
        <Panel
          eyebrow="News"
          title="Headline Feed"
          description="Current market-watch headlines published by the backend."
        >
          {safeArray(marketWatch?.news).length ? (
            <div className="ops-headline-list">
              {safeArray(marketWatch?.news).slice(0, 16).map((row, index) => (
                <article key={`${row.symbol}-${row.published_at}-${index}`} className="ops-headline-row">
                  <div className="ops-headline-tags">
                    <span className="ops-chip">{row.symbol || 'Market'}</span>
                    <span className="ops-chip">{row.source || 'Source'}</span>
                    <span className="ops-chip">{formatRelative(row.published_at)}</span>
                  </div>
                  {row.url ? (
                    <a className="ops-headline-link" href={row.url} target="_blank" rel="noreferrer">
                      {row.headline}
                    </a>
                  ) : (
                    <p className="ops-headline-link is-static">{row.headline}</p>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No headlines are currently attached to the market watch feed.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Coverage"
          title="Universe Map"
          description="The symbols the live backend is monitoring and the names currently held in the paper book."
        >
          <div className="ops-universe-section">
            <span className="ops-universe-label">Portfolio symbols</span>
            <div className="ops-inline-chips">
              {safeArray(marketWatch?.portfolio_symbols).length ? (
                safeArray(marketWatch?.portfolio_symbols).map((symbol) => (
                  <span key={`portfolio-${symbol}`} className="ops-chip">
                    {symbol}
                  </span>
                ))
              ) : (
                <span className="ops-chip">No live holdings</span>
              )}
            </div>
          </div>

          <div className="ops-universe-section">
            <span className="ops-universe-label">Coverage universe</span>
            <div className="ops-inline-chips">
              {safeArray(pipelineStatus?.configured_symbols).map((symbol) => (
                <span key={`coverage-${symbol}`} className="ops-chip">
                  {symbol}
                </span>
              ))}
            </div>
          </div>

          <div className="ops-universe-section">
            <span className="ops-universe-label">Trade candidate focus</span>
            <div className="ops-inline-chips">
              {tradeCandidates.length ? (
                tradeCandidates.slice(0, 10).map((row) => (
                  <span key={`candidate-${row.symbol}`} className="ops-chip">
                    {row.symbol} {ratioPercent(row.score, 0)}
                  </span>
                ))
              ) : (
                <span className="ops-chip">No current candidates</span>
              )}
            </div>
          </div>
        </Panel>
      </div>
    </>
  );

  const renderControls = () => {
    const policy = systemStatus?.allocation_policy?.policy;
    const constraints = policy?.constraints || {};

    return (
      <>
        <div className="ops-grid ops-grid-overview">
          <Panel
            eyebrow="Runtime"
            title="Control Surface"
            description="Operational actions aligned with the current backend contract."
            actions={
              <button
                type="button"
                className="ops-button secondary"
                disabled={refreshing}
                onClick={() => fetchAdminState({ manual: true })}
              >
                <RefreshCw size={15} className={refreshing ? 'ops-spin' : ''} />
                Refresh
              </button>
            }
          >
            <div className="ops-kv-grid">
              <div className="ops-kv">
                <span className="ops-kv-label">Runtime</span>
                <strong className="ops-kv-value">{runtimeControl?.runtime_started ? 'Running' : 'Paused'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Autopilot</span>
                <strong className="ops-kv-value">{runtimeControl?.autopilot?.enabled ? 'Enabled' : 'Disabled'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Strict real data</span>
                <strong className="ops-kv-value">{runtimeControl?.strict_real_data_only ? 'On' : 'Off'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">System halt</span>
                <strong className="ops-kv-value">{systemStatus?.halt?.halted ? 'Active' : 'Clear'}</strong>
              </div>
            </div>

            <div className="ops-button-row">
              <button
                type="button"
                className="ops-button"
                disabled={busyAction === 'resume' || runtimeControl?.runtime_started}
                onClick={() => handleRuntimeAction('resume')}
              >
                <Play size={15} />
                Resume runtime
              </button>
              <button
                type="button"
                className="ops-button secondary"
                disabled={busyAction === 'pause' || !runtimeControl?.runtime_started}
                onClick={() => handleRuntimeAction('pause')}
              >
                <Pause size={15} />
                Pause runtime
              </button>
              <button
                type="button"
                className="ops-button secondary"
                disabled={busyAction === 'recover'}
                onClick={() => handleRuntimeAction('recover')}
              >
                <Workflow size={15} />
                Recover deterministic ML
              </button>
              <button
                type="button"
                className="ops-button secondary"
                disabled={busyAction === 'clear-halt' || !systemStatus?.halt?.halted}
                onClick={() => handleRuntimeAction('clear-halt')}
              >
                <Shield size={15} />
                Clear halt
              </button>
              <button
                type="button"
                className="ops-button secondary"
                disabled={busyAction === 'capture'}
                onClick={() => handleRuntimeAction('capture')}
              >
                <LineChart size={15} />
                Capture snapshot
              </button>
            </div>
          </Panel>

          <Panel
            eyebrow="Policy"
            title="Allocation Boundaries"
            description="The live policy envelope the runtime is expected to respect."
          >
            <div className="ops-kv-grid">
              <div className="ops-kv">
                <span className="ops-kv-label">Capital base</span>
                <strong className="ops-kv-value">{currency(policy?.total_capital_usd)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Reserve cash</span>
                <strong className="ops-kv-value">{currency(policy?.reserve_cash_usd)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Min cash reserve</span>
                <strong className="ops-kv-value">{ratioPercent(constraints?.min_cash_reserve_pct)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Max asset-class exposure</span>
                <strong className="ops-kv-value">{ratioPercent(constraints?.max_asset_class_exposure_pct)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Max single trade</span>
                <strong className="ops-kv-value">{ratioPercent(constraints?.max_single_trade_notional_pct)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Weekend trading</span>
                <strong className="ops-kv-value">{constraints?.weekend_trading_enabled ? 'Allowed' : 'Blocked'}</strong>
              </div>
            </div>

            <div className="ops-inline-chips">
              {safeArray(constraints?.allowed_asset_classes).map((assetClass) => (
                <span key={assetClass} className="ops-chip">
                  {titleize(assetClass)}
                </span>
              ))}
            </div>
          </Panel>
        </div>

        <div className="ops-grid ops-grid-overview-bottom">
          <Panel
            eyebrow="Recovery"
            title="Checklist"
            description="Published directly by the backend when deterministic recovery steps are required."
          >
            {recoveryChecklist.length ? (
              <ul className="ops-list">
                {recoveryChecklist.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <div className="ops-empty">No recovery checklist is currently active.</div>
            )}
          </Panel>

          <Panel
            eyebrow="Lineage"
            title="Knowledge and Support Layer"
            description="Canonical store posture, graph sync state, and the retained AI support layer."
          >
            <div className="ops-kv-grid">
              <div className="ops-kv">
                <span className="ops-kv-label">Canonical store</span>
                <strong className="ops-kv-value">{knowledgeStats?.canonical_store || 'n/a'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Projection</span>
                <strong className="ops-kv-value">{knowledgeStats?.projection_store || 'n/a'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Knowledge events</span>
                <strong className="ops-kv-value">{number(knowledgeStats?.event_count)}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Graph sync</span>
                <strong className="ops-kv-value">{knowledgeStats?.last_graphify_sync_status || 'n/a'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">AI adapter</span>
                <strong className="ops-kv-value">{workersStatus?.ai_role_adapter?.enabled ? 'Enabled' : 'Standby'}</strong>
              </div>
              <div className="ops-kv">
                <span className="ops-kv-label">Default model</span>
                <strong className="ops-kv-value">{workersStatus?.ai_role_adapter?.default_model || 'n/a'}</strong>
              </div>
            </div>

            <p className="ops-note">
              AI support stays visible, but the backend is explicit that it is off the deterministic trade path and available only for research, editorial, and knowledge workflows when enabled.
            </p>

            {supportRoleModels.length ? (
              <div className="ops-inline-chips">
                {supportRoleModels.map(([role, model]) => (
                  <span key={role} className="ops-chip">
                    {titleize(role)} · {model}
                  </span>
                ))}
              </div>
            ) : null}

            {topNamespaceRows.length ? (
              <div className="ops-mini-list">
                {topNamespaceRows.map((row) => (
                  <div key={row.key} className="ops-mini-row">
                    <div>
                      <strong>{titleize(row.key)}</strong>
                      <small>namespace</small>
                    </div>
                    <div className="ops-mini-value">
                      <strong>{number(row.count)}</strong>
                      <small>events</small>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>
        </div>
      </>
    );
  };

  return (
    <div className="ops-shell">
      <aside className="ops-sidebar">
        <div className="ops-sidebar-top">
          <div className="ops-brand">
            <div className="ops-brand-mark">
              <Sigma size={18} />
            </div>
            <div className="ops-brand-copy">
              <strong>Vektor Admin</strong>
              <small>Deterministic fund console</small>
            </div>
          </div>

          <div className="ops-sidebar-summary">
            <div className="ops-sidebar-summary-row">
              <span>Backend</span>
              <strong>{backendTarget}</strong>
            </div>
            <div className="ops-sidebar-summary-row">
              <span>Last sync</span>
              <strong>{lastUpdate ? formatRelative(lastUpdate) : 'pending'}</strong>
            </div>
            <div className="ops-sidebar-summary-row">
              <span>Profile</span>
              <strong>{activeProfile?.name || 'n/a'}</strong>
            </div>
            <div className="ops-sidebar-summary-row">
              <span>Universe</span>
              <strong>{number(safeArray(pipelineStatus?.configured_symbols).length)}</strong>
            </div>
          </div>
        </div>

        <nav className="ops-nav" aria-label="Admin sections">
          {navigationItems.map((item) => (
            <NavItem key={item.id} item={item} active={activeTab === item.id} onSelect={setActiveTab} />
          ))}
        </nav>

        <div className="ops-sidebar-footer">
          <div className="ops-connection-row">
            <span className={`ops-connection-dot ${connectionStatus}`} />
            <span className="ops-connection-label">
              {connectionStatus === 'connected' ? 'Live backend' : connectionStatus === 'error' ? 'Backend unreachable' : 'Syncing'}
            </span>
          </div>
          <p className="ops-sidebar-note">
            AI is retained as a support layer only. Deterministic ML, policy gates, and paper execution are the surfaced trade path.
          </p>
        </div>
      </aside>

      <main className="ops-main">
        <header className="ops-header">
          <div className="ops-header-top">
            <div className="ops-header-copy">
              <p className="ops-header-eyebrow">Desktop operator surface</p>
              <h1>Current Backend State, No Theater</h1>
              <p className="ops-header-description">
                This surface is aligned to the live backend contract: pipeline quality, deterministic model routing, policy gates,
                paper positions, benchmark drift, and explicit support-layer status.
              </p>
            </div>
            <button
              type="button"
              className="ops-button"
              disabled={refreshing}
              onClick={() => fetchAdminState({ manual: true })}
            >
              <RefreshCw size={15} className={refreshing ? 'ops-spin' : ''} />
              Refresh
            </button>
          </div>

          <div className="ops-status-row">
            {headerBadges.map((badge) => (
              <div key={badge.label} className={`ops-status-badge ${toneClassName(badge.tone)}`}>
                <span className="ops-status-label">{badge.label}</span>
                <strong className="ops-status-value">{badge.value}</strong>
              </div>
            ))}
          </div>
        </header>

        <div className="ops-content">
          {initialLoading ? (
            <Panel
              eyebrow="Loading"
              title="Pulling live admin snapshot"
              description="The page will populate as soon as the backend responds."
            >
              <div className="ops-empty">Waiting for metrics, pipeline status, and paper-book data.</div>
            </Panel>
          ) : null}

          {connectionStatus === 'error' ? (
            <div className={`ops-banner ${toneClassName('bad')}`}>
              <AlertCircle size={16} />
              <div>
                <strong>Backend connectivity issue</strong>
                <p>The frontend is up, but the admin surface could not verify the live backend snapshot.</p>
              </div>
            </div>
          ) : null}

          {fallbackProvider ? (
            <div className={`ops-banner ${toneClassName('caution')}`}>
              <Database size={16} />
              <div>
                <strong>Fallback provider detected</strong>
                <p>
                  {fallbackProvider.provider} is currently supplementing {fallbackProvider.symbol || 'the universe'} with{' '}
                  {fallbackProvider.detail || 'fallback data'}. Keep deterministic autonomy constrained until provider posture is clean.
                </p>
              </div>
            </div>
          ) : null}

          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'pipeline' && renderPipeline()}
          {activeTab === 'portfolio' && renderPortfolio()}
          {activeTab === 'market' && renderMarket()}
          {activeTab === 'controls' && renderControls()}
        </div>

        <ToastContainer />
      </main>
    </div>
  );
}
