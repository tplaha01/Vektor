import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Bot,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
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
import '../styles/admin.css';
import '../styles/admin-portal.css';
import { adminAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ToastContainer from '../components/common/Toast';
import AgentMonitor from '../components/admin/AgentMonitor';
import DecisionQueue from '../components/admin/DecisionQueue';
import KnowledgeTraceGraph from '../components/admin/KnowledgeTraceGraph';
import LineagePanel from '../components/admin/LineagePanel';
import OverviewPanel from '../components/admin/OverviewPanel';
import PositionsPanel from '../components/admin/PositionsPanel';
import RiskGauges from '../components/admin/RiskGauges';
import SystemOverview from '../components/admin/SystemOverview';
import TradingViewWidget from '../components/TradingViewWidget';

const backendTarget = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const POLL_INTERVAL_MS = 20000;
const RETRY_INTERVAL_MS = 60000;
const SIDEBAR_STORAGE_KEY = 'vektor.admin.sidebarCollapsed';
const DESKTOP_MEDIA_QUERY = '(min-width: 1281px)';

const navigationItems = [
  {
    id: 'control',
    label: 'Control',
    icon: Sigma,
    description: 'Executive command deck',
  },
  {
    id: 'positions',
    label: 'Positions',
    icon: Activity,
    description: 'Portfolio and book detail',
  },
  {
    id: 'market',
    label: 'Market',
    icon: Globe,
    description: 'Focus charts and market feed',
  },
  {
    id: 'agents',
    label: 'Agents',
    icon: Bot,
    description: 'Workers, hierarchy, and task flow',
  },
  {
    id: 'risk',
    label: 'Risk',
    icon: Shield,
    description: 'Alerts, drawdown, and capital pressure',
  },
  {
    id: 'performance',
    label: 'Performance',
    icon: FileText,
    description: 'Track record and review trail',
  },
  {
    id: 'orders',
    label: 'Orders',
    icon: LineChart,
    description: 'Manual execution and book snapshot',
  },
  {
    id: 'decisions',
    label: 'Decisions',
    icon: TrendingUp,
    description: 'Approvals and blocked flow',
  },
  {
    id: 'runtime',
    label: 'Runtime',
    icon: Workflow,
    description: 'Workers, providers, and control logs',
  },
  {
    id: 'knowledge',
    label: 'Knowledge',
    icon: Database,
    description: 'Store state and run lineage',
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    description: 'Backend config and model routing',
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

const makeListKey = (parts, index) => {
  const key = parts
    .filter((part) => part !== null && part !== undefined && String(part).trim() !== '')
    .map((part) => String(part).trim())
    .join('-');
  return key ? `${key}-${index}` : `row-${index}`;
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

const compactDateTime = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
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

function NavItem({ active, collapsed, item, onSelect }) {
  const Icon = item.icon;

  return (
    <button
      type="button"
      className={`ops-nav-item ${active ? 'is-active' : ''}`}
      onClick={() => onSelect(item.id)}
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
    >
      <span className="ops-nav-icon">
        <Icon size={16} />
      </span>
      <span className="ops-nav-copy">
        <strong>{item.label}</strong>
        {item.description ? <small>{item.description}</small> : null}
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
  const [isDesktopViewport, setIsDesktopViewport] = useState(() =>
    typeof window === 'undefined' ? true : window.matchMedia(DESKTOP_MEDIA_QUERY).matches
  );
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;

    try {
      return (
        window.matchMedia(DESKTOP_MEDIA_QUERY).matches &&
        window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true'
      );
    } catch {
      return false;
    }
  });
  const [activeTab, setActiveTab] = useState('control');
  const [metrics, setMetrics] = useState(null);
  const [overviewData, setOverviewData] = useState({
    nav: null,
    monthlyPnl: null,
    sharpe: null,
    drawdown: null,
    runtime: null,
    exposure: null,
    risk: null,
    alerts: null,
  });
  const [systemStatus, setSystemStatus] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [mlStatus, setMlStatus] = useState(null);
  const [riskStatus, setRiskStatus] = useState(null);
  const [runtimeControl, setRuntimeControl] = useState(null);
  const [workersStatus, setWorkersStatus] = useState(null);
  const [performanceSummary, setPerformanceSummary] = useState(null);
  const [performanceSnapshots, setPerformanceSnapshots] = useState([]);
  const [paperPositions, setPaperPositions] = useState([]);
  const [ceoPositionsSummary, setCeoPositionsSummary] = useState(null);
  const [marketWatch, setMarketWatch] = useState(null);
  const [performanceBreakdown, setPerformanceBreakdown] = useState(null);
  const [mlEffectiveness, setMlEffectiveness] = useState(null);
  const [riskAlerts, setRiskAlerts] = useState([]);
  const [operatorCrm] = useState(null);
  const [controlHistory, setControlHistory] = useState([]);
  const [taskHistory, setTaskHistory] = useState([]);
  const [blockedTrades, setBlockedTrades] = useState([]);
  const [postTradeReviews, setPostTradeReviews] = useState([]);
  const [reportDeliverables] = useState([]);
  const [blogDeliverables] = useState([]);
  const [lineageRows] = useState([]);
  const [commandHelp] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [positionBrief, setPositionBrief] = useState(null);
  const [positionBriefLoading, setPositionBriefLoading] = useState(false);
  const [knowledgeStats, setKnowledgeStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [busyAction, setBusyAction] = useState('');
  const [orderForm, setOrderForm] = useState({
    symbol: 'AAPL',
    side: 'buy',
    quantity: '10',
  });
  const [capitalForm, setCapitalForm] = useState({
    amountUsd: '',
    targetCashUsd: '',
    clearPositions: false,
    clearOrders: false,
  });
  const [policyForm, setPolicyForm] = useState({
    totalCapitalUsd: '',
    reserveCashUsd: '',
    minCashReservePct: '',
    maxAssetClassExposurePct: '',
    maxSingleTradeNotionalPct: '',
    weekendTradingEnabled: false,
    allowedAssetClasses: '',
  });
  const [knowledgeForm, setKnowledgeForm] = useState({
    runId: '',
    agentId: 'ceo',
    seedEvent: true,
  });
  const [busyMutation, setBusyMutation] = useState('');
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const mediaQuery = window.matchMedia(DESKTOP_MEDIA_QUERY);
    const syncViewportState = (event) => {
      const matches = event.matches;
      setIsDesktopViewport(matches);

      if (!matches) {
        setIsSidebarCollapsed(false);
        return;
      }

      try {
        setIsSidebarCollapsed(window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true');
      } catch {
        setIsSidebarCollapsed(false);
      }
    };

    syncViewportState(mediaQuery);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', syncViewportState);
      return () => mediaQuery.removeEventListener('change', syncViewportState);
    }

    mediaQuery.addListener(syncViewportState);
    return () => mediaQuery.removeListener(syncViewportState);
  }, []);

  useEffect(() => {
    if (!isDesktopViewport || typeof window === 'undefined') return;

    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isSidebarCollapsed));
    } catch {
      // Ignore localStorage failures; the UI still works without persistence.
    }
  }, [isDesktopViewport, isSidebarCollapsed]);

  const fetchAdminState = useCallback(
    async ({ manual = false } = {}) => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;
      if (manual) setRefreshing(true);

      try {
        setConnectionStatus((previous) => (previous === 'connected' ? 'connected' : 'connecting'));

        const results = await Promise.allSettled([
          adminAPI.getMetricsSummary(),
          adminAPI.getOverviewNav(),
          adminAPI.getOverviewMonthlyPnl(),
          adminAPI.getOverviewSharpe(),
          adminAPI.getOverviewDrawdown(),
          adminAPI.getOverviewRuntimeStatus(),
          adminAPI.getOverviewPortfolioExposure(),
          adminAPI.getOverviewRiskStatus(),
          adminAPI.getOverviewPendingAlerts(),
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
          adminAPI.getCeoRiskAlerts(),
          adminAPI.getCeoPerformanceBreakdown(),
          adminAPI.getCeoMlEffectiveness(),
          adminAPI.getRuntimeControlHistory(10),
          adminAPI.getFundTaskHistory(12),
          adminAPI.getFundBlockedTrades(12),
          adminAPI.getCeoPositions(),
          adminAPI.getLatestPostTradeReviews(8),
        ]);

        if (!isMounted.current) return;

        const coreResults = [results[0], results[9], results[10], results[15], results[17], results[18]];
        if (coreResults.every((result) => result.status === 'rejected')) {
          throw new Error(String(coreResults[0]?.reason?.message || 'backend_unreachable'));
        }

        const [
          metricsResult,
          overviewNavResult,
          overviewMonthlyPnlResult,
          overviewSharpeResult,
          overviewDrawdownResult,
          overviewRuntimeResult,
          overviewExposureResult,
          overviewRiskResult,
          overviewAlertsResult,
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
          riskAlertsResult,
          performanceBreakdownResult,
          mlEffectivenessResult,
          controlHistoryResult,
          taskHistoryResult,
          blockedTradesResult,
          ceoPositionsResult,
          postTradeReviewsResult,
        ] = results;

        if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value);
        setOverviewData((previous) => ({
          ...previous,
          nav: overviewNavResult.status === 'fulfilled' ? overviewNavResult.value : previous.nav,
          monthlyPnl: overviewMonthlyPnlResult.status === 'fulfilled' ? overviewMonthlyPnlResult.value : previous.monthlyPnl,
          sharpe: overviewSharpeResult.status === 'fulfilled' ? overviewSharpeResult.value : previous.sharpe,
          drawdown: overviewDrawdownResult.status === 'fulfilled' ? overviewDrawdownResult.value : previous.drawdown,
          runtime: overviewRuntimeResult.status === 'fulfilled' ? overviewRuntimeResult.value : previous.runtime,
          exposure: overviewExposureResult.status === 'fulfilled' ? overviewExposureResult.value : previous.exposure,
          risk: overviewRiskResult.status === 'fulfilled' ? overviewRiskResult.value : previous.risk,
          alerts: overviewAlertsResult.status === 'fulfilled' ? overviewAlertsResult.value : previous.alerts,
        }));
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
        if (riskAlertsResult.status === 'fulfilled') {
          setRiskAlerts(adminAPI.normalizeArray(riskAlertsResult.value, 'alerts'));
        }
        if (performanceBreakdownResult.status === 'fulfilled') {
          setPerformanceBreakdown(performanceBreakdownResult.value);
        }
        if (mlEffectivenessResult.status === 'fulfilled') {
          setMlEffectiveness(mlEffectivenessResult.value);
        }
        if (controlHistoryResult.status === 'fulfilled') {
          setControlHistory(adminAPI.normalizeArray(controlHistoryResult.value, 'rows'));
        }
        if (taskHistoryResult.status === 'fulfilled') {
          setTaskHistory(adminAPI.normalizeArray(taskHistoryResult.value, 'rows'));
        }
        if (blockedTradesResult.status === 'fulfilled') {
          setBlockedTrades(adminAPI.normalizeArray(blockedTradesResult.value, 'rows'));
        }
        if (ceoPositionsResult.status === 'fulfilled') {
          setCeoPositionsSummary(ceoPositionsResult.value);
        }
        if (postTradeReviewsResult.status === 'fulfilled') {
          setPostTradeReviews(adminAPI.normalizeArray(postTradeReviewsResult.value, 'items'));
        }

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

  const activeProfile = useMemo(() => {
    const profiles = safeArray(mlStatus?.core_engine?.available_profiles);
    return profiles.find((profile) => profile?.name === mlStatus?.core_engine?.active_profile) || null;
  }, [mlStatus]);

  const packWeights = activeProfile?.stack_weights || {};
  const latestRun = pipelineStatus?.last_run || null;
  const latestSnapshot = performanceSummary?.latest_snapshot || null;

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
          case 'kick':
            await adminAPI.kickAutopilot();
            success('Autopilot kick requested');
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

  const handleOrderSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      const symbol = String(orderForm.symbol || '').trim().toUpperCase();
      const quantity = Number(orderForm.quantity || 0);

      if (!symbol || quantity <= 0) {
        showError('Enter a symbol and quantity.');
        return;
      }

      try {
        setBusyMutation('order');
        const result = await adminAPI.placePaperOrder({
          symbol,
          side: orderForm.side,
          quantity,
        });

        if (result?.approved === false) {
          showError(`${symbol} blocked: ${safeArray(result?.reasons).join(', ') || result?.error || 'policy_gate_blocked'}`);
        } else {
          success(`${symbol} ${String(orderForm.side).toUpperCase()} submitted`);
        }

        fetchAdminState();
      } catch (err) {
        showError(`Order failed: ${err.message}`);
      } finally {
        setBusyMutation('');
      }
    },
    [fetchAdminState, orderForm, showError, success]
  );

  const handleCapitalSubmit = useCallback(
    async (event) => {
      event.preventDefault();

      try {
        setBusyMutation('capital');
        await adminAPI.updatePaperBrokerCapital({
          amountUsd: capitalForm.amountUsd === '' ? null : Number(capitalForm.amountUsd),
          targetCashUsd: capitalForm.targetCashUsd === '' ? null : Number(capitalForm.targetCashUsd),
          clearPositions: capitalForm.clearPositions,
          clearOrders: capitalForm.clearOrders,
          reason: 'admin_control_center_capital_update',
        });
        success('Paper broker capital updated');
        fetchAdminState();
      } catch (err) {
        showError(`Capital update failed: ${err.message}`);
      } finally {
        setBusyMutation('');
      }
    },
    [capitalForm, fetchAdminState, showError, success]
  );

  const handlePolicySubmit = useCallback(
    async (event) => {
      event.preventDefault();
      const currentPolicy = systemStatus?.allocation_policy?.policy || {};
      const currentConstraints = currentPolicy?.constraints || {};

      try {
        setBusyMutation('policy');
        await adminAPI.updateAllocationPolicy({
          run_id: currentPolicy?.run_id || latestRun?.run_id || 'admin-live',
          agent_id: currentPolicy?.agent_id || 'ceo',
          total_capital_usd: Number(policyForm.totalCapitalUsd || currentPolicy?.total_capital_usd || 0),
          reserve_cash_usd: Number(policyForm.reserveCashUsd || currentPolicy?.reserve_cash_usd || 0),
          asset_weights: currentPolicy?.asset_weights || {},
          sleeve_weights: currentPolicy?.sleeve_weights || {},
          constraints: {
            ...currentConstraints,
            min_cash_reserve_pct: Number(policyForm.minCashReservePct || currentConstraints?.min_cash_reserve_pct || 0),
            max_asset_class_exposure_pct: Number(
              policyForm.maxAssetClassExposurePct || currentConstraints?.max_asset_class_exposure_pct || 0
            ),
            max_single_trade_notional_pct: Number(
              policyForm.maxSingleTradeNotionalPct || currentConstraints?.max_single_trade_notional_pct || 0
            ),
            weekend_trading_enabled: Boolean(policyForm.weekendTradingEnabled),
            allowed_asset_classes: policyForm.allowedAssetClasses
              .split(',')
              .map((value) => value.trim().toLowerCase())
              .filter(Boolean),
          },
          metadata: {
            ...(currentPolicy?.metadata || {}),
            updated_from: 'admin_control_center',
          },
        });
        success('Allocation policy updated');
        fetchAdminState();
      } catch (err) {
        showError(`Policy update failed: ${err.message}`);
      } finally {
        setBusyMutation('');
      }
    },
    [fetchAdminState, latestRun, policyForm, showError, success, systemStatus]
  );

  const handleKnowledgeSubmit = useCallback(
    async (action) => {
      try {
        setBusyMutation(action);
        const payload = {
          run_id: knowledgeForm.runId || null,
          agent_id: knowledgeForm.agentId || 'ceo',
          seed_event: knowledgeForm.seedEvent,
        };

        if (action === 'knowledge-reset') {
          await adminAPI.resetKnowledgeBase(payload);
          success('Knowledge store reset');
        } else {
          await adminAPI.rebuildKnowledgeProjection(payload);
          success('Knowledge projection rebuild requested');
        }

        fetchAdminState();
      } catch (err) {
        showError(`Knowledge action failed: ${err.message}`);
      } finally {
        setBusyMutation('');
      }
    },
    [fetchAdminState, knowledgeForm, showError, success]
  );

  const handleInceptionReset = useCallback(async () => {
    try {
      setBusyMutation('inception-reset');
      await adminAPI.resetCleanInception({
        startingCashUsd: Number(policyForm.totalCapitalUsd || 100000),
        reason: 'admin_control_center_clean_reset',
      });
      success('Clean inception reset requested');
      fetchAdminState();
    } catch (err) {
      showError(`Reset failed: ${err.message}`);
    } finally {
      setBusyMutation('');
    }
  }, [fetchAdminState, policyForm.totalCapitalUsd, showError, success]);

  const copyCommand = useCallback(
    async (value) => {
      try {
        await navigator.clipboard.writeText(value);
        success('Command copied to clipboard');
      } catch (err) {
        showError(`Copy failed: ${err.message}`);
      }
    },
    [showError, success]
  );

  useEffect(() => {
    const policy = systemStatus?.allocation_policy?.policy;
    const constraints = policy?.constraints || {};
    if (!policy) return;

    setPolicyForm({
      totalCapitalUsd: policy?.total_capital_usd != null ? String(policy.total_capital_usd) : '',
      reserveCashUsd: policy?.reserve_cash_usd != null ? String(policy.reserve_cash_usd) : '',
      minCashReservePct: constraints?.min_cash_reserve_pct != null ? String(constraints.min_cash_reserve_pct) : '',
      maxAssetClassExposurePct:
        constraints?.max_asset_class_exposure_pct != null ? String(constraints.max_asset_class_exposure_pct) : '',
      maxSingleTradeNotionalPct:
        constraints?.max_single_trade_notional_pct != null ? String(constraints.max_single_trade_notional_pct) : '',
      weekendTradingEnabled: Boolean(constraints?.weekend_trading_enabled),
      allowedAssetClasses: safeArray(constraints?.allowed_asset_classes).join(', '),
    });
  }, [systemStatus]);

  useEffect(() => {
    setCapitalForm((previous) => ({
      ...previous,
      targetCashUsd:
        previous.targetCashUsd || latestSnapshot?.cash == null
          ? previous.targetCashUsd
          : String(latestSnapshot.cash),
    }));
  }, [latestSnapshot]);

  useEffect(() => {
    setKnowledgeForm((previous) => ({
      ...previous,
      runId: previous.runId || latestRun?.run_id || '',
    }));
  }, [latestRun]);

  const ceoPositionMap = useMemo(
    () =>
      safeArray(ceoPositionsSummary?.positions).reduce((rows, row) => {
        if (row?.symbol) rows[row.symbol] = row;
        return rows;
      }, {}),
    [ceoPositionsSummary]
  );

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
          const ceoRow = ceoPositionMap[position.symbol] || {};

          return {
            ...position,
            quantity,
            avgPrice,
            marketPrice,
            marketValue,
            unrealizedPnl,
            returnPct,
            thesisState: ceoRow.thesis_state || 'unknown',
            reviewStatus: ceoRow.review_status || 'unknown',
            riskFlags: safeArray(ceoRow.risk_flags),
            assetClass: ceoRow.asset_class || position.asset_class || 'equities',
            allocationPct: Number(ceoRow.allocation_pct || 0),
          };
        })
        .sort((left, right) => right.unrealizedPnl - left.unrealizedPnl),
    [ceoPositionMap, paperPositions]
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

  useEffect(() => {
    const symbols = positions.map((row) => row.symbol);

    if (!symbols.length) {
      setSelectedSymbol('');
      setPositionBrief(null);
      return;
    }

    if (!selectedSymbol || !symbols.includes(selectedSymbol)) {
      setSelectedSymbol(symbols[0]);
    }
  }, [positions, selectedSymbol]);

  useEffect(() => {
    let active = true;

    if (!selectedSymbol) {
      setPositionBrief(null);
      setPositionBriefLoading(false);
      return undefined;
    }

    setPositionBriefLoading(true);
    adminAPI
      .getCeoPositionBrief(selectedSymbol)
      .then((value) => {
        if (active) setPositionBrief(value);
      })
      .catch((err) => {
        console.error('Failed to load position brief:', err);
        if (active) setPositionBrief(null);
      })
      .finally(() => {
        if (active) setPositionBriefLoading(false);
      });

    return () => {
      active = false;
    };
  }, [lastUpdate, selectedSymbol]);

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
  const pipelineFailures = useMemo(
    () =>
      Object.entries(latestRun?.quality || {})
        .filter(([, row]) => String(row?.status || '').toLowerCase() === 'symbol_failed' || row?.error)
        .map(([symbol, row]) => ({
          symbol,
          error: row?.error || row?.status || 'symbol_failed',
        })),
    [latestRun]
  );
  const workerRows = safeArray(workersStatus?.workers);
  const taskHistoryRows = safeArray(taskHistory);
  const blockedDecisionRows = safeArray(blockedTrades);
  const performanceAreaRows = safeArray(performanceBreakdown?.areas);
  const mlCoverageRows = safeArray(mlEffectiveness?.positions_with_ml_context);
  const latestControlAction = controlHistory[0] || null;
  const latestTaskRow = taskHistoryRows[0] || null;
  const commandGroups = useMemo(
    () =>
      [
        { key: 'controls', label: 'Controls', items: safeArray(commandHelp?.controls).slice(0, 6) },
        { key: 'queries', label: 'CEO queries', items: safeArray(commandHelp?.ceo_queries).slice(0, 6) },
        { key: 'approvals', label: 'Approvals', items: safeArray(commandHelp?.approvals).slice(0, 5) },
      ].filter((group) => group.items.length),
    [commandHelp]
  );
  const priorityRows = useMemo(
    () => [
      {
        key: 'runtime',
        title: runtimeControl?.runtime_started ? 'Runtime is armed' : 'Runtime is paused',
        tone: runtimeControl?.runtime_started ? 'good' : 'caution',
        status: runtimeControl?.runtime_started ? 'Running' : 'Paused',
        detail: runtimeControl?.runtime_started
          ? `${number(runtimeControl?.active_task_count)} active tasks and autopilot ${
              runtimeControl?.autopilot?.enabled ? 'enabled' : 'disabled'
            }.`
          : `Resume runtime before issuing autopilot work for ${number(
              safeArray(runtimeControl?.autopilot?.symbols).length
            )} priority symbols.`,
      },
      {
        key: 'strict',
        title: runtimeControl?.strict_real_data_only ? 'Strict real-data policy is on' : 'Strict real-data policy is off',
        tone: runtimeControl?.strict_real_data_only ? 'good' : 'caution',
        status: runtimeControl?.strict_real_data_only ? 'Strict' : 'Relaxed',
        detail: runtimeControl?.strict_real_data_only
          ? 'Deterministic signals remain gated to live provider data only.'
          : 'Recovery flow disabled strict mode. Keep autonomy constrained until providers are fully clean.',
      },
      {
        key: 'pipeline',
        title: pipelineFailures.length ? 'Pipeline exceptions need review' : 'Pipeline quality is clear',
        tone: pipelineFailures.length ? 'bad' : 'good',
        status: pipelineFailures.length ? `${pipelineFailures.length} failed` : 'Clear',
        detail: pipelineFailures.length
          ? `${pipelineFailures.map((row) => row.symbol).join(', ')} - ${summarize(pipelineFailures[0]?.error, 120)}`
          : `Latest completed run ${formatRelative(latestRun?.finished_at)} across ${number(
              safeArray(pipelineStatus?.configured_symbols).length
            )} names.`,
      },
      {
        key: 'risk',
        title: riskAlerts.length ? 'CEO risk alerts are active' : systemStatus?.halt?.halted ? 'System halt is active' : 'Risk queue is clear',
        tone: riskAlerts.length || systemStatus?.halt?.halted ? 'bad' : 'good',
        status: riskAlerts.length ? `${riskAlerts.length} alerts` : systemStatus?.halt?.halted ? 'Halted' : 'Clear',
        detail: riskAlerts.length
          ? summarize(riskAlerts[0]?.message || JSON.stringify(riskAlerts[0] || {}), 140)
          : systemStatus?.halt?.halted
            ? summarize(systemStatus?.halt?.message || systemStatus?.halt?.reason, 140)
            : 'No blocked trades, drawdown breaker halts, or thesis degradation alerts are currently published.',
      },
      {
        key: 'memory',
        title: latestControlAction ? 'Recent control activity is available' : 'No recent control memory',
        tone: latestControlAction ? statusTone(latestControlAction?.status) : 'neutral',
        status: latestControlAction ? titleize(latestControlAction?.action) : 'Idle',
        detail: latestControlAction
          ? `${compactDateTime(latestControlAction?.timestamp)} - ${summarize(
              latestControlAction?.reason || latestControlAction?.payload?.reason,
              140
            )}`
          : latestTaskRow
            ? `${titleize(latestTaskRow?.role)} last moved ${formatRelative(latestTaskRow?.ts)}.`
            : 'Task and control history will appear here once operators or automations act.',
      },
    ],
    [latestControlAction, latestRun, latestTaskRow, pipelineFailures, pipelineStatus, riskAlerts, runtimeControl, systemStatus]
  );
  const quickActions = useMemo(
    () => [
      runtimeControl?.runtime_started
        ? { key: 'pause', label: 'Pause runtime', icon: Pause, disabled: busyAction === 'pause' }
        : { key: 'resume', label: 'Resume runtime', icon: Play, disabled: busyAction === 'resume' },
      { key: 'recover', label: 'Recover ML', icon: Workflow, disabled: busyAction === 'recover' },
      {
        key: 'kick',
        label: 'Kick autopilot',
        icon: Activity,
        disabled: busyAction === 'kick' || !runtimeControl?.runtime_started,
      },
      { key: 'capture', label: 'Capture snapshot', icon: LineChart, disabled: busyAction === 'capture' },
    ],
    [busyAction, runtimeControl]
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
  const focusChartSymbols = useMemo(
    () =>
      Array.from(
        new Set([
          ...positions.map((row) => row.symbol),
          ...tradeCandidates.map((row) => row.symbol),
          ...safeArray(pipelineStatus?.configured_symbols),
        ])
      )
        .filter(Boolean)
        .slice(0, 4),
    [pipelineStatus, positions, tradeCandidates]
  );

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

      <div className="ops-grid ops-grid-command-center">
        <Panel
          eyebrow="Operator queue"
          title="Immediate priorities"
          description="The backend truth that most affects whether the desk is safe to steer right now."
        >
          <div className="ops-priority-list">
            {priorityRows.map((row) => (
              <article key={row.key} className="ops-priority-card">
                <div className="ops-priority-head">
                  <div>
                    <strong>{row.title}</strong>
                    <small>{row.key === 'memory' ? 'Operator memory' : 'Live runtime signal'}</small>
                  </div>
                  <TonePill tone={row.tone}>{row.status}</TonePill>
                </div>
                <p>{row.detail}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel
          eyebrow="CEO command deck"
          title="Copyable control language"
          description="Published by the backend so the operator surface and command rail stay aligned."
        >
          {commandGroups.length ? (
            <div className="ops-command-groups">
              {commandGroups.map((group) => (
                <section key={group.key} className="ops-command-group">
                  <div className="ops-command-group-head">
                    <strong>{group.label}</strong>
                    <small>{number(group.items.length)} commands</small>
                  </div>
                  <div className="ops-command-chip-grid">
                    {group.items.map((command) => (
                      <button
                        key={command}
                        type="button"
                        className="ops-command-chip"
                        onClick={() => copyCommand(command)}
                      >
                        {command}
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Command help has not loaded yet.</div>
          )}
        </Panel>
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
          description="Click a symbol to pull the CEO brief, latest order lineage, and symbol-specific news."
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
                    <th>Risk flags</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">
                        <button
                          type="button"
                          className={`ops-table-button ${selectedSymbol === row.symbol ? 'is-active' : ''}`}
                          onClick={() => setSelectedSymbol(row.symbol)}
                        >
                          {row.symbol}
                        </button>
                        <small className="ops-table-subcopy">
                          {titleize(row.thesisState)} / {titleize(row.reviewStatus)}
                        </small>
                      </td>
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
                      <td>{row.riskFlags.length ? row.riskFlags.join(', ') : 'Clear'}</td>
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
          eyebrow="CEO brief"
          title={selectedSymbol ? `${selectedSymbol} spotlight` : 'Position spotlight'}
          description="Position context published by the backend, including recent orders and symbol-linked news."
        >
          {positionBriefLoading ? (
            <div className="ops-empty">Loading position brief for {selectedSymbol || 'the selected symbol'}.</div>
          ) : positionBrief?.position ? (
            <div className="ops-section-stack">
              <div className="ops-kv-grid">
                <div className="ops-kv">
                  <span className="ops-kv-label">Quantity</span>
                  <strong className="ops-kv-value">{number(positionBrief?.position?.quantity)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Average price</span>
                  <strong className="ops-kv-value">{currency(positionBrief?.position?.average_price)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Market price</span>
                  <strong className="ops-kv-value">{currency(positionBrief?.position?.market_price)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Unrealized P&L</span>
                  <strong className="ops-kv-value">{currency(positionBrief?.position?.unrealized_pnl)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Routing mode</span>
                  <strong className="ops-kv-value">{titleize(positionBrief?.position?.routing_mode)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Allocation share</span>
                  <strong className="ops-kv-value">{plainPercent(positionBrief?.position?.allocation_pct, 2)}</strong>
                </div>
              </div>

              <div className="ops-section-block">
                <span className="ops-universe-label">Recent orders</span>
                {safeArray(positionBrief?.recent_orders).length ? (
                  <div className="ops-mini-list">
                    {safeArray(positionBrief?.recent_orders)
                      .slice(0, 3)
                      .map((row) => (
                        <div key={`${row.id}-${row.created_at}`} className="ops-mini-row">
                          <div>
                            <strong>{titleize(row.side)} {number(row.qty)}</strong>
                            <small>{compactDateTime(row.created_at)}</small>
                          </div>
                          <div className="ops-mini-value">
                            <strong>{currency(row.avg_price)}</strong>
                            <small>{titleize(row.status)}</small>
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div className="ops-empty">No recent orders are attached to this symbol.</div>
                )}
              </div>

              <div className="ops-section-block">
                <span className="ops-universe-label">Recent news</span>
                {safeArray(positionBrief?.news).length ? (
                  <div className="ops-headline-list">
                    {safeArray(positionBrief?.news)
                      .slice(0, 4)
                      .map((row, index) => (
                        <article key={`${row.published_at}-${index}`} className="ops-headline-row">
                          <div className="ops-headline-tags">
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
                  <div className="ops-empty">No backend-linked headlines are attached to this position yet.</div>
                )}
              </div>
            </div>
          ) : (
            <div className="ops-empty">Select a live position to load the backend's CEO brief.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Performance context"
          title="Area breakdown and ML coverage"
          description="Portfolio-level context sourced from the CEO performance and post-trade review surfaces."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Total unrealized</span>
              <strong className="ops-kv-value">{currency(performanceBreakdown?.total_unrealized_pnl)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">ML context count</span>
              <strong className="ops-kv-value">{number(mlEffectiveness?.count)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Post-trade reviews</span>
              <strong className="ops-kv-value">{number(postTradeReviews.length)}</strong>
            </div>
          </div>

          {performanceAreaRows.length ? (
            <div className="ops-mini-list">
              {performanceAreaRows.map((row) => (
                <div key={row.asset_class} className="ops-mini-row">
                  <div>
                    <strong>{titleize(row.asset_class)}</strong>
                    <small>{number(row.count)} symbols</small>
                  </div>
                  <div className="ops-mini-value">
                    <strong>{currency(row.market_value)}</strong>
                    <small className={Number(row.unrealized_pnl || 0) >= 0 ? 'ops-positive' : 'ops-negative'}>
                      {currency(row.unrealized_pnl)}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Performance breakdown rows have not been published yet.</div>
          )}

          <p className="ops-note">{summarize(mlEffectiveness?.note, 220)}</p>

          {mlCoverageRows.length ? (
            <div className="ops-inline-chips">
              {mlCoverageRows.slice(0, 8).map((row) => (
                <span key={`${row.symbol}-${row.order_id || 'order'}`} className="ops-chip">
                  {row.symbol} {titleize(row.strategy_family || 'ml')}
                </span>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No open-position ML context is currently published.</div>
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

            <div className="ops-inline-chips">
              <span className="ops-chip">Interval {number(runtimeControl?.autopilot?.interval_seconds)}s</span>
              <span className="ops-chip">Universe {number(safeArray(runtimeControl?.autopilot?.scout_symbols).length)}</span>
              <span className="ops-chip">Wave size {number(runtimeControl?.autopilot?.swarm_wave_size)}</span>
              <span className="ops-chip">Sleeve {titleize(runtimeControl?.autopilot?.sleeve)}</span>
              <span className="ops-chip">Min conviction {ratioPercent(runtimeControl?.autopilot?.min_trade_conviction)}</span>
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
                disabled={busyAction === 'kick' || !runtimeControl?.runtime_started}
                onClick={() => handleRuntimeAction('kick')}
              >
                <Activity size={15} />
                Kick autopilot
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

        <div className="ops-grid ops-grid-controls-live">
          <Panel
            eyebrow="Timeline"
            title="Recent control history"
            description="Recovered, paused, resumed, or command-adapter events recorded by the backend."
          >
            {controlHistory.length ? (
              <div className="ops-timeline-list">
                {controlHistory.map((row) => (
                  <article key={row.event_id} className="ops-timeline-row">
                    <div className="ops-timeline-head">
                      <div>
                        <strong>{titleize(row.action || row.event_type)}</strong>
                        <small>{compactDateTime(row.timestamp)}</small>
                      </div>
                      <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                    </div>
                    <p className="ops-timeline-reason">
                      {summarize(row.reason || row.payload?.reason || row.event_type, 180)}
                    </p>
                    <div className="ops-timeline-meta">
                      <span>{row.actor || 'api.admin'}</span>
                      <span>{row.run_id || 'n/a'}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="ops-empty">Runtime control history is not available yet.</div>
            )}
          </Panel>

          <Panel
            eyebrow="Swarm"
            title="Workers and task board"
            description="Live worker posture plus the most recent operator-visible task events from the CRM surface."
          >
            {workerRows.length ? (
              <div className="ops-worker-grid">
                {workerRows.map((row, index) => (
                  <article key={makeListKey([row.role, row.agent_id, row.started], index)} className="ops-worker-card">
                    <div className="ops-worker-head">
                      <div>
                        <strong>{titleize(row.role)}</strong>
                        <small>{row.running ? 'running' : row.started ? 'started' : 'idle'}</small>
                      </div>
                      <TonePill tone={row.running ? 'good' : row.started ? 'neutral' : 'caution'}>
                        {row.running ? 'Running' : row.started ? 'Standby' : 'Idle'}
                      </TonePill>
                    </div>
                    <div className="ops-worker-stats">
                      <div className="ops-worker-stat">
                        <span>Done</span>
                        <strong>{number(row.completed_count)}</strong>
                      </div>
                      <div className="ops-worker-stat">
                        <span>Failed</span>
                        <strong>{number(row.failed_count)}</strong>
                      </div>
                      <div className="ops-worker-stat">
                        <span>Blocked</span>
                        <strong>{number(row.blocked_count)}</strong>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="ops-empty">Worker posture has not been published yet.</div>
            )}

            {taskHistoryRows.length ? (
              <div className="ops-task-list">
                {taskHistoryRows.slice(0, 6).map((row, index) => (
                  <article key={makeListKey([row.task_id, row.ts, row.event, row.run_id], index)} className="ops-task-row">
                    <div className="ops-task-head">
                      <strong>{row.details?.symbol || row.payload?.symbol || titleize(row.role)}</strong>
                      <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                    </div>
                    <p className="ops-task-copy">
                      {titleize(row.role)} / {row.run_id || 'n/a'}
                    </p>
                    <div className="ops-task-meta">
                      <span>{compactDateTime(row.ts)}</span>
                      <span>{summarize(row.details?.reason || row.payload?.command || row.event, 120)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="ops-empty">No recent task history is available from the operator CRM surface.</div>
            )}

            <div className="ops-inline-chips">
              <span className="ops-chip">Blocked decisions {number(blockedDecisionRows.length)}</span>
              <span className="ops-chip">Active tasks {number(runtimeControl?.active_task_count)}</span>
              <span className="ops-chip">Opportunity rows {number(safeArray(operatorCrm?.discovery?.opportunities).length)}</span>
            </div>
          </Panel>
        </div>
      </>
    );
  };

  const renderCore = () => renderPipeline();

  const renderWarRoom = () => renderOverview();

  const renderAgents = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Hierarchy"
          title="System Overview"
          description="Restored live hierarchy map and WebSocket-backed agent posture from the pre-refactor admin surface."
        >
          <SystemOverview />
        </Panel>

        <Panel
          eyebrow="Swarm"
          title="Agent Monitor"
          description="Specialist workers, active tasks, and recent runtime events."
        >
          <AgentMonitor expanded />
        </Panel>
      </div>

      <div className="ops-grid ops-grid-controls-live">
        <Panel
          eyebrow="Runtime queue"
          title="Workers and task board"
          description="Specialist worker posture and the latest fund-runtime task history."
        >
          {workerRows.length ? (
            <div className="ops-worker-grid">
                {workerRows.map((row, index) => (
                  <article key={makeListKey([row.role, row.agent_id, row.started], index)} className="ops-worker-card">
                  <div className="ops-worker-head">
                    <div>
                      <strong>{titleize(row.role)}</strong>
                      <small>{row.running ? 'running' : row.started ? 'started' : 'idle'}</small>
                    </div>
                    <TonePill tone={row.running ? 'good' : row.started ? 'neutral' : 'caution'}>
                      {row.running ? 'Running' : row.started ? 'Standby' : 'Idle'}
                    </TonePill>
                  </div>
                  <div className="ops-worker-stats">
                    <div className="ops-worker-stat">
                      <span>Done</span>
                      <strong>{number(row.completed_count)}</strong>
                    </div>
                    <div className="ops-worker-stat">
                      <span>Failed</span>
                      <strong>{number(row.failed_count)}</strong>
                    </div>
                    <div className="ops-worker-stat">
                      <span>Blocked</span>
                      <strong>{number(row.blocked_count)}</strong>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Worker posture has not been published yet.</div>
          )}

          {taskHistoryRows.length ? (
            <div className="ops-task-list">
              {taskHistoryRows.slice(0, 8).map((row, index) => (
                <article key={makeListKey([row.task_id, row.ts, row.event, row.run_id], index)} className="ops-task-row">
                  <div className="ops-task-head">
                    <strong>{row.details?.symbol || row.payload?.symbol || titleize(row.role)}</strong>
                    <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                  </div>
                  <p className="ops-task-copy">
                    {titleize(row.role)} / {row.run_id || 'n/a'}
                  </p>
                  <div className="ops-task-meta">
                    <span>{compactDateTime(row.ts)}</span>
                    <span>{summarize(row.details?.reason || row.payload?.command || row.event, 120)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No recent task history is available from the fund runtime.</div>
          )}
        </Panel>

        <Panel
          eyebrow="Runtime memory"
          title="Control history"
          description="Recovered control actions and operator-visible runtime memory."
        >
          {controlHistory.length ? (
            <div className="ops-timeline-list">
              {controlHistory.map((row, index) => (
                <article key={makeListKey([row.event_id, row.timestamp, row.event_type], index)} className="ops-timeline-row">
                  <div className="ops-timeline-head">
                    <div>
                      <strong>{titleize(row.action || row.event_type)}</strong>
                      <small>{compactDateTime(row.timestamp)}</small>
                    </div>
                    <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                  </div>
                  <p className="ops-timeline-reason">
                    {summarize(row.reason || row.payload?.reason || row.event_type, 180)}
                  </p>
                  <div className="ops-timeline-meta">
                    <span>{row.actor || 'api.admin'}</span>
                    <span>{row.run_id || 'n/a'}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Runtime control history is not available yet.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderPerformance = () => (
    <>
      <div className="ops-metric-grid ops-metric-grid-portfolio">
        <MetricTile
          icon={Database}
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

      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Track record"
          title="Equity and P&L curve"
          description="Paper performance history captured by the backend snapshot ledger."
        >
          {performanceSeries.length ? (
            <>
              <div className="ops-chart-wrap">
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={performanceSeries} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="opsPerformanceFill" x1="0" y1="0" x2="0" y2="1">
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
                      fill="url(#opsPerformanceFill)"
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
                  <span className="ops-kv-label">Sharpe ratio</span>
                  <strong className="ops-kv-value">{Number(metrics?.sharpe_ratio || 0).toFixed(2)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Sample days</span>
                  <strong className="ops-kv-value">{number(performanceSummary?.track_record?.sample_days)}</strong>
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
          eyebrow="Post-trade context"
          title="Area breakdown and review trail"
          description="Portfolio-level context sourced from the CEO performance and post-trade review surfaces."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">Total unrealized</span>
              <strong className="ops-kv-value">{currency(performanceBreakdown?.total_unrealized_pnl)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">ML context count</span>
              <strong className="ops-kv-value">{number(mlEffectiveness?.count)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Post-trade reviews</span>
              <strong className="ops-kv-value">{number(postTradeReviews.length)}</strong>
            </div>
          </div>

          {performanceAreaRows.length ? (
            <div className="ops-mini-list">
              {performanceAreaRows.map((row) => (
                <div key={row.asset_class} className="ops-mini-row">
                  <div>
                    <strong>{titleize(row.asset_class)}</strong>
                    <small>{number(row.count)} symbols</small>
                  </div>
                  <div className="ops-mini-value">
                    <strong>{currency(row.market_value)}</strong>
                    <small className={Number(row.unrealized_pnl || 0) >= 0 ? 'ops-positive' : 'ops-negative'}>
                      {currency(row.unrealized_pnl)}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">Performance breakdown rows have not been published yet.</div>
          )}

          {postTradeReviews.length ? (
            <div className="ops-headline-list">
              {postTradeReviews.slice(0, 4).map((row, index) => (
                <article key={`${row.review_id || row.symbol}-${index}`} className="ops-headline-row">
                  <div className="ops-headline-tags">
                    <span className="ops-chip">{row.symbol || 'Review'}</span>
                    <span className="ops-chip">{titleize(row.status || row.review_status || 'recorded')}</span>
                    <span className="ops-chip">{formatRelative(row.created_at || row.recorded_at)}</span>
                  </div>
                  <p className="ops-headline-link is-static">
                    {row.title || row.summary || row.notes || 'No review detail published yet.'}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No recent post-trade reviews are available.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderDeliverables = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Knowledge outputs"
          title="Reports, posts, and lineage"
          description="Restored knowledge-base view so research outputs and downstream usage are visible again."
        >
          <div className="ops-kv-grid">
            <div className="ops-kv">
              <span className="ops-kv-label">KB reports</span>
              <strong className="ops-kv-value">{number(reportDeliverables.length)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Published posts</span>
              <strong className="ops-kv-value">{number(blogDeliverables.length)}</strong>
            </div>
            <div className="ops-kv">
              <span className="ops-kv-label">Lineage rows</span>
              <strong className="ops-kv-value">{number(lineageRows.length)}</strong>
            </div>
          </div>

          <div className="ops-inline-chips">
            {reportDeliverables.slice(0, 6).map((row) => (
              <span key={row.report_id} className="ops-chip">
                {row.title || row.report_id}
              </span>
            ))}
          </div>
        </Panel>

        <Panel
          eyebrow="Review trail"
          title="Recent post-trade reviews"
          description="The operational review artifacts that were hidden by the simplified surface."
        >
          {postTradeReviews.length ? (
            <div className="ops-headline-list">
              {postTradeReviews.slice(0, 6).map((row, index) => (
                <article key={`${row.review_id || row.symbol}-${index}`} className="ops-headline-row">
                  <div className="ops-headline-tags">
                    <span className="ops-chip">{row.symbol || 'Review'}</span>
                    <span className="ops-chip">{titleize(row.status || row.review_status || 'recorded')}</span>
                  </div>
                  <p className="ops-headline-link is-static">
                    {row.title || row.summary || row.notes || 'No review detail published yet.'}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No recent post-trade reviews are available.</div>
          )}
        </Panel>
      </div>

      <Panel
        eyebrow="Trace graph"
        title="Knowledge output chain"
        description="Research findings, KB documents, downstream consumers, and published outputs."
      >
        <KnowledgeTraceGraph reports={reportDeliverables} posts={blogDeliverables} lineageRows={lineageRows} />
      </Panel>

      <Panel
        eyebrow="Lineage"
        title="Recent lineage and traceability"
        description="The pre-refactor lineage browser is back so backend outputs remain auditable."
      >
        <LineagePanel />
      </Panel>
    </>
  );

  const renderDecisions = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Queue"
          title="Pending fund decisions"
          description="Restored approval queue for operator review and audit-trail access."
        >
          <DecisionQueue expanded />
        </Panel>

        <Panel
          eyebrow="Blocked"
          title="Blocked and deferred items"
          description="Risk-gate and execution items that still need review."
        >
          {blockedDecisionRows.length ? (
            <div className="ops-headline-list">
              {blockedDecisionRows.slice(0, 8).map((row, index) => (
                <article key={`${row.decision_id || row.symbol}-${index}`} className="ops-headline-row">
                  <div className="ops-headline-tags">
                    <span className="ops-chip">{row.symbol || 'Decision'}</span>
                    <span className="ops-chip">{titleize(row.status || 'blocked')}</span>
                  </div>
                  <p className="ops-headline-link is-static">
                    {summarize(row.reason || row.block_reason || row.message || JSON.stringify(row), 160)}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No blocked decisions are currently published.</div>
          )}

          {commandGroups.length ? (
            <div className="ops-command-groups">
              {commandGroups.map((group) => (
                <section key={group.key} className="ops-command-group">
                  <div className="ops-command-group-head">
                    <strong>{group.label}</strong>
                    <small>{number(group.items.length)} commands</small>
                  </div>
                  <div className="ops-command-chip-grid">
                    {group.items.map((command) => (
                      <button
                        key={`${group.key}-${command}`}
                        type="button"
                        className="ops-command-chip"
                        onClick={() => copyCommand(command)}
                      >
                        {command}
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : null}
        </Panel>
      </div>
    </>
  );

  const renderRisk = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Controls"
          title="Risk gauges"
          description="The dedicated risk surface is restored instead of being folded into a generic runtime tab."
        >
          <RiskGauges metrics={metrics} expanded />
        </Panel>

        <Panel
          eyebrow="Alerts"
          title="Live risk alerts"
          description="Drawdown, halt, and thesis degradation alerts published by the backend."
        >
          {riskAlerts.length ? (
            <div className="ops-headline-list">
              {riskAlerts.slice(0, 8).map((alert, index) => (
                <article key={`${alert.type || 'risk'}-${index}`} className="ops-headline-row">
                  <div className="ops-headline-tags">
                    <span className="ops-chip">{titleize(alert.type || 'risk_alert')}</span>
                    <span className="ops-chip">{titleize(alert.severity || 'info')}</span>
                  </div>
                  <p className="ops-headline-link is-static">{alert.message || 'No message provided.'}</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No live risk alerts are currently reported by the backend.</div>
          )}

          <div className="ops-inline-chips">
            <span className="ops-chip">System halt {systemStatus?.halt?.halted ? 'active' : 'clear'}</span>
            <span className="ops-chip">Strict data {runtimeControl?.strict_real_data_only ? 'on' : 'off'}</span>
            <span className="ops-chip">Drawdown {plainPercent(metrics?.current_drawdown, 2)}</span>
          </div>
        </Panel>
      </div>

      <Panel
        eyebrow="Allocation"
        title="Capital pressure"
        description="Asset-class weights and live utilization from the active allocation policy."
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
    </>
  );

  const renderPositions = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel
          eyebrow="Portfolio"
          title="Portfolio positions"
          description="Detailed position management plus the original operator-friendly positions panel."
        >
          <PositionsPanel />
        </Panel>

        <Panel
          eyebrow="Book context"
          title="Current paper-book summary"
          description="Quick ranking of the current book without leaving the positions tab."
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
        </Panel>
      </div>
      {renderPortfolio()}
    </>
  );

  const renderMarketWatch = () => (
    <>
      <Panel
        eyebrow="Charts"
        title="Focus chart board"
        description="The chart strip is back so operators can inspect the live focus names without leaving admin."
      >
        {focusChartSymbols.length ? (
          <div className="market-watch-chart-grid">
            {focusChartSymbols.map((symbol) => (
              <div key={symbol} className="market-watch-chart-card">
                <div className="market-watch-chart-head">
                  <strong>{symbol}</strong>
                  <span>{titleize(symbol)}</span>
                </div>
                <TradingViewWidget symbol={symbol} height={340} />
              </div>
            ))}
          </div>
        ) : (
          <div className="ops-empty">No focus symbols are available for the chart board.</div>
        )}
      </Panel>
      {renderMarket()}
    </>
  );

  const activeNavigationItem = navigationItems.find((item) => item.id === activeTab) || navigationItems[0];
  const currentPolicy = systemStatus?.allocation_policy?.policy || {};
  const currentConstraints = currentPolicy?.constraints || {};
  const topCandidateRows = tradeCandidates.slice(0, 10);
  const topPositionRows = positions.slice(0, 8);
  const providerRows = safeArray(systemStatus?.data_source?.providers);

  const renderControlCenter = () => (
    <>
      <OverviewPanel data={overviewData} onNavigate={setActiveTab} />

      <div className="ops-metric-grid ops-metric-grid-control">
        <MetricTile
          icon={Activity}
          label="Total Equity"
          value={currency(metrics?.total_equity)}
          detail={`Baseline ${currency(metrics?.baseline_equity)} | ${signedPlainPercent(metrics?.equity_change)}`}
          tone={Number(metrics?.equity_change || 0) >= 0 ? 'good' : 'caution'}
        />
        <MetricTile
          icon={LineChart}
          label="Live P&L"
          value={currency(metrics?.unrealized_pnl)}
          detail={`Market value ${currency(latestSnapshot?.market_value)} | cash ${currency(latestSnapshot?.cash)}`}
          tone={Number(metrics?.unrealized_pnl || 0) >= 0 ? 'good' : 'bad'}
        />
        <MetricTile
          icon={Workflow}
          label="Runtime"
          value={runtimeControl?.runtime_started ? 'Running' : 'Paused'}
          detail={`Tasks ${number(runtimeControl?.active_task_count)} | autopilot ${runtimeControl?.autopilot?.enabled ? 'on' : 'off'}`}
          tone={runtimeControl?.runtime_started ? 'good' : 'caution'}
        />
        <MetricTile
          icon={Shield}
          label="Risk Posture"
          value={riskAlerts.length ? `${riskAlerts.length} alerts` : systemStatus?.halt?.halted ? 'Halted' : 'Clear'}
          detail={riskAlerts.length ? summarize(riskAlerts[0]?.message, 80) : systemStatus?.halt?.reason || 'No active breaker conditions'}
          tone={riskAlerts.length || systemStatus?.halt?.halted ? 'bad' : 'good'}
        />
        <MetricTile
          icon={Database}
          label="Pipeline"
          value={systemStatus?.data_source?.status || 'Unknown'}
          detail={`${number(safeArray(pipelineStatus?.configured_symbols).length)} symbols | ${number(pipelineFailures.length)} failures`}
          tone={pipelineFailures.length ? 'caution' : statusTone(systemStatus?.data_source?.status)}
        />
        <MetricTile
          icon={TrendingUp}
          label="Demand Funnel"
          value={number(topCandidateRows.length)}
          detail={`${number(candidateBuckets.trade_candidate)} ready | ${number(blockedDecisionRows.length)} blocked`}
          tone={topCandidateRows.length ? 'good' : 'neutral'}
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

      <div className="ops-grid ops-grid-control-top">
        <Panel
          eyebrow="Executive Brief"
          title="Immediate priorities"
          description="The highest-leverage decisions and operational risks across capital, runtime, and pipeline health."
        >
          <div className="ops-priority-list">
            {priorityRows.map((row) => (
              <article key={row.key} className="ops-priority-card">
                <div className="ops-priority-head">
                  <div>
                    <strong>{row.title}</strong>
                    <small>{row.key === 'memory' ? 'Operator memory' : 'Live runtime signal'}</small>
                  </div>
                  <TonePill tone={row.tone}>{row.status}</TonePill>
                </div>
                <p>{row.detail}</p>
              </article>
            ))}
          </div>
          <div className="ops-inline-chips">
            <span className="ops-chip">Run {latestRun?.run_id || 'n/a'}</span>
            <span className="ops-chip">Positions {number(positions.length)}</span>
            <span className="ops-chip">Tasks {number(taskHistoryRows.length)}</span>
            <span className="ops-chip">Knowledge events {number(knowledgeStats?.event_count)}</span>
          </div>
        </Panel>

        <Panel
          eyebrow="Performance"
          title="Equity pulse"
          description="Short-horizon portfolio health so the operator can see drift before changing controls."
        >
          {performanceSeries.length ? (
            <>
              <div className="ops-chart-wrap">
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={performanceSeries} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="opsExecutiveEquityFill" x1="0" y1="0" x2="0" y2="1">
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
                      domain={[(dataMin) => Math.max(0, dataMin - 50), (dataMax) => dataMax + 50]}
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
                      fill="url(#opsExecutiveEquityFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="ops-kv-grid ops-kv-grid-tight">
                <div className="ops-kv">
                  <span className="ops-kv-label">Sharpe</span>
                  <strong className="ops-kv-value">{Number(metrics?.sharpe_ratio || 0).toFixed(2)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Track return</span>
                  <strong className="ops-kv-value">{plainPercent(performanceSummary?.track_record?.total_return_pct, 2)}</strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Alpha vs benchmark</span>
                  <strong className="ops-kv-value">
                    {signedPlainPercent(performanceSummary?.track_record?.alpha_vs_primary_benchmark_pct, 2)}
                  </strong>
                </div>
                <div className="ops-kv">
                  <span className="ops-kv-label">Latest snapshot</span>
                  <strong className="ops-kv-value">{formatDateTime(latestSnapshot?.recorded_at)}</strong>
                </div>
              </div>
            </>
          ) : (
            <div className="ops-empty">Performance snapshots have not loaded yet.</div>
          )}
        </Panel>
      </div>

      <div className="ops-grid ops-grid-control-top">
        <Panel
          eyebrow="Capital Deployment"
          title="Portfolio leaders"
          description="Highest-conviction winners and laggards so interventions stay tied to book reality."
        >
          {topPositionRows.length ? (
            <div className="ops-mini-list">
              {topPositionRows.slice(0, 5).map((row) => (
                <div key={row.symbol} className="ops-mini-row">
                  <div>
                    <strong>{row.symbol}</strong>
                    <div className="ops-table-subcopy">
                      {titleize(row.assetClass)} | {titleize(row.thesisState)}
                    </div>
                  </div>
                  <div className="ops-mini-value">
                    <strong>{currency(row.marketValue)}</strong>
                    <span className={row.unrealizedPnl >= 0 ? 'ops-positive' : 'ops-negative'}>
                      {currency(row.unrealizedPnl)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No live positions are deployed.</div>
          )}
          <div className="ops-inline-chips">
            <span className="ops-chip">
              Strongest {strongestPosition ? `${strongestPosition.symbol} ${currency(strongestPosition.unrealizedPnl)}` : 'n/a'}
            </span>
            <span className="ops-chip">
              Weakest {weakestPosition ? `${weakestPosition.symbol} ${currency(weakestPosition.unrealizedPnl)}` : 'n/a'}
            </span>
          </div>
        </Panel>

        <Panel
          eyebrow="Demand Funnel"
          title="Pipeline and blocked flow"
          description="Candidate supply, provider posture, and blocked execution demand in one place."
        >
          <div className="ops-inline-chips">
            {Object.entries(candidateBuckets).map(([bucket, count]) => (
              <span key={bucket} className="ops-chip">
                {titleize(bucket)} {number(count)}
              </span>
            ))}
          </div>
          {topCandidateRows.length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Score</th>
                    <th>Text</th>
                    <th>Bars</th>
                  </tr>
                </thead>
                <tbody>
                  {topCandidateRows.slice(0, 5).map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">{row.symbol}</td>
                      <td>{ratioPercent(row.score, 1)}</td>
                      <td>{number(row.textEvents)}</td>
                      <td>{titleize(row.barsStatus)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">No live trade candidates are currently ranked.</div>
          )}
          <div className="ops-inline-chips">
            {providerRows.slice(0, 5).map((row, index) => (
              <span key={makeListKey([row.provider, row.mode, row.status], index)} className="ops-chip">
                {row.provider || row.name || 'provider'} {titleize(row.mode || row.status || 'unknown')}
              </span>
            ))}
          </div>
          {blockedDecisionRows.length ? (
            <div className="ops-task-list">
              {blockedDecisionRows.slice(0, 3).map((row, index) => (
                <article key={makeListKey([row.event_id, row.symbol, row.timestamp, row.reason], index)} className="ops-task-row">
                  <div className="ops-task-head">
                    <strong>{row.symbol || row.asset_class || 'blocked trade'}</strong>
                    <TonePill tone="bad">{titleize(row.status || row.event_type || 'blocked')}</TonePill>
                  </div>
                  <div className="ops-task-meta">
                    <span>{row.run_id || 'n/a'}</span>
                    <span>{summarize(row.reason || row.payload?.reason || row.payload?.message || JSON.stringify(row), 120)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </Panel>
      </div>

      <div className="ops-grid ops-grid-overview">
        <Panel eyebrow="Runtime" title="Backend Controls">
          <div className="ops-kv-grid">
            <div className="ops-kv"><span className="ops-kv-label">Runtime</span><strong className="ops-kv-value">{runtimeControl?.runtime_started ? 'Running' : 'Paused'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Autopilot</span><strong className="ops-kv-value">{runtimeControl?.autopilot?.enabled ? 'Enabled' : 'Disabled'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Strict Data</span><strong className="ops-kv-value">{runtimeControl?.strict_real_data_only ? 'On' : 'Off'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Broker</span><strong className="ops-kv-value">{systemStatus?.execution_mode?.broker || 'n/a'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Profile</span><strong className="ops-kv-value">{activeProfile?.name || 'n/a'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Last Sync</span><strong className="ops-kv-value">{lastUpdate ? formatRelative(lastUpdate) : 'pending'}</strong></div>
          </div>

          <div className="ops-button-row">
            <button type="button" className="ops-button" disabled={busyAction === 'resume' || runtimeControl?.runtime_started} onClick={() => handleRuntimeAction('resume')}><Play size={15} />Resume</button>
            <button type="button" className="ops-button secondary" disabled={busyAction === 'pause' || !runtimeControl?.runtime_started} onClick={() => handleRuntimeAction('pause')}><Pause size={15} />Pause</button>
            <button type="button" className="ops-button secondary" disabled={busyAction === 'recover'} onClick={() => handleRuntimeAction('recover')}><Workflow size={15} />Recover ML</button>
            <button type="button" className="ops-button secondary" disabled={busyAction === 'clear-halt' || !systemStatus?.halt?.halted} onClick={() => handleRuntimeAction('clear-halt')}><Shield size={15} />Clear Halt</button>
            <button type="button" className="ops-button secondary" disabled={busyAction === 'kick' || !runtimeControl?.runtime_started} onClick={() => handleRuntimeAction('kick')}><Activity size={15} />Kick Autopilot</button>
            <button type="button" className="ops-button secondary" disabled={busyAction === 'capture'} onClick={() => handleRuntimeAction('capture')}><RefreshCw size={15} />Snapshot</button>
          </div>

          {systemStatus?.halt?.halted ? (
            <div className="ops-section-block">
              <div className="ops-inline-chips">
                <span className={`ops-chip ${systemStatus?.halt?.halted ? toneClassName('bad') : ''}`}>Halt {systemStatus?.halt?.halted ? 'active' : 'clear'}</span>
                {systemStatus?.halt?.reason ? <span className="ops-chip">{systemStatus.halt.reason}</span> : null}
              </div>
              {recoveryChecklist.length ? (
                <ul className="ops-list">
                  {recoveryChecklist.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </Panel>

        <Panel eyebrow="Capital" title="Paper Broker">
          <form className="ops-form-stack" onSubmit={handleCapitalSubmit}>
            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Delta USD</span>
                <input className="ops-input" type="number" step="100" value={capitalForm.amountUsd} onChange={(event) => setCapitalForm((prev) => ({ ...prev, amountUsd: event.target.value }))} />
              </label>
              <label className="ops-field">
                <span>Target Cash USD</span>
                <input className="ops-input" type="number" step="100" value={capitalForm.targetCashUsd} onChange={(event) => setCapitalForm((prev) => ({ ...prev, targetCashUsd: event.target.value }))} />
              </label>
            </div>
            <label className="ops-check">
              <input type="checkbox" checked={capitalForm.clearPositions} onChange={(event) => setCapitalForm((prev) => ({ ...prev, clearPositions: event.target.checked }))} />
              <span>Clear positions</span>
            </label>
            <label className="ops-check">
              <input type="checkbox" checked={capitalForm.clearOrders} onChange={(event) => setCapitalForm((prev) => ({ ...prev, clearOrders: event.target.checked }))} />
              <span>Clear order history</span>
            </label>
            <div className="ops-button-row compact">
              <button type="submit" className="ops-button" disabled={busyMutation === 'capital'}>Apply Capital Update</button>
              <button type="button" className="ops-button danger" disabled={busyMutation === 'inception-reset'} onClick={handleInceptionReset}>Clean Inception Reset</button>
            </div>
          </form>
        </Panel>
      </div>

      <Panel eyebrow="Policy" title="Allocation Policy">
        <form className="ops-form-stack" onSubmit={handlePolicySubmit}>
          <div className="ops-form-grid ops-form-grid-wide">
            <label className="ops-field">
              <span>Total Capital USD</span>
              <input className="ops-input" type="number" min="1" step="100" value={policyForm.totalCapitalUsd} onChange={(event) => setPolicyForm((prev) => ({ ...prev, totalCapitalUsd: event.target.value }))} />
            </label>
            <label className="ops-field">
              <span>Reserve Cash USD</span>
              <input className="ops-input" type="number" min="0" step="100" value={policyForm.reserveCashUsd} onChange={(event) => setPolicyForm((prev) => ({ ...prev, reserveCashUsd: event.target.value }))} />
            </label>
            <label className="ops-field">
              <span>Min Cash Reserve %</span>
              <input className="ops-input" type="number" min="0" max="1" step="0.01" value={policyForm.minCashReservePct} onChange={(event) => setPolicyForm((prev) => ({ ...prev, minCashReservePct: event.target.value }))} />
            </label>
            <label className="ops-field">
              <span>Max Asset Class Exposure %</span>
              <input className="ops-input" type="number" min="0" max="1" step="0.01" value={policyForm.maxAssetClassExposurePct} onChange={(event) => setPolicyForm((prev) => ({ ...prev, maxAssetClassExposurePct: event.target.value }))} />
            </label>
            <label className="ops-field">
              <span>Max Single Trade %</span>
              <input className="ops-input" type="number" min="0" max="1" step="0.01" value={policyForm.maxSingleTradeNotionalPct} onChange={(event) => setPolicyForm((prev) => ({ ...prev, maxSingleTradeNotionalPct: event.target.value }))} />
            </label>
            <label className="ops-field">
              <span>Allowed Asset Classes</span>
              <input className="ops-input" type="text" value={policyForm.allowedAssetClasses} onChange={(event) => setPolicyForm((prev) => ({ ...prev, allowedAssetClasses: event.target.value }))} />
            </label>
          </div>
          <label className="ops-check">
            <input type="checkbox" checked={policyForm.weekendTradingEnabled} onChange={(event) => setPolicyForm((prev) => ({ ...prev, weekendTradingEnabled: event.target.checked }))} />
            <span>Weekend Trading Enabled</span>
          </label>
          <div className="ops-inline-chips">
            {allocationRows.map((row) => (
              <span key={row.assetClass} className="ops-chip">
                {titleize(row.assetClass)} {ratioPercent(row.weight)} / {ratioPercent(row.utilization)}
              </span>
            ))}
          </div>
          <div className="ops-button-row compact">
            <button type="submit" className="ops-button" disabled={busyMutation === 'policy'}>Save Policy</button>
          </div>
        </form>
      </Panel>
    </>
  );

  const renderOrdersDesk = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel eyebrow="Ticket" title="Manual Order">
          <form className="ops-form-stack" onSubmit={handleOrderSubmit}>
            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Symbol</span>
                <input className="ops-input ops-input-uppercase" type="text" value={orderForm.symbol} onChange={(event) => setOrderForm((prev) => ({ ...prev, symbol: event.target.value.toUpperCase() }))} />
              </label>
              <label className="ops-field">
                <span>Side</span>
                <select className="ops-input" value={orderForm.side} onChange={(event) => setOrderForm((prev) => ({ ...prev, side: event.target.value }))}>
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Quantity</span>
                <input className="ops-input" type="number" min="1" step="1" value={orderForm.quantity} onChange={(event) => setOrderForm((prev) => ({ ...prev, quantity: event.target.value }))} />
              </label>
            </div>
            <div className="ops-inline-chips">
              {safeArray(pipelineStatus?.configured_symbols).slice(0, 12).map((symbol) => (
                <button key={symbol} type="button" className="ops-command-chip" onClick={() => setOrderForm((prev) => ({ ...prev, symbol }))}>
                  {symbol}
                </button>
              ))}
            </div>
            <div className="ops-button-row compact">
              <button type="submit" className="ops-button" disabled={busyMutation === 'order'}>Submit Order</button>
            </div>
          </form>
        </Panel>

        <Panel eyebrow="Book" title="Book Snapshot">
          <div className="ops-kv-grid">
            <div className="ops-kv"><span className="ops-kv-label">Cash</span><strong className="ops-kv-value">{currency(latestSnapshot?.cash)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Market Value</span><strong className="ops-kv-value">{currency(latestSnapshot?.market_value)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Positions</span><strong className="ops-kv-value">{number(metrics?.active_positions)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">PnL</span><strong className="ops-kv-value">{currency(metrics?.unrealized_pnl)}</strong></div>
          </div>

          {topPositionRows.length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>PnL</th>
                    <th>Alloc</th>
                  </tr>
                </thead>
                <tbody>
                  {topPositionRows.map((row) => (
                    <tr key={row.symbol}>
                      <td className="ops-symbol-cell">{row.symbol}</td>
                      <td>{number(row.quantity)}</td>
                      <td>{currency(row.marketPrice)}</td>
                      <td className={row.unrealizedPnl >= 0 ? 'ops-positive' : 'ops-negative'}>{currency(row.unrealizedPnl)}</td>
                      <td>{plainPercent(row.allocationPct, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">No positions.</div>
          )}
        </Panel>
      </div>

      <Panel eyebrow="Positions" title="Open Positions">
        <PositionsPanel />
      </Panel>
    </>
  );

  const renderDecisionsDesk = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel eyebrow="Queue" title="Pending Decisions">
          <DecisionQueue expanded />
        </Panel>

        <Panel eyebrow="Blocked" title="Blocked Items">
          {blockedDecisionRows.length ? (
            <div className="ops-task-list">
              {blockedDecisionRows.slice(0, 10).map((row, index) => (
                <article key={`${row.decision_id || row.symbol}-${index}`} className="ops-task-row">
                  <div className="ops-task-head">
                    <strong>{row.symbol || row.decision_id || 'blocked'}</strong>
                    <TonePill tone="bad">{titleize(row.status || 'blocked')}</TonePill>
                  </div>
                  <div className="ops-task-meta">
                    <span>{row.run_id || 'n/a'}</span>
                    <span>{summarize(row.reason || row.block_reason || row.message || JSON.stringify(row), 160)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No blocked items.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderRuntimeDesk = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel eyebrow="Workers" title="Worker State">
          {workerRows.length ? (
            <div className="ops-worker-grid">
              {workerRows.map((row, index) => (
                <article key={makeListKey([row.role, row.agent_id, row.started], index)} className="ops-worker-card">
                  <div className="ops-worker-head">
                    <div>
                      <strong>{titleize(row.role)}</strong>
                      <small>{row.last_error ? summarize(row.last_error, 80) : 'ok'}</small>
                    </div>
                    <TonePill tone={row.running ? 'good' : row.started ? 'neutral' : 'caution'}>
                      {row.running ? 'Running' : row.started ? 'Standby' : 'Idle'}
                    </TonePill>
                  </div>
                  <div className="ops-worker-stats">
                    <div className="ops-worker-stat"><span>Done</span><strong>{number(row.completed_count)}</strong></div>
                    <div className="ops-worker-stat"><span>Failed</span><strong>{number(row.failed_count)}</strong></div>
                    <div className="ops-worker-stat"><span>Blocked</span><strong>{number(row.blocked_count)}</strong></div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No worker state.</div>
          )}
        </Panel>

        <Panel eyebrow="Pipeline" title="Pipeline / Providers">
          <div className="ops-kv-grid">
            <div className="ops-kv"><span className="ops-kv-label">Scheduler</span><strong className="ops-kv-value">{pipelineStatus?.running ? 'Running' : 'Idle'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Universe</span><strong className="ops-kv-value">{number(safeArray(pipelineStatus?.configured_symbols).length)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Prices</span><strong className="ops-kv-value">{number(latestRun?.counts?.prices)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Text Events</span><strong className="ops-kv-value">{number(latestRun?.counts?.text_events)}</strong></div>
          </div>
          <div className="ops-inline-chips">
            {providerRows.slice(0, 8).map((row, index) => (
              <span key={`${row.provider || 'provider'}-${index}`} className="ops-chip">
                {row.provider || row.name || 'provider'} {titleize(row.mode || row.status || 'unknown')}
              </span>
            ))}
          </div>
          {pipelineFailures.length ? (
            <div className="ops-task-list">
              {pipelineFailures.map((row) => (
                <article key={row.symbol} className="ops-task-row">
                  <div className="ops-task-head">
                    <strong>{row.symbol}</strong>
                    <TonePill tone="bad">Failed</TonePill>
                  </div>
                  <div className="ops-task-meta">
                    <span>{summarize(row.error, 160)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </Panel>
      </div>

      <div className="ops-grid ops-grid-controls-live">
        <Panel eyebrow="Tasks" title="Recent Task History">
          {taskHistoryRows.length ? (
            <div className="ops-task-list">
              {taskHistoryRows.slice(0, 12).map((row, index) => (
                <article key={makeListKey([row.task_id, row.ts, row.event, row.run_id], index)} className="ops-task-row">
                  <div className="ops-task-head">
                    <strong>{row.details?.symbol || row.payload?.symbol || titleize(row.role)}</strong>
                    <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                  </div>
                  <div className="ops-task-meta">
                    <span>{compactDateTime(row.ts)}</span>
                    <span>{row.run_id || 'n/a'}</span>
                    <span>{summarize(row.details?.reason || row.payload?.command || row.event, 120)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No task history.</div>
          )}
        </Panel>

        <Panel eyebrow="Controls" title="Control History">
          {controlHistory.length ? (
            <div className="ops-timeline-list">
              {controlHistory.map((row, index) => (
                <article key={makeListKey([row.event_id, row.timestamp, row.event_type], index)} className="ops-timeline-row">
                  <div className="ops-timeline-head">
                    <div>
                      <strong>{titleize(row.action || row.event_type)}</strong>
                      <small>{compactDateTime(row.timestamp)}</small>
                    </div>
                    <TonePill tone={statusTone(row.status)}>{titleize(row.status)}</TonePill>
                  </div>
                  <div className="ops-timeline-meta">
                    <span>{row.actor || 'api.admin'}</span>
                    <span>{summarize(row.reason || row.payload?.reason || row.event_type, 140)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No control history.</div>
          )}
        </Panel>
      </div>
    </>
  );

  const renderKnowledgeDesk = () => (
    <>
      <div className="ops-grid ops-grid-overview">
        <Panel eyebrow="Store" title="Knowledge Store">
          <div className="ops-kv-grid">
            <div className="ops-kv"><span className="ops-kv-label">Canonical</span><strong className="ops-kv-value">{knowledgeStats?.canonical_store || 'n/a'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Projection</span><strong className="ops-kv-value">{knowledgeStats?.projection_store || 'n/a'}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Events</span><strong className="ops-kv-value">{number(knowledgeStats?.event_count)}</strong></div>
            <div className="ops-kv"><span className="ops-kv-label">Graph Sync</span><strong className="ops-kv-value">{knowledgeStats?.last_graphify_sync_status || 'n/a'}</strong></div>
          </div>

          <form className="ops-form-stack" onSubmit={(event) => event.preventDefault()}>
            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Run ID</span>
                <input className="ops-input" type="text" value={knowledgeForm.runId} onChange={(event) => setKnowledgeForm((prev) => ({ ...prev, runId: event.target.value }))} />
              </label>
              <label className="ops-field">
                <span>Agent ID</span>
                <input className="ops-input" type="text" value={knowledgeForm.agentId} onChange={(event) => setKnowledgeForm((prev) => ({ ...prev, agentId: event.target.value }))} />
              </label>
            </div>
            <label className="ops-check">
              <input type="checkbox" checked={knowledgeForm.seedEvent} onChange={(event) => setKnowledgeForm((prev) => ({ ...prev, seedEvent: event.target.checked }))} />
              <span>Seed event</span>
            </label>
            <div className="ops-button-row compact">
              <button type="button" className="ops-button danger" disabled={busyMutation === 'knowledge-reset'} onClick={() => handleKnowledgeSubmit('knowledge-reset')}>Reset Store</button>
              <button type="button" className="ops-button" disabled={busyMutation === 'knowledge-rebuild'} onClick={() => handleKnowledgeSubmit('knowledge-rebuild')}>Rebuild Projection</button>
            </div>
          </form>
        </Panel>

        <Panel eyebrow="Namespaces" title="Namespace Load">
          {topNamespaceRows.length ? (
            <div className="ops-mini-list">
              {topNamespaceRows.map((row) => (
                <div key={row.key} className="ops-mini-row">
                  <div><strong>{titleize(row.key)}</strong></div>
                  <div className="ops-mini-value"><strong>{number(row.count)}</strong></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ops-empty">No namespace data.</div>
          )}
        </Panel>
      </div>

      <Panel eyebrow="Lineage" title="Run Lineage">
        <LineagePanel limit={20} />
      </Panel>
    </>
  );

  const renderSettingsDesk = () => (
    <div className="ops-grid ops-grid-overview">
      <Panel eyebrow="System" title="Backend State">
        <div className="ops-kv-grid">
          <div className="ops-kv"><span className="ops-kv-label">Backend</span><strong className="ops-kv-value">{backendTarget}</strong></div>
          <div className="ops-kv"><span className="ops-kv-label">Execution</span><strong className="ops-kv-value">{systemStatus?.execution_mode?.status || 'n/a'}</strong></div>
          <div className="ops-kv"><span className="ops-kv-label">Default Model</span><strong className="ops-kv-value">{workersStatus?.ai_role_adapter?.default_model || 'n/a'}</strong></div>
          <div className="ops-kv"><span className="ops-kv-label">Provider</span><strong className="ops-kv-value">{workersStatus?.ai_role_adapter?.provider || 'n/a'}</strong></div>
          <div className="ops-kv"><span className="ops-kv-label">Profile</span><strong className="ops-kv-value">{activeProfile?.name || 'n/a'}</strong></div>
          <div className="ops-kv"><span className="ops-kv-label">Run</span><strong className="ops-kv-value">{latestRun?.run_id || 'n/a'}</strong></div>
        </div>
        <div className="ops-inline-chips">
          {supportRoleModels.map(([role, model]) => (
            <span key={role} className="ops-chip">
              {titleize(role)} {model}
            </span>
          ))}
        </div>
      </Panel>

      <Panel eyebrow="Candidates" title="Top Candidate Board">
        {topCandidateRows.length ? (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Bucket</th>
                  <th>Score</th>
                  <th>Bars</th>
                  <th>Text</th>
                </tr>
              </thead>
              <tbody>
                {topCandidateRows.map((row) => (
                  <tr key={row.symbol}>
                    <td className="ops-symbol-cell">{row.symbol}</td>
                    <td>{titleize(row.category)}</td>
                    <td>{ratioPercent(row.score, 1)}</td>
                    <td>{number(row.priceBars)}</td>
                    <td>{number(row.textEvents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="ops-empty">No candidates.</div>
        )}
      </Panel>
    </div>
  );

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'control':
        return renderControlCenter();
      case 'positions':
        return renderPositions();
      case 'market':
        return renderMarketWatch();
      case 'agents':
        return renderAgents();
      case 'risk':
        return renderRisk();
      case 'performance':
        return renderPerformance();
      case 'orders':
        return renderOrdersDesk();
      case 'decisions':
        return renderDecisionsDesk();
      case 'runtime':
        return renderRuntimeDesk();
      case 'knowledge':
        return renderKnowledgeDesk();
      case 'settings':
        return renderSettingsDesk();
      default:
        return renderControlCenter();
    }
  };

  return (
    <div className={`ops-shell ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`ops-sidebar ${isSidebarCollapsed ? 'is-collapsed' : ''}`}>
        <div className="ops-sidebar-top">
          <div className="ops-sidebar-header">
            <div className="ops-brand">
              <div className="ops-brand-mark ops-brand-mark-logo">
                <img src="/VektorLogo.png?v=20260422b" alt="Vektor" className="ops-brand-logo" />
              </div>
              <div className="ops-brand-copy">
                <strong>Vektor</strong>
                <small>Control Center</small>
              </div>
            </div>
            {isDesktopViewport ? (
              <button
                type="button"
                className="ops-sidebar-toggle"
                aria-label={isSidebarCollapsed ? 'Expand admin sidebar' : 'Collapse admin sidebar'}
                aria-pressed={isSidebarCollapsed}
                onClick={() => setIsSidebarCollapsed((previous) => !previous)}
              >
                {isSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
              </button>
            ) : null}
          </div>

          <div className="ops-sidebar-summary">
            <div className="ops-sidebar-summary-row"><span>Backend</span><strong>{backendTarget}</strong></div>
            <div className="ops-sidebar-summary-row"><span>Status</span><strong>{connectionStatus === 'connected' ? 'Live' : connectionStatus === 'error' ? 'Offline' : 'Syncing'}</strong></div>
            <div className="ops-sidebar-summary-row"><span>Runtime</span><strong>{runtimeControl?.runtime_started ? 'Running' : 'Paused'}</strong></div>
            <div className="ops-sidebar-summary-row"><span>Halt</span><strong>{systemStatus?.halt?.halted ? 'Active' : 'Clear'}</strong></div>
          </div>
        </div>

        <nav className="ops-nav" aria-label="Admin sections">
          {navigationItems.map((item) => (
            <NavItem key={item.id} item={item} active={activeTab === item.id} collapsed={isSidebarCollapsed} onSelect={setActiveTab} />
          ))}
        </nav>

        <div className="ops-sidebar-footer">
          <div className="ops-connection-row">
            <span className={`ops-connection-dot ${connectionStatus}`} />
            <span className="ops-connection-label">{connectionStatus === 'connected' ? 'Live backend' : connectionStatus === 'error' ? 'Backend unreachable' : 'Syncing'}</span>
          </div>
        </div>
      </aside>

      <main className="ops-main">
        <header className="ops-header">
          <div className="ops-header-top">
            <div className="ops-header-copy">
              <p className="ops-header-eyebrow">{activeNavigationItem.label}</p>
              <h1>{activeNavigationItem.label}</h1>
            </div>
            <div className="ops-button-row compact">
              <button type="button" className="ops-button secondary" disabled={refreshing} onClick={() => fetchAdminState({ manual: true })}>
                <RefreshCw size={15} className={refreshing ? 'ops-spin' : ''} />
                Refresh
              </button>
            </div>
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
          {initialLoading ? <div className="ops-empty">Loading backend state.</div> : null}

          {connectionStatus === 'error' ? (
            <div className={`ops-banner ${toneClassName('bad')}`}>
              <AlertCircle size={16} />
              <div>
                <strong>Backend unreachable</strong>
                <p>{backendTarget}</p>
              </div>
            </div>
          ) : null}

          {fallbackProvider ? (
            <div className={`ops-banner ${toneClassName('caution')}`}>
              <Database size={16} />
              <div>
                <strong>Fallback provider</strong>
                <p>{fallbackProvider.provider} {fallbackProvider.symbol || ''} {fallbackProvider.detail || ''}</p>
              </div>
            </div>
          ) : null}

          {renderActiveTab()}
        </div>

        <ToastContainer />
      </main>
    </div>
  );
}
