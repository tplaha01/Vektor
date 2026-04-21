import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Globe,
  LineChart,
  Menu,
  Minus,
  Network,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Radio,
  RefreshCw,
  ScrollText,
  Settings,
  Shield,
  Sigma,
  TrendingUp,
  Workflow,
  X,
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
import { adminAPI, blogAPI, researchAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ToastContainer from '../components/common/Toast';
import KPIGrid from '../components/admin/KPIGrid';
import DecisionQueue from '../components/admin/DecisionQueue';
import RiskGauges from '../components/admin/RiskGauges';
import PositionsPanel from '../components/admin/PositionsPanel';
import LineagePanel from '../components/admin/LineagePanel';
import KnowledgeTraceGraph from '../components/admin/KnowledgeTraceGraph';

const badgeTone = (status) => {
  const normalized = String(status || '').toLowerCase();
  if (['healthy', 'provider', 'paper only', 'running', 'clear', 'ok', 'published', 'research'].includes(normalized)) return 'ok';
  if (['degraded', 'fallback', 'halted', 'error', 'down', 'blocked', 'failed', 'blog'].includes(normalized)) return 'bad';
  return 'wait';
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
  const diffMin = Math.round(diffMs / 60000);
  if (Math.abs(diffMin) < 1) return 'just now';
  if (Math.abs(diffMin) < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (Math.abs(diffHr) < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
};

const formatCountdown = (value, nowTs = Date.now()) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  const diffMs = date.getTime() - nowTs;
  const remaining = Math.abs(Math.round(diffMs / 1000));
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const label = `${minutes}m ${String(seconds).padStart(2, '0')}s`;
  return diffMs >= 0 ? `in ${label}` : `${label} ago`;
};

const summarizeText = (value, max = 220) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return 'No detail loaded yet.';
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const currency = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });

const percent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

const safeNumber = (value) => Number(value || 0);

const roleLabel = (role) =>
  String(role || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const TICKER_LABELS = {
  AAPL: 'Apple Inc.',
  AMD: 'Advanced Micro Devices',
  AMZN: 'Amazon.com',
  DIA: 'SPDR Dow Jones Industrial Average ETF',
  GLD: 'SPDR Gold Shares',
  GOOGL: 'Alphabet Class A',
  IWM: 'iShares Russell 2000 ETF',
  META: 'Meta Platforms',
  MSFT: 'Microsoft Corporation',
  NVDA: 'NVIDIA Corporation',
  QQQ: 'Invesco QQQ Trust',
  SLV: 'iShares Silver Trust',
  SPY: 'SPDR S&P 500 ETF',
  TLT: 'iShares 20+ Year Treasury Bond ETF',
  TSLA: 'Tesla Inc.',
  UNG: 'United States Natural Gas Fund',
  USO: 'United States Oil Fund',
  XLE: 'Energy Select Sector SPDR Fund',
  XLF: 'Financial Select Sector SPDR Fund',
  XLK: 'Technology Select Sector SPDR Fund',
};

const tickerFullName = (symbol) => {
  const normalized = String(symbol || '').trim().toUpperCase();
  if (!normalized) return 'Multi-asset context';
  return TICKER_LABELS[normalized] || normalized;
};

const jsonPreview = (value, max = 220) => summarizeText(JSON.stringify(value || {}), max);

const classifyResearch = (report) => {
  const title = String(report?.title || '').toLowerCase();
  const summary = String(report?.summary || '').toLowerCase();
  const findings = Array.isArray(report?.findings) ? report.findings.length : 0;
  if (title.includes('proposal') || summary.includes('proposal')) return 'Proposal Paper';
  if (title.includes('discovery') || summary.includes('discovery')) return 'Discovery Paper';
  if (report?.agent_role === 'researcher' || findings >= 4) return 'Case Study';
  return 'Signal Brief';
};

const deliverableHref = (kind, id) => {
  if (!id) return '#';
  if (kind === 'research') return `/research?report=${encodeURIComponent(id)}`;
  if (kind === 'blog') return `/blog?id=${encodeURIComponent(id)}`;
  return '#';
};

const STATUS_KEYS = [
  ['orchestration', 'Orchestration'],
  ['data_source', 'Data Source'],
  ['execution_mode', 'Execution Mode'],
  ['llm_agent_health', 'LLM Agent Health'],
];

const Admin = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('warroom');
  const [metrics, setMetrics] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [runtimeControl, setRuntimeControl] = useState(null);
  const [controlHistory, setControlHistory] = useState([]);
  const [knowledgeStats, setKnowledgeStats] = useState(null);
  const [workersStatus, setWorkersStatus] = useState(null);
  const [agentHierarchy, setAgentHierarchy] = useState(null);
  const [hierarchyStats, setHierarchyStats] = useState(null);
  const [activeTasks, setActiveTasks] = useState([]);
  const [taskHistory, setTaskHistory] = useState([]);
  const [knowledgeEvents, setKnowledgeEvents] = useState([]);
  const [lineageRows, setLineageRows] = useState([]);
  const [paperPositions, setPaperPositions] = useState([]);
  const [performanceSummary, setPerformanceSummary] = useState(null);
  const [performanceSnapshots, setPerformanceSnapshots] = useState([]);
  const [reports, setReports] = useState([]);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [nowTick, setNowTick] = useState(Date.now());
  const [controlBusy, setControlBusy] = useState('');
  const [kbBusy, setKbBusy] = useState('');
  const [contextBusy, setContextBusy] = useState(false);
  const [performanceBusy, setPerformanceBusy] = useState('');
  const [allocationSaving, setAllocationSaving] = useState(false);
  const [selectedContext, setSelectedContext] = useState(null);
  const [contextRailTab, setContextRailTab] = useState('focus');
  const [deliverableDrawerOpen, setDeliverableDrawerOpen] = useState(false);
  const [timelineIndex, setTimelineIndex] = useState(0);
  const [timelineRoleFilter, setTimelineRoleFilter] = useState('all');
  const [timelineRunFilter, setTimelineRunFilter] = useState('all');
  const [timelineSymbolFilter, setTimelineSymbolFilter] = useState('');
  const [timelineZoom, setTimelineZoom] = useState(8);
  const [taskTrailPage, setTaskTrailPage] = useState(1);
  const [treePanelOpen, setTreePanelOpen] = useState(true);
  const [allocationDraft, setAllocationDraft] = useState({
    totalCapitalUsd: 100000,
    reserveCashUsd: 10000,
    assetWeights: {
      equities: 55,
      options: 10,
      commodities: 10,
      forex: 10,
      crypto: 5,
      cash: 10,
    },
    sleeveWeights: {
      long_term: 50,
      recurring: 30,
      tactical: 20,
    },
    constraints: {
      min_cash_reserve_pct: 10,
      max_asset_class_exposure_pct: 60,
      max_options_notional_pct: 5,
      max_crypto_notional_pct: 5,
      max_forex_notional_pct: 10,
    },
  });
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  const navigationItems = [
    { id: 'warroom', label: 'War Room', icon: Workflow, description: 'CEO theater and command surface' },
    { id: 'agents', label: 'Agents', icon: Bot, description: 'Hierarchy, workers, swarm runtime' },
    { id: 'performance', label: 'Performance', icon: LineChart, description: 'Track record, alpha, drawdown' },
    { id: 'deliverables', label: 'KB', icon: FileText, description: 'Knowledge base documents, outputs, and lineage' },
    { id: 'decisions', label: 'Decisions', icon: TrendingUp, description: 'Pending approvals and lineage' },
    { id: 'risk', label: 'Risk', icon: Shield, description: 'Limits, controls, runtime status' },
    { id: 'positions', label: 'Positions', icon: Activity, description: 'Portfolio exposure and holdings' },
    { id: 'settings', label: 'Settings', icon: Settings, description: 'Runtime controls and KB policy' },
  ];

  const fetchAdminState = useCallback(async ({ manual = false } = {}) => {
    if (fetchInProgress.current) return;
    fetchInProgress.current = true;
    if (manual) setRefreshing(true);

    try {
      setConnectionStatus((prev) => (prev === 'connected' ? 'connected' : 'connecting'));
      const results = await Promise.allSettled([
        adminAPI.getMetricsSummary(),
        adminAPI.getSystemStatusBadges(),
        adminAPI.getRuntimeControlStatus(),
        adminAPI.getRuntimeControlHistory(20),
        adminAPI.getKnowledgeStats(),
        adminAPI.getFundWorkersStatus(),
        adminAPI.getAgentHierarchy(),
        adminAPI.getFundActiveTasks(),
        adminAPI.getFundTaskHistory(120),
        adminAPI.getFundKnowledgeEvents(60, 'development'),
        adminAPI.getRecentLineage(80),
        adminAPI.getPaperPositions(),
        adminAPI.getPerformanceSummary(),
        adminAPI.getPerformanceSnapshots({ limit: 240 }),
        researchAPI.getReports({ surface: 'kb', limit: 24 }),
        blogAPI.getPosts({ limit: 24 }),
      ]);

      if (!isMounted.current) return;

      const rejected = results.filter((result) => result.status === 'rejected');
      if (rejected.length === results.length) {
        throw new Error(String(rejected[0]?.reason?.message || 'backend_unreachable'));
      }

      const [
        metricsResult,
        systemResult,
        runtimeResult,
        historyResult,
        knowledgeResult,
        workersResult,
        hierarchyResult,
        tasksResult,
        taskHistoryResult,
        knowledgeEventsResult,
        lineageResult,
        positionsResult,
        performanceSummaryResult,
        performanceSnapshotsResult,
        reportsResult,
        postsResult,
      ] = results;

      if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value);
      if (systemResult.status === 'fulfilled') setSystemStatus(systemResult.value);
      if (runtimeResult.status === 'fulfilled') setRuntimeControl(runtimeResult.value);
      if (historyResult.status === 'fulfilled') setControlHistory(adminAPI.normalizeArray(historyResult.value, 'rows'));
      if (knowledgeResult.status === 'fulfilled') setKnowledgeStats(knowledgeResult.value);
      if (workersResult.status === 'fulfilled') setWorkersStatus(workersResult.value);
      if (hierarchyResult.status === 'fulfilled') {
        setAgentHierarchy(hierarchyResult.value?.hierarchy || null);
        setHierarchyStats(hierarchyResult.value?.stats || null);
      }
      if (tasksResult.status === 'fulfilled') setActiveTasks(adminAPI.normalizeArray(tasksResult.value, 'tasks'));
      if (taskHistoryResult.status === 'fulfilled') setTaskHistory(adminAPI.normalizeArray(taskHistoryResult.value, 'history'));
      if (knowledgeEventsResult.status === 'fulfilled') setKnowledgeEvents(adminAPI.normalizeArray(knowledgeEventsResult.value, 'events'));
      if (lineageResult.status === 'fulfilled') setLineageRows(adminAPI.normalizeArray(lineageResult.value, 'rows'));
      if (positionsResult.status === 'fulfilled') setPaperPositions(adminAPI.normalizeArray(positionsResult.value, 'value'));
      if (performanceSummaryResult.status === 'fulfilled') setPerformanceSummary(performanceSummaryResult.value);
      if (performanceSnapshotsResult.status === 'fulfilled') setPerformanceSnapshots(adminAPI.normalizeArray(performanceSnapshotsResult.value, 'snapshots'));
      if (reportsResult.status === 'fulfilled') setReports(adminAPI.normalizeArray(reportsResult.value, 'reports'));
      if (postsResult.status === 'fulfilled') setPosts(adminAPI.normalizeArray(postsResult.value, 'posts'));

      setConnectionStatus('connected');
      setLastUpdate(new Date());
      setLoading(false);
      if (manual) success('Admin panel refreshed');
    } catch (err) {
      if (!isMounted.current) return;
      console.error('Failed to fetch admin state:', err);
      setConnectionStatus('error');
      setLoading(false);
      if (manual) showError(`Refresh failed: ${err.message}`);
    } finally {
      fetchInProgress.current = false;
      setRefreshing(false);
    }
  }, [showError, success]);

  useEffect(() => {
    isMounted.current = true;
    fetchAdminState();
    const interval = setInterval(() => fetchAdminState(), 20000);
    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, [fetchAdminState]);

  useEffect(() => {
    const interval = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const policy = systemStatus?.allocation_policy?.policy;
    if (!policy) return;
    setAllocationDraft({
      totalCapitalUsd: Number(policy.total_capital_usd || 100000),
      reserveCashUsd: Number(policy.reserve_cash_usd || 0),
      assetWeights: {
        equities: Number(policy.asset_weights?.equities || 0) * 100,
        options: Number(policy.asset_weights?.options || 0) * 100,
        commodities: Number(policy.asset_weights?.commodities || 0) * 100,
        forex: Number(policy.asset_weights?.forex || 0) * 100,
        crypto: Number(policy.asset_weights?.crypto || 0) * 100,
        cash: Number(policy.asset_weights?.cash || 0) * 100,
      },
      sleeveWeights: {
        long_term: Number(policy.sleeve_weights?.long_term || 0) * 100,
        recurring: Number(policy.sleeve_weights?.recurring || 0) * 100,
        tactical: Number(policy.sleeve_weights?.tactical || 0) * 100,
      },
      constraints: {
        min_cash_reserve_pct: Number(policy.constraints?.min_cash_reserve_pct || 0) * 100,
        max_asset_class_exposure_pct: Number(policy.constraints?.max_asset_class_exposure_pct || 0) * 100,
        max_options_notional_pct: Number(policy.constraints?.max_options_notional_pct || 0) * 100,
        max_crypto_notional_pct: Number(policy.constraints?.max_crypto_notional_pct || 0) * 100,
        max_forex_notional_pct: Number(policy.constraints?.max_forex_notional_pct || 0) * 100,
      },
    });
  }, [systemStatus]);

  const haltRecoveryChecklist = Array.isArray(systemStatus?.halt?.recovery_checklist)
    ? systemStatus.halt.recovery_checklist
    : [];

  const workerRows = useMemo(() => {
    const workers = Array.isArray(workersStatus?.workers) ? workersStatus.workers : [];
    return workers
      .map((worker, index) => ({
        id: worker.agent_id || `${worker.role || 'worker'}-${index}`,
        role: worker.role || 'unknown',
        status: worker.running ? 'running' : worker.started ? 'idle' : 'stopped',
        completed: Number(worker.completed_count || 0),
        failed: Number(worker.failed_count || 0),
        blocked: Number(worker.blocked_count || 0),
        lastHeartbeat: worker.last_heartbeat_at || null,
        lastTaskId: worker.last_task_id || '',
        lastError: worker.last_error || '',
      }))
      .sort((a, b) => (b.completed + b.failed) - (a.completed + a.failed));
  }, [workersStatus]);

  const activeTaskMap = useMemo(() => {
    const map = new Map();
    activeTasks.forEach((task) => {
      const role = String(task.role || task.agent_id || '').trim();
      if (!role || map.has(role)) return;
      map.set(role, task);
    });
    return map;
  }, [activeTasks]);

  const reportDeliverables = useMemo(
    () =>
      reports
        .map((report) => ({
          id: report.report_id,
          kind: 'research',
          type: 'KB Document',
          title: report.title,
          subtitle: `${report.agent_role || report.agent_id || 'agent'} | ${String(report.asset_universe?.[0] || 'multi-asset').toUpperCase()}`,
          detail: [
            `${Math.round(Number(report.confidence || 0) * 100)}% confidence`,
            report.provider_used,
            report.model_used,
          ].filter(Boolean).join(' · '),
          timestamp: report.published_at || report.created_at,
          href: report.surface === 'public' ? deliverableHref('research', report.report_id) : '',
          preview: summarizeText(report.summary || report.thesis || report.executive_summary, 180),
          metaBadges: [report.provider_used, report.model_used].filter(Boolean),
          data: report,
        }))
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    [reports]
  );

  const blogDeliverables = useMemo(
    () =>
      posts
        .map((post) => ({
          id: post.id,
          kind: 'blog',
          type: 'Blog',
          title: post.title,
          subtitle: `${post.category || 'Research'} | ${post.author_role || 'editorial'}`,
          detail: [
            `${Number(post.views || 0)} views`,
            post.providerUsed,
            post.modelUsed,
          ].filter(Boolean).join(' · '),
          timestamp: post.published_at || post.created_at,
          href: deliverableHref('blog', post.id),
          preview: summarizeText(post.excerpt || post.summary || post.content, 180),
          metaBadges: [post.providerUsed, post.modelUsed].filter(Boolean),
        }))
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    [posts]
  );

  const missionStats = [
    {
      label: 'Active Tasks',
      value: activeTasks.length,
      detail: `${workerRows.filter((row) => row.status === 'running').length} workers live`,
    },
    {
      label: 'Runtime KB',
      value: knowledgeStats?.event_count ?? 'n/a',
      detail: `${knowledgeStats?.canonical_store || 'sqlite'} canonical`,
    },
    {
      label: 'Research',
      value: reportDeliverables.length,
      detail: `${blogDeliverables.length} blogs available`,
    },
    {
      label: 'Last Sync',
      value: formatRelative(lastUpdate),
      detail: connectionStatus === 'connected' ? 'backend live' : 'connection degraded',
    },
  ];

  const sidebarCounts = useMemo(() => ({
    warroom: activeTasks.length,
    agents: workerRows.length,
    performance: Number(performanceSummary?.snapshot_count ?? 0),
    deliverables: reportDeliverables.length + blogDeliverables.length,
    decisions: Number(metrics?.decisionQueue?.pending ?? 0),
    risk: Number(systemStatus?.halt?.halted ? 1 : 0),
    positions: Number(metrics?.portfolio?.positions ?? metrics?.portfolio?.holdings ?? 0),
    settings: Number(controlHistory.length || 0),
  }), [activeTasks.length, blogDeliverables.length, controlHistory.length, metrics, performanceSummary?.snapshot_count, reportDeliverables.length, systemStatus, workerRows.length]);

  const broadcastRows = useMemo(
    () =>
      workerRows.map((worker) => {
        const task = activeTaskMap.get(worker.role);
        const symbol = String(task?.payload?.symbol || task?.details?.symbol || '').toUpperCase();
        return {
          ...worker,
          symbol: symbol || 'multi-asset',
          command: task?.payload?.command || task?.event || 'Monitoring queue',
          runId: task?.run_id || '',
          taskStatus: task?.status || worker.status,
          taskId: task?.task_id || worker.lastTaskId || '',
        };
      }),
    [activeTaskMap, workerRows]
  );

  const paperSummary = useMemo(() => {
    const positions = Array.isArray(paperPositions) ? paperPositions : [];
    const equity = positions.reduce((sum, row) => sum + safeNumber(row.market_value), 0);
    const unrealized = positions.reduce((sum, row) => sum + safeNumber(row.unrealized_pnl), 0);
    const biggestWinner = [...positions].sort((a, b) => safeNumber(b.unrealized_pnl) - safeNumber(a.unrealized_pnl))[0] || null;
    const biggestLoser = [...positions].sort((a, b) => safeNumber(a.unrealized_pnl) - safeNumber(b.unrealized_pnl))[0] || null;
    return {
      equity,
      unrealized,
      count: positions.length,
      biggestWinner,
      biggestLoser,
    };
  }, [paperPositions]);

  const orderedPerformanceSnapshots = useMemo(
    () =>
      [...performanceSnapshots]
        .filter((row) => row && row.recorded_at)
        .sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()),
    [performanceSnapshots]
  );

  const performanceCurveRows = useMemo(() => {
    const dailyRows = orderedPerformanceSnapshots.filter((row) => row.snapshot_kind === 'daily');
    const baseRows = dailyRows.length >= 2 ? dailyRows : orderedPerformanceSnapshots;
    return baseRows.map((row) => {
      const primaryBenchmark = Array.isArray(row.benchmarks) ? row.benchmarks[0] : null;
      return {
        id: row.snapshot_id,
        recordedAt: row.recorded_at,
        label: new Date(row.recorded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        equity: safeNumber(row.equity),
        totalPnl: safeNumber(row.total_pnl),
        benchmarkReturnPct: safeNumber(primaryBenchmark?.return_pct),
      };
    });
  }, [orderedPerformanceSnapshots]);

  const performanceLatest = performanceSummary?.latest_snapshot || null;
  const performanceTrackRecord = performanceSummary?.track_record || {};
  const performanceBenchmarks = Array.isArray(performanceLatest?.benchmarks) ? performanceLatest.benchmarks : [];
  const performanceRecentSnapshots = useMemo(
    () => [...orderedPerformanceSnapshots].reverse().slice(0, 16),
    [orderedPerformanceSnapshots]
  );

  const taskHistoryRows = useMemo(
    () =>
      [...taskHistory]
        .sort((a, b) => new Date(b.ts || b.created_at || 0).getTime() - new Date(a.ts || a.created_at || 0).getTime())
        .map((entry, index) => {
          const symbol = String(entry.details?.symbol || entry.payload?.symbol || entry.details?.asset || 'multi-asset').toUpperCase();
          const nextAttemptAt = entry.details?.next_attempt_at || entry.payload?._scheduler?.next_attempt_at || '';
          const retryCount = Number(entry.details?.retry_count || entry.payload?._scheduler?.retry_count || 0);
          const deferReason = entry.details?.reason || '';
          return {
            id: entry.task_id || `${entry.run_id || 'run'}-${index}`,
            taskId: entry.task_id || '',
            role: entry.role || entry.agent_id || 'unknown',
            status: entry.status || 'unknown',
            event: entry.event || 'status_update',
            runId: entry.run_id || '',
            symbol,
            symbolName: tickerFullName(symbol),
            timestamp: entry.ts || entry.created_at,
            detail: entry.payload?.command || entry.details?.status || jsonPreview(entry.details, 120),
            nextAttemptAt,
            retryCount,
            deferReason,
            raw: entry,
          };
        }),
    [taskHistory]
  );

  const deferredTaskCount = useMemo(
    () =>
      activeTasks.filter((task) => {
        const nextAttemptAt = task?.payload?._scheduler?.next_attempt_at;
        if (!nextAttemptAt) return false;
        const date = new Date(nextAttemptAt);
        return !Number.isNaN(date.getTime()) && date.getTime() > Date.now();
      }).length,
    [activeTasks]
  );

  const allocationRows = useMemo(
    () =>
      Object.entries(systemStatus?.allocation_policy?.asset_classes || {}).map(([assetClass, row]) => ({
        assetClass,
        allocated: Number(row?.allocated_usd || 0),
        used: Number(row?.used_usd || 0),
        remaining: Number(row?.remaining_usd || 0),
        weight: Number(row?.weight || 0),
      })),
    [systemStatus]
  );

  const discoveryRows = useMemo(
    () => Array.isArray(systemStatus?.discovery?.top) ? systemStatus.discovery.top : [],
    [systemStatus]
  );

  const swarmActiveContexts = useMemo(
    () => Array.isArray(systemStatus?.swarm_snapshot?.active_contexts) ? systemStatus.swarm_snapshot.active_contexts : [],
    [systemStatus]
  );

  const scheduledWaveRows = useMemo(
    () =>
      Array.isArray(workersStatus?.swarm_waves)
        ? workersStatus.swarm_waves.map((wave, index) => ({
            id: `${wave.run_id || 'run'}-${wave.wave_index || index}`,
            runId: wave.run_id,
            title: `Wave ${wave.wave_index || index + 1}/${wave.total_waves || '?'}`,
            subtitle: (wave.symbols || []).join(', ') || 'no symbols',
            detail: `Dispatch ${formatDateTime(wave.scheduled_for)} (${formatCountdown(wave.scheduled_for, nowTick)})`,
            status: new Date(wave.scheduled_for).getTime() <= nowTick ? 'running' : 'queued',
            data: wave,
          }))
        : [],
    [workersStatus, nowTick]
  );

  const signalPackRows = useMemo(
    () =>
      Array.isArray(workersStatus?.signal_packs)
        ? workersStatus.signal_packs.map((pack) => ({
            id: pack.signal_pack_id,
            title: `${pack.symbol} pack`,
            subtitle: `${pack.completed_roles?.length || 0}/${pack.expected_roles?.length || 0} specialists complete`,
            detail: pack.status === 'canceled'
              ? `Canceled ${formatRelative(pack.canceled_at)}`
              : pack.dispatched
                ? `Dispatched to fund manager`
                : `Waiting for ${Math.max((pack.expected_roles?.length || 0) - (pack.completed_roles?.length || 0), 0)} roles`,
            status: pack.status || (pack.dispatched ? 'running' : 'queued'),
            data: pack,
          }))
        : [],
    [workersStatus]
  );

  const nextProviderWindow = useMemo(() => {
    const providers = workersStatus?.ai_role_adapter?.providers || {};
    const candidates = Object.entries(providers)
      .map(([name, provider]) => {
        const cooldownRemaining = Number(provider?.cooldown_remaining_seconds || 0);
        const windowRemaining = Number(provider?.window_remaining_seconds || 0);
        const budgeted =
          provider?.quota_state === 'budget_window_exhausted' ||
          (Number(provider?.requests_per_window || 0) > 0 &&
            Number(provider?.requests_in_window || 0) >= Number(provider?.requests_per_window || 0)) ||
          (Number(provider?.tokens_per_window || 0) > 0 &&
            Number(provider?.estimated_tokens_in_window || 0) >= Number(provider?.tokens_per_window || 0));
        const nextSeconds = budgeted && windowRemaining > 0
          ? windowRemaining
          : cooldownRemaining > 0
            ? cooldownRemaining
            : 0;
        return {
          name,
          nextSeconds,
          budgeted,
          cooldownRemaining,
          windowRemaining,
        };
      })
      .filter((item) => item.nextSeconds > 0)
      .sort((a, b) => a.nextSeconds - b.nextSeconds);

    if (!candidates.length) {
      return {
        provider: 'all providers',
        label: 'open now',
        detail: 'No active cooldown or budget window',
      };
    }

    const next = candidates[0];
    const resetAt = new Date(Date.now() + next.nextSeconds * 1000);
    return {
      provider: next.name,
      label: `${Math.ceil(next.nextSeconds)}s`,
      detail: `${next.budgeted ? 'budget window' : 'cooldown'} until ${resetAt.toLocaleTimeString()}`,
    };
  }, [workersStatus]);

  const overviewRows = useMemo(
    () =>
      broadcastRows.map((worker) => ({
        ...worker,
        focus: worker.command,
        tickerName: tickerFullName(worker.symbol),
        overview: worker.taskId
          ? `Task ${worker.taskId.slice(0, 8)} ${worker.taskStatus}. ${worker.completed} completed, ${worker.failed} failed.`
          : `No active claim. ${worker.completed} completed tasks recorded.`,
      })),
    [broadcastRows]
  );

  const signalPackDeliverables = useMemo(
    () =>
      (workersStatus?.signal_packs || []).map((pack) => ({
        id: pack.signal_pack_id,
        kind: 'signalpack',
        type: 'JSON Packet',
        title: `${pack.symbol} signal pack`,
        subtitle: `${pack.completed_roles?.length || 0}/${pack.expected_roles?.length || 0} specialist roles complete`,
        detail: `Run ${pack.run_id || 'n/a'} · report ${String(pack.composite_report_id || '').slice(0, 8) || 'pending'}`,
        timestamp: workersStatus?.autopilot?.last_run_at || lastUpdate.toISOString(),
        preview: jsonPreview(pack, 240),
        data: pack,
      })),
    [lastUpdate, workersStatus]
  );

  const mlMathDeliverables = useMemo(
    () =>
      taskHistoryRows
        .filter((row) => row.role === 'ml_timeseries_analyst')
        .slice(0, 8)
        .map((row) => ({
          id: `ml-${row.id}`,
          kind: 'mlmath',
          type: 'ML Math',
          title: `${row.symbol} model packet`,
          subtitle: row.symbolName,
          detail: row.detail,
          timestamp: row.timestamp,
          preview: jsonPreview(row.raw?.details || row.raw?.payload, 260),
          data: row.raw,
        })),
    [taskHistoryRows]
  );

  const recentTaskRows = useMemo(
    () =>
      activeTasks.slice(0, 8).map((task) => ({
        id: task.task_id,
        kind: 'task',
        title: task.role || task.agent_id || 'task',
        subtitle: `symbol: ${String(task.payload?.symbol || task.details?.symbol || 'multi-asset').toUpperCase()}`,
        detail: task.payload?.command || task.event || 'Active task',
        status: task.status,
        timestamp: task.ts || task.created_at,
        data: task,
      })),
    [activeTasks]
  );

  const hierarchyTree = useMemo(() => {
    const fundManager = agentHierarchy?.fund_manager || null;
    const executiveGroups = Array.isArray(agentHierarchy?.executives) ? agentHierarchy.executives : [];
    const researchGroup = executiveGroups.find((group) => group?.research_director);
    const researchDirector = researchGroup?.research_director || null;
    const analysts = Array.isArray(researchGroup?.analysts) ? researchGroup.analysts.filter(Boolean) : [];
    const tradingDirector = executiveGroups.find((group) => group?.trading_director)?.trading_director || null;
    const riskAuditor = executiveGroups.find((group) => group?.risk_auditor)?.risk_auditor || null;
    const complianceOps = executiveGroups.find((group) => group?.compliance_ops)?.compliance_ops || null;
    const blogWriter = Array.isArray(agentHierarchy?.support) ? agentHierarchy.support[0] : null;
    const traderWorker = broadcastRows.find((worker) => worker.role === 'trader') || null;

    const enrichNode = (key, label, data, children = []) => {
      const liveTask = activeTaskMap.get(data?.role || key) || activeTasks.find((task) => task.agent_id === data?.agent_id) || null;
      const symbol = String(liveTask?.payload?.symbol || liveTask?.details?.symbol || '').toUpperCase();
      return {
        key,
        label,
        data,
        children,
        status: data?.status || (children.some((child) => child.status === 'running') ? 'running' : 'idle'),
        symbol: symbol || 'multi-asset',
        symbolName: tickerFullName(symbol),
        focus: data?.current_activity || liveTask?.payload?.command || liveTask?.event || 'Monitoring queue',
      };
    };

    const analystNodes = analysts.map((agent) => enrichNode(agent.role, roleLabel(agent.role), agent));
    const traderNode = enrichNode(
      'trader',
      'Trader',
      traderWorker
        ? {
            role: 'trader',
            status: traderWorker.taskStatus || traderWorker.status,
            current_activity: traderWorker.command,
            agent_id: traderWorker.id,
          }
        : {
            role: 'trader',
            status: 'idle',
            current_activity: 'Awaiting approved execution',
          },
    );
    const researchNode = enrichNode('research_director', 'Research Director', researchDirector, analystNodes);
    const tradingNode = enrichNode('trading_director', 'Trading Director', tradingDirector, [traderNode]);
    const riskNode = enrichNode('risk_auditor', 'Risk Auditor', riskAuditor);
    const complianceNode = enrichNode('compliance_ops', 'Compliance Ops', complianceOps);
    const blogNode = enrichNode('blog_writer', 'Blog Writer', blogWriter);
    const fundNode = enrichNode('fund_manager', 'Fund Manager', fundManager);
    const openClawNode = enrichNode(
      'openclaw',
      'OpenClaw Orchestrator',
      {
        role: 'openclaw',
        status: runtimeControl?.runtime_started ? 'running' : 'stopped',
        current_activity: workersStatus?.autopilot?.enabled
          ? `Autopilot ${workersStatus?.autopilot?.running ? 'running' : 'armed'}`
          : 'Manual orchestration mode',
      },
    );
    const ceoNode = enrichNode('ceo', 'CEO', {
      role: 'ceo',
      status: connectionStatus === 'connected' ? 'running' : connectionStatus === 'connecting' ? 'idle' : 'error',
      current_activity: 'Issuing mandate, constraints, and approvals',
    });

    return {
      ceo: ceoNode,
      openclaw: openClawNode,
      fundManager: fundNode,
      supervisors: [researchNode, tradingNode, riskNode, complianceNode, blogNode],
    };
  }, [activeTaskMap, activeTasks, agentHierarchy, broadcastRows, connectionStatus, runtimeControl, workersStatus]);

  const swarmTimeline = useMemo(() => {
    const taskChronology = taskHistory
      .map((event, index) => {
        const timestamp = event.timestamp || event.ts || event.created_at || '';
        return {
          id: event.task_id || `task-${index}`,
          source: 'task',
          role: event.role || event.agent_id || 'agent',
          symbol: String(event.details?.symbol || event.payload?.symbol || 'multi-asset').toUpperCase(),
          status: event.status || 'unknown',
          phase: event.event || event.payload?.command || 'task event',
          runId: event.run_id || '',
          taskId: event.task_id || '',
          heartbeat: timestamp,
          intensity: event.status === 'running' ? 'high' : event.status === 'completed' ? 'medium' : 'low',
          ts: timestamp,
          data: event,
        };
      })
      .filter((item) => item.ts)
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

    const knowledgeChronology = knowledgeEvents
      .map((event, index) => {
        const timestamp = event.occurred_at || event.event_ts || event.ts || event.created_at || '';
        const payload = event.payload && typeof event.payload === 'object' ? event.payload : {};
        return {
          id: event.id || event.event_id || `knowledge-${index}`,
          source: 'knowledge',
          role: String(payload.role || payload.agent_role || payload.agent_id || event.namespace || 'memory'),
          symbol: String(payload.symbol || payload.asset || payload.topic || 'context').toUpperCase(),
          status: 'recorded',
          phase: event.event_type || event.type || event.namespace || 'knowledge event',
          runId: String(payload.run_id || ''),
          taskId: String(payload.task_id || ''),
          heartbeat: timestamp,
          intensity: 'low',
          ts: timestamp,
          data: event,
        };
      })
      .filter((item) => item.ts)
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

    return [...taskChronology, ...knowledgeChronology]
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
      .slice(-18);
  }, [knowledgeEvents, taskHistory]);

  const timelineRoleOptions = useMemo(
    () => ['all', ...Array.from(new Set(swarmTimeline.map((item) => item.role).filter(Boolean)))],
    [swarmTimeline]
  );

  const timelineRunOptions = useMemo(
    () => ['all', ...Array.from(new Set(swarmTimeline.map((item) => item.runId).filter(Boolean)))],
    [swarmTimeline]
  );

  const filteredSwarmTimeline = useMemo(() => {
    let items = [...swarmTimeline];
    if (timelineRoleFilter !== 'all') {
      items = items.filter((item) => item.role === timelineRoleFilter);
    }
    if (timelineRunFilter !== 'all') {
      items = items.filter((item) => item.runId === timelineRunFilter);
    }
    if (timelineSymbolFilter.trim()) {
      const query = timelineSymbolFilter.trim().toUpperCase();
      items = items.filter((item) => String(item.symbol || '').includes(query));
    }
    const zoomCount = Math.max(4, Math.min(18, timelineZoom));
    return items.slice(-zoomCount);
  }, [swarmTimeline, timelineRoleFilter, timelineRunFilter, timelineSymbolFilter, timelineZoom]);

  useEffect(() => {
    if (!filteredSwarmTimeline.length) {
      setTimelineIndex(0);
      return;
    }
    setTimelineIndex(filteredSwarmTimeline.length - 1);
  }, [filteredSwarmTimeline]);

  useEffect(() => {
    if (selectedContext) return;
    if (reportDeliverables[0]) {
      setSelectedContext({
        kind: 'research',
        id: reportDeliverables[0].id,
        title: reportDeliverables[0].title,
        subtitle: reportDeliverables[0].subtitle,
        preview: reportDeliverables[0].preview,
        href: reportDeliverables[0].href,
      });
      return;
    }
    if (broadcastRows[0]) {
      setSelectedContext({
        kind: 'worker',
        id: broadcastRows[0].id,
        title: broadcastRows[0].role,
        subtitle: `${broadcastRows[0].symbol} | ${broadcastRows[0].taskStatus}`,
        preview: broadcastRows[0].command,
        data: broadcastRows[0],
      });
    }
  }, [broadcastRows, reportDeliverables, selectedContext]);

  const openWorkerContext = useCallback((worker) => {
    setContextRailTab('focus');
    setSelectedContext({
      kind: 'worker',
      id: worker.id,
      title: worker.role,
      subtitle: `${worker.symbol} | ${worker.taskStatus}`,
      preview: worker.command,
      data: worker,
    });
  }, []);

  const openTaskContext = useCallback((task) => {
    setContextRailTab('focus');
    setSelectedContext({
      kind: 'task',
      id: task.task_id,
      title: task.role || task.agent_id || 'task',
      subtitle: String(task.payload?.symbol || task.details?.symbol || 'multi-asset').toUpperCase(),
      preview: task.payload?.command || task.event || 'Task in progress',
      data: task,
    });
  }, []);

  const openTimelineContext = useCallback((item, index) => {
    setTimelineIndex(index);
    setContextRailTab('focus');
    setSelectedContext({
      kind: item.source === 'task' ? 'task' : 'timeline',
      id: item.id,
      title: item.role,
      subtitle: `${item.symbol} | ${item.phase}`,
      preview: item.phase,
      data: item.source === 'task' ? item.data : item,
    });
  }, []);

  const openTreeNode = useCallback((node) => {
    setContextRailTab('focus');
    setSelectedContext({
      kind: 'timeline',
      id: node.key,
      title: node.label,
      subtitle: `${node.symbol} | ${node.status}`,
      preview: node.focus,
      data: node,
    });
  }, []);

  const openDeliverable = useCallback(async (item) => {
    if (!item?.id) return;
    setContextBusy(true);
    setContextRailTab('focus');
    setDeliverableDrawerOpen(true);
    setSelectedContext({
      kind: item.kind,
      id: item.id,
      title: item.title,
      subtitle: item.subtitle,
      preview: item.preview,
      href: item.href,
      loading: true,
    });
    try {
      const detail = item.kind === 'research'
        ? await researchAPI.getReportDetail(item.id)
        : await blogAPI.getPostDetail(item.id);
      const lineageRow = lineageRows.find((row) => {
        const reportIds = Array.isArray(row.report_ids) ? row.report_ids : [];
        const blogIds = Array.isArray(row.blog_post_ids) ? row.blog_post_ids : [];
        if (item.kind === 'research') return reportIds.includes(item.id);
        const sourceReportId = detail?.sourceReportId || detail?.metadata?.report_id;
        return blogIds.includes(item.id) || (sourceReportId ? reportIds.includes(sourceReportId) : false);
      });
      let auditDetail = null;
      const resolvedRunId = detail?.sourceRunId || detail?.run_id || lineageRow?.run_id || null;
      if (resolvedRunId) {
        try {
          auditDetail = await adminAPI.getLineageRunDetail(resolvedRunId, 120);
        } catch (auditErr) {
          console.warn('Failed to load lineage detail for deliverable:', auditErr);
        }
      }
      setSelectedContext({
        kind: item.kind,
        id: item.id,
        title: item.title,
        subtitle: item.subtitle,
        preview: item.preview,
        href: item.href,
        loading: false,
        data: detail || null,
        lineageSummary: lineageRow || null,
        auditDetail,
      });
    } catch (err) {
      console.error('Failed to load deliverable detail:', err);
      showError(`Failed to load ${item.kind}: ${err.message}`);
      setSelectedContext((prev) => ({
        ...prev,
        loading: false,
        error: err.message,
      }));
    } finally {
      setContextBusy(false);
    }
  }, [lineageRows, showError]);

  const openArtifactContext = useCallback((item) => {
    setDeliverableDrawerOpen(false);
    setContextRailTab('focus');
    setSelectedContext({
      kind: 'timeline',
      id: item.id,
      title: item.title,
      subtitle: item.subtitle,
      preview: item.preview,
      data: {
        source: item.type,
        role: item.type,
        symbol: item.title,
        status: 'recorded',
        phase: item.detail,
        ts: item.timestamp,
        payload: item.data,
      },
    });
  }, []);

  const runControlAction = async (action) => {
    if (controlBusy) return;
    try {
      if (action === 'pause') {
        const confirmed = window.confirm('Pause runtime workers and autopilot now?');
        if (!confirmed) return;
      }
      setControlBusy(action);
      if (action === 'pause') await adminAPI.pauseRuntime('ceo_admin_pause');
      if (action === 'resume') await adminAPI.resumeRuntime('ceo_admin_resume');
      if (action === 'clear_halt') await adminAPI.clearSystemHalt('ceo_admin_clear_halt');
      if (action === 'kick_autopilot') await adminAPI.kickAutopilot('');
      success(`Action complete: ${action}`);
      await fetchAdminState();
    } catch (err) {
      showError(`Control action failed: ${err.message}`);
    } finally {
      setControlBusy('');
    }
  };

  const runKnowledgeAction = async (action) => {
    if (kbBusy) return;
    try {
      if (action === 'reset') {
        const confirmed = window.confirm('Reset the Vektor runtime KB now?');
        if (!confirmed) return;
      }
      setKbBusy(action);
      if (action === 'reset') {
        await adminAPI.resetKnowledgeBase({ agent_id: 'ceo', seed_event: false });
      } else {
        await adminAPI.rebuildKnowledgeProjection({ agent_id: 'ceo', seed_event: false });
      }
      success(action === 'reset' ? 'Runtime KB reset' : 'Knowledge projection rebuilt');
      await fetchAdminState();
    } catch (err) {
      showError(`Knowledge action failed: ${err.message}`);
    } finally {
      setKbBusy('');
    }
  };

  const runPerformanceAction = async (action) => {
    if (performanceBusy) return;
    try {
      if (action === 'initialize_inception') {
        const confirmed = window.confirm('Reset the paper broker, clear prior performance history, and create a new inception snapshot?');
        if (!confirmed) return;
      }
      if (action === 'reset_history') {
        const confirmed = window.confirm('Clear stored performance history without resetting the broker ledger?');
        if (!confirmed) return;
      }
      setPerformanceBusy(action);
      if (action === 'initialize_inception') {
        await adminAPI.resetCleanInception({
          startingCashUsd: 100000,
          reason: 'clean_inception_reset',
        });
      } else if (action === 'capture_checkpoint') {
        await adminAPI.capturePerformanceSnapshot({
          snapshotKind: 'manual',
          reason: 'admin_manual_checkpoint',
        });
      } else if (action === 'reset_history') {
        await adminAPI.resetPerformanceHistory();
      }
      success(
        action === 'initialize_inception'
          ? 'Clean inception initialized'
          : action === 'capture_checkpoint'
            ? 'Performance checkpoint captured'
            : 'Performance history cleared'
      );
      await fetchAdminState();
    } catch (err) {
      showError(`Performance action failed: ${err.message}`);
    } finally {
      setPerformanceBusy('');
    }
  };

  const updateAllocationDraftGroup = (group, key, value) => {
    setAllocationDraft((prev) => ({
      ...prev,
      [group]: {
        ...prev[group],
        [key]: Number(value),
      },
    }));
  };

  const saveAllocationPolicy = async () => {
    if (allocationSaving) return;
    try {
      setAllocationSaving(true);
      const runId =
        systemStatus?.allocation_policy?.policy?.run_id ||
        workersStatus?.autopilot?.last_run_id ||
        activeTasks?.[0]?.run_id ||
        'run-ceo-allocation';
      const normalizeWeights = (source) =>
        Object.fromEntries(Object.entries(source).map(([key, value]) => [key, Math.max(0, Number(value || 0)) / 100]));
      await adminAPI.updateAllocationPolicy({
        run_id: runId,
        agent_id: 'ceo',
        total_capital_usd: Number(allocationDraft.totalCapitalUsd || 0),
        reserve_cash_usd: Number(allocationDraft.reserveCashUsd || 0),
        asset_weights: normalizeWeights(allocationDraft.assetWeights),
        sleeve_weights: normalizeWeights(allocationDraft.sleeveWeights),
        constraints: normalizeWeights(allocationDraft.constraints),
        metadata: { source: 'admin_crm' },
      });
      success('Allocation policy updated');
      await fetchAdminState();
    } catch (err) {
      showError(`Allocation update failed: ${err.message}`);
    } finally {
      setAllocationSaving(false);
    }
  };

  const renderFeedRows = (rows, emptyText, options = {}) => {
    const { selectable = false, onSelect = null, selectedId = null, openLabel = 'Open' } = options;
    if (!rows.length) {
      return <div className="theater-empty">{emptyText}</div>;
    }
    return (
      <div className="theater-feed-list">
        {rows.map((row) => {
          const content = (
            <>
              <div className="theater-feed-copy">
                <strong>{row.title || row.role || row.id}</strong>
                <span>{row.subtitle || row.meta || row.detail || 'n/a'}</span>
                {row.detail && row.subtitle ? <small className="theater-feed-detail">{row.detail}</small> : null}
              </div>
              <div className="theater-feed-meta">
                {row.type ? <span className={`ops-role-chip ops-role-chip-${badgeTone(row.type === 'Blog' ? 'wait' : 'ok')}`}>{row.type}</span> : null}
                {row.status ? <span className={`ops-role-chip ops-role-chip-${badgeTone(row.status)}`}>{row.status}</span> : null}
                {Array.isArray(row.metaBadges) ? row.metaBadges.slice(0, 2).map((badge) => (
                  <span key={`${row.id}-${badge}`} className="ops-role-chip ops-role-chip-wait">{badge}</span>
                )) : null}
                <small>{row.timestamp || row.lastHeartbeat ? formatRelative(row.timestamp || row.lastHeartbeat) : row.detail}</small>
              </div>
            </>
          );
          if (!selectable || typeof onSelect !== 'function') {
            return (
              <div key={`${row.kind || row.type || 'row'}-${row.id}`} className="theater-feed-row">
                {content}
              </div>
            );
          }
          return (
            <button
              key={`${row.kind || row.type || 'row'}-${row.id}`}
              type="button"
              className={`theater-feed-row theater-feed-row-action ${selectedId === row.id ? 'active' : ''}`}
              onClick={() => onSelect(row)}
            >
              {content}
              <span className="theater-feed-open">{openLabel}<ChevronRight size={14} /></span>
            </button>
          );
        })}
      </div>
    );
  };

  const filteredTaskTrailRows = taskHistoryRows
    .filter((row) => timelineRoleFilter === 'all' || row.role === timelineRoleFilter)
    .filter((row) => timelineRunFilter === 'all' || row.runId === timelineRunFilter)
    .filter((row) => !timelineSymbolFilter.trim() || row.symbol.includes(timelineSymbolFilter.trim().toUpperCase()));
  const TASKS_PER_PAGE = 12;
  const taskTrailTotalPages = Math.max(1, Math.ceil(filteredTaskTrailRows.length / TASKS_PER_PAGE));
  const paginatedTaskTrail = filteredTaskTrailRows.slice((taskTrailPage - 1) * TASKS_PER_PAGE, taskTrailPage * TASKS_PER_PAGE);

  useEffect(() => {
    setTaskTrailPage((prev) => Math.min(prev, taskTrailTotalPages));
  }, [taskTrailTotalPages]);

  const renderArchitectureNode = (node, variant = 'standard') => {
    if (!node) return null;
    return (
      <button
        key={node.key}
        type="button"
        className={`agent-arch-card ${variant} ${selectedContext?.id === node.key ? 'active' : ''}`}
        onClick={() => openTreeNode(node)}
      >
        <div className="agent-arch-card-head">
          <span className={`agent-arch-dot ${badgeTone(node.status)}`} />
          <span className="agent-arch-role">{node.label}</span>
          <span className={`ops-role-chip ops-role-chip-${badgeTone(node.status)}`}>{node.status}</span>
        </div>
        <div className="agent-arch-card-body">
          <strong>{node.symbol}</strong>
          <span>{tickerFullName(node.symbol)}</span>
        </div>
        <p>{node.focus}</p>
      </button>
    );
  };

  const renderArchitectureBoard = (board, { compact = false, withPanel = false } = {}) => {
    if (!board?.ceo || !board?.openclaw || !board?.fundManager) {
      return <div className="theater-empty">Hierarchy data is not available yet.</div>;
    }
    return (
      <div className={`agent-arch-board ${compact ? 'compact' : ''} ${withPanel ? 'with-panel' : ''}`}>
        <div className="agent-arch-topline">
          <div className="agent-arch-tier">
            {renderArchitectureNode(board.ceo, compact ? 'compact top' : 'top')}
          </div>
          <div className="agent-arch-connector vertical" />
          <div className="agent-arch-tier">
            {renderArchitectureNode(board.openclaw, compact ? 'compact orchestration' : 'orchestration')}
          </div>
          <div className="agent-arch-connector vertical" />
          <div className="agent-arch-tier">
            {renderArchitectureNode(board.fundManager, compact ? 'compact command' : 'command')}
          </div>
        </div>
        <div className="agent-arch-supervisor-rail" />
        <div className={`agent-arch-columns ${compact ? 'compact' : ''}`}>
          {(board.supervisors || []).map((supervisor) => (
            <div key={supervisor.key} className="agent-arch-column">
              <div className="agent-arch-column-supervisor">
                {renderArchitectureNode(supervisor, compact ? 'compact supervisor' : 'supervisor')}
              </div>
              <div className="agent-arch-column-spine" />
              <div className={`agent-arch-leaves ${supervisor.children?.length > 3 ? 'dense' : ''}`}>
                {(supervisor.children || []).length ? (
                  supervisor.children.map((child) => renderArchitectureNode(child, compact ? 'compact leaf' : 'leaf'))
                ) : (
                  <div className="agent-arch-empty">No downstream workers</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderContextBody = () => {
    if (!selectedContext) {
      return <div className="context-empty">Select an agent, task, report, or blog to pin it here.</div>;
    }
    if (selectedContext.loading || contextBusy) {
      return <div className="panel-loading">Loading focus context...</div>;
    }
    if (selectedContext.kind === 'worker') {
      const worker = selectedContext.data || {};
      return (
        <div className="context-block">
          <div className="context-title-row">
            <span className={`ops-role-chip ops-role-chip-${badgeTone(worker.taskStatus || worker.status)}`}>{worker.taskStatus || worker.status}</span>
            <strong>{worker.symbol}</strong>
          </div>
          <p>{worker.command || 'Monitoring queue'}</p>
          <div className="context-kv-list">
            <div><span>Completed</span><strong>{worker.completed}</strong></div>
            <div><span>Failed</span><strong>{worker.failed}</strong></div>
            <div><span>Blocked</span><strong>{worker.blocked}</strong></div>
            <div><span>Heartbeat</span><strong>{formatRelative(worker.lastHeartbeat)}</strong></div>
          </div>
          {worker.lastError ? <div className="context-warning">{worker.lastError}</div> : null}
        </div>
      );
    }
    if (selectedContext.kind === 'task') {
      const task = selectedContext.data || {};
      return (
        <div className="context-block">
          <div className="context-title-row">
            <span className={`ops-role-chip ops-role-chip-${badgeTone(task.status)}`}>{task.status || 'active'}</span>
            <strong>{String(task.payload?.symbol || task.details?.symbol || 'multi-asset').toUpperCase()}</strong>
          </div>
          <p>{task.payload?.command || task.event || 'Task event active.'}</p>
          <div className="context-kv-list">
            <div><span>Role</span><strong>{task.role || task.agent_id || 'n/a'}</strong></div>
            <div><span>Run</span><strong>{task.run_id ? task.run_id.slice(0, 16) : 'n/a'}</strong></div>
            <div><span>Task</span><strong>{task.task_id ? task.task_id.slice(0, 12) : 'n/a'}</strong></div>
            <div><span>Updated</span><strong>{formatRelative(task.ts || task.created_at)}</strong></div>
          </div>
        </div>
      );
    }
    if (selectedContext.kind === 'timeline') {
      const item = selectedContext.data || {};
      return (
        <div className="context-block">
          <div className="context-title-row">
            <span className={`ops-role-chip ops-role-chip-${badgeTone(item.status)}`}>{item.status || item.source}</span>
            <strong>{item.symbol || 'context'}</strong>
          </div>
          <p>{item.phase || 'Timeline event'}</p>
          <div className="context-kv-list">
            <div><span>Role</span><strong>{item.role || 'memory'}</strong></div>
            <div><span>Source</span><strong>{item.source || 'timeline'}</strong></div>
            <div><span>Run</span><strong>{item.runId ? item.runId.slice(0, 16) : 'n/a'}</strong></div>
            <div><span>At</span><strong>{formatRelative(item.heartbeat || item.ts)}</strong></div>
          </div>
        </div>
      );
    }
    if (selectedContext.kind === 'research') {
      const detail = selectedContext.data || {};
      const summary = detail.summary || detail.executive_summary || detail.thesis || selectedContext.preview;
      return (
        <div className="context-block">
          <div className="context-title-row">
            <span className="ops-role-chip ops-role-chip-ok">Research</span>
            <strong>{Math.round(Number(detail.confidence || 0) * 100 || 0)}%</strong>
          </div>
          <p>{summarizeText(summary, 360)}</p>
          <div className="context-kv-list">
            <div><span>Role</span><strong>{detail.agent_role || detail.agent_id || 'n/a'}</strong></div>
            <div><span>Asset</span><strong>{String(detail.asset_universe?.[0] || 'multi-asset').toUpperCase()}</strong></div>
            <div><span>Status</span><strong>{detail.status || 'published'}</strong></div>
            <div><span>Published</span><strong>{formatRelative(detail.published_at || detail.created_at)}</strong></div>
          </div>
          {selectedContext.href ? (
            <a className="context-link" href={selectedContext.href} target="_blank" rel="noreferrer">
              Open full research page <ExternalLink size={14} />
            </a>
          ) : null}
        </div>
      );
    }
    if (selectedContext.kind === 'blog') {
      const detail = selectedContext.data || {};
      return (
        <div className="context-block">
          <div className="context-title-row">
            <span className="ops-role-chip ops-role-chip-wait">Blog</span>
            <strong>{detail.read_time || detail.readTime || 'n/a'} min</strong>
          </div>
          <p>{summarizeText(detail.excerpt || detail.summary || detail.content || selectedContext.preview, 360)}</p>
          <div className="context-kv-list">
            <div><span>Category</span><strong>{detail.category || 'research'}</strong></div>
            <div><span>Author</span><strong>{detail.author || detail.author_role || 'Vektor'}</strong></div>
            <div><span>Views</span><strong>{detail.views || 0}</strong></div>
            <div><span>Published</span><strong>{formatRelative(detail.publishedAt || detail.published_at || detail.created_at)}</strong></div>
          </div>
          {selectedContext.href ? (
            <a className="context-link" href={selectedContext.href} target="_blank" rel="noreferrer">
              Open full blog page <ExternalLink size={14} />
            </a>
          ) : null}
        </div>
      );
    }
    return <div className="context-empty">No context selected.</div>;
  };

  const renderAuditRail = () => (
    <div className="context-block">
      <div className="context-audit-list">
        {(controlHistory || []).slice(0, 6).map((entry, index) => (
          <div key={`${entry.action || 'event'}-${entry.timestamp || index}`} className="context-audit-row">
            <div>
              <strong>{entry.action || entry.event_type || 'control event'}</strong>
              <span>{entry.reason || entry.actor || 'operator action'}</span>
            </div>
            <small>{formatRelative(entry.timestamp || entry.at || entry.created_at)}</small>
          </div>
        ))}
        {(!controlHistory || controlHistory.length === 0) && (
          <div className="context-empty">No runtime control events recorded.</div>
        )}
      </div>
      <div className="context-kv-list">
        <div><span>Halt State</span><strong>{systemStatus?.halt?.halted ? 'Halted' : 'Clear'}</strong></div>
        <div><span>Recovery Steps</span><strong>{haltRecoveryChecklist.length || 0}</strong></div>
        <div><span>Open Tasks</span><strong>{activeTasks.length}</strong></div>
        <div><span>Live Agents</span><strong>{broadcastRows.filter((row) => row.status === 'running').length}</strong></div>
      </div>
    </div>
  );

  const renderMemoryRail = () => (
    <div className="context-block">
      <div className="context-kv-list">
        <div><span>Canonical</span><strong>{knowledgeStats?.canonical_store || 'sqlite'}</strong></div>
        <div><span>Projection</span><strong>{knowledgeStats?.projection_store || 'filesystem_notes'}</strong></div>
        <div><span>Events</span><strong>{knowledgeStats?.event_count ?? 'n/a'}</strong></div>
        <div><span>Graphify</span><strong>{knowledgeStats?.graphify_sync_enabled ? 'Enabled' : 'Disabled'}</strong></div>
      </div>
      <div className="context-memory-stack">
        <div className="context-memory-card">
          <span>Recent Output</span>
          <strong>{reportDeliverables.length + blogDeliverables.length}</strong>
          <small>{reportDeliverables.length} research / {blogDeliverables.length} blog</small>
        </div>
        <div className="context-memory-card">
          <span>Freshness</span>
          <strong>{formatRelative(lastUpdate)}</strong>
          <small>Last operator sync</small>
        </div>
      </div>
    </div>
  );

  const renderMiniProvenanceGraph = () => {
    if (!selectedContext || !['research', 'blog'].includes(selectedContext.kind)) return null;
    const lineageSummary = selectedContext.lineageSummary || {};
    const auditDetail = selectedContext.auditDetail || {};
    const reportIds = Array.isArray(auditDetail?.related_research_report_ids) ? auditDetail.related_research_report_ids : [];
    const blogIds = Array.isArray(auditDetail?.related_blog_post_ids) ? auditDetail.related_blog_post_ids : [];
    const isResearch = selectedContext.kind === 'research';
    const deliverableLabel = isResearch ? 'Report' : 'Blog';
    const deliverableId = selectedContext.id ? String(selectedContext.id).slice(0, 8) : 'item';
    const runLabel = lineageSummary.run_id ? lineageSummary.run_id.slice(0, 10) : 'unlinked';
    const decisionLabel = lineageSummary.decision_id ? lineageSummary.decision_id.slice(0, 8) : 'n/a';
    const orderLabel = lineageSummary.order_id ? String(lineageSummary.order_id).slice(0, 8) : 'n/a';

    return (
      <section className="drawer-section">
        <h4>Mini Provenance Graph</h4>
        <svg viewBox="0 0 320 150" className="drawer-provenance-graph" role="img" aria-label="Deliverable provenance graph">
          <line x1="54" y1="75" x2="132" y2="42" className="drawer-provenance-edge" />
          <line x1="54" y1="75" x2="132" y2="108" className="drawer-provenance-edge" />
          <line x1="166" y1="42" x2="254" y2="42" className="drawer-provenance-edge" />
          <line x1="166" y1="108" x2="254" y2="108" className="drawer-provenance-edge" />

          <g className="drawer-provenance-node primary">
            <rect x="12" y="55" width="84" height="40" rx="10" />
            <text x="54" y="72" textAnchor="middle">{deliverableLabel}</text>
            <text x="54" y="87" textAnchor="middle">{deliverableId}</text>
          </g>

          <g className="drawer-provenance-node">
            <rect x="132" y="22" width="68" height="40" rx="10" />
            <text x="166" y="39" textAnchor="middle">Run</text>
            <text x="166" y="54" textAnchor="middle">{runLabel}</text>
          </g>

          <g className="drawer-provenance-node">
            <rect x="132" y="88" width="68" height="40" rx="10" />
            <text x="166" y="105" textAnchor="middle">Reports</text>
            <text x="166" y="120" textAnchor="middle">{reportIds.length || (isResearch ? 1 : 0)}</text>
          </g>

          <g className="drawer-provenance-node accent">
            <rect x="254" y="22" width="54" height="40" rx="10" />
            <text x="281" y="39" textAnchor="middle">Decision</text>
            <text x="281" y="54" textAnchor="middle">{decisionLabel}</text>
          </g>

          <g className="drawer-provenance-node accent">
            <rect x="254" y="88" width="54" height="40" rx="10" />
            <text x="281" y="105" textAnchor="middle">{isResearch ? 'Blogs' : 'Order'}</text>
            <text x="281" y="120" textAnchor="middle">{isResearch ? (blogIds.length || 0) : orderLabel}</text>
          </g>
        </svg>
      </section>
    );
  };

  const openDeliverablePage = useCallback((href) => {
    if (!href || href === '#') return;
    const navigate = () => {
      setDeliverableDrawerOpen(false);
      window.location.assign(href);
    };
    if (document.startViewTransition) {
      document.startViewTransition(() => {
        navigate();
      });
      return;
    }
    navigate();
  }, []);

  const renderDeliverableDrawerBody = () => {
    if (!selectedContext || !['research', 'blog'].includes(selectedContext.kind)) {
      return <div className="context-empty">No deliverable selected.</div>;
    }
    if (selectedContext.loading || contextBusy) {
      return <div className="panel-loading">Loading deliverable...</div>;
    }
    const detail = selectedContext.data || {};
    const auditDetail = selectedContext.auditDetail || null;
    const auditTimeline = Array.isArray(auditDetail?.audit_timeline) ? auditDetail.audit_timeline.slice(-12) : [];
    const taskEvents = Array.isArray(auditDetail?.task_events) ? auditDetail.task_events.slice(-10) : [];
    const lineageSummary = selectedContext.lineageSummary || null;
    if (selectedContext.kind === 'research') {
      const summary = detail.summary || detail.executive_summary || detail.thesis || selectedContext.preview;
      return (
        <div className="drawer-body">
          <div className="drawer-kv-grid">
            <div><span>Role</span><strong>{detail.agent_role || detail.agent_id || 'n/a'}</strong></div>
            <div><span>Confidence</span><strong>{Math.round(Number(detail.confidence || 0) * 100 || 0)}%</strong></div>
            <div><span>Asset</span><strong>{String(detail.asset_universe?.[0] || 'multi-asset').toUpperCase()}</strong></div>
            <div><span>Published</span><strong>{formatRelative(detail.published_at || detail.created_at)}</strong></div>
            <div><span>Provider</span><strong>{detail.provider_used || detail.ai_trace?.provider || 'n/a'}</strong></div>
            <div><span>Model</span><strong>{detail.model_used || detail.ai_trace?.model || 'n/a'}</strong></div>
            <div><span>Surface</span><strong>{detail.surface || 'kb'}</strong></div>
            <div><span>Run</span><strong>{detail.run_id || lineageSummary?.run_id || 'n/a'}</strong></div>
          </div>
          {lineageSummary ? (
            <section className="drawer-section">
              <h4>Linked Run</h4>
              <div className="drawer-kv-grid">
                <div><span>Run</span><strong>{lineageSummary.run_id || 'n/a'}</strong></div>
                <div><span>Decision</span><strong>{lineageSummary.decision_id || 'n/a'}</strong></div>
                <div><span>Trader</span><strong>{lineageSummary.trader_status || 'n/a'}</strong></div>
                <div><span>Blocked</span><strong>{Array.isArray(lineageSummary.blocked_reasons) ? lineageSummary.blocked_reasons.length : 0}</strong></div>
              </div>
            </section>
          ) : null}
          <section className="drawer-section">
            <h4>Summary</h4>
            <p>{summary || 'No summary available.'}</p>
          </section>
          <section className="drawer-section">
            <h4>Key Thesis</h4>
            <p>{detail.thesis || detail.executive_summary || 'No thesis available.'}</p>
          </section>
          {renderMiniProvenanceGraph()}
          <section className="drawer-section">
            <h4>Audit Timeline</h4>
            <div className="drawer-audit-list">
              {auditTimeline.map((event, index) => (
                <div key={`${event.event_id || event.timestamp || index}`} className="drawer-audit-row">
                  <div>
                    <strong>{event.event_type || event.source || 'audit event'}</strong>
                    <span>{summarizeText(JSON.stringify(event.payload || {}), 120)}</span>
                  </div>
                  <small>{formatRelative(event.timestamp)}</small>
                </div>
              ))}
              {!auditTimeline.length && (
                <div className="context-empty">No linked audit timeline for this report yet.</div>
              )}
            </div>
          </section>
          <section className="drawer-section">
            <h4>Task Trail</h4>
            <div className="drawer-audit-list">
              {taskEvents.map((event, index) => (
                <div key={`${event.task_id || event.timestamp || index}`} className="drawer-audit-row">
                  <div>
                    <strong>{event.role || 'agent'} · {event.status || 'status'}</strong>
                    <span>{event.event || 'task event'}</span>
                  </div>
                  <small>{formatRelative(event.timestamp)}</small>
                </div>
              ))}
              {!taskEvents.length && (
                <div className="context-empty">No task trail linked to this report.</div>
              )}
            </div>
          </section>
          {selectedContext.href && selectedContext.href !== '#' ? (
            <button type="button" className="drawer-open-page-btn" onClick={() => openDeliverablePage(selectedContext.href)}>
              Open full research page <ExternalLink size={14} />
            </button>
          ) : (
            <div className="context-empty">This document stays inside the KB surface until promoted to a public research paper.</div>
          )}
        </div>
      );
    }
    return (
      <div className="drawer-body">
        <div className="drawer-kv-grid">
          <div><span>Category</span><strong>{detail.category || 'research'}</strong></div>
          <div><span>Author</span><strong>{detail.author || detail.author_role || 'Vektor'}</strong></div>
          <div><span>Views</span><strong>{detail.views || 0}</strong></div>
          <div><span>Read Time</span><strong>{detail.read_time || detail.readTime || 'n/a'} min</strong></div>
          <div><span>Provider</span><strong>{detail.providerUsed || detail.aiTrace?.provider || detail.metadata?.ai?.provider || 'n/a'}</strong></div>
          <div><span>Model</span><strong>{detail.modelUsed || detail.aiTrace?.model || detail.metadata?.ai?.model || 'n/a'}</strong></div>
        </div>
        {lineageSummary ? (
          <section className="drawer-section">
            <h4>Linked Run</h4>
            <div className="drawer-kv-grid">
              <div><span>Run</span><strong>{detail.sourceRunId || lineageSummary.run_id || 'n/a'}</strong></div>
              <div><span>Report</span><strong>{detail.sourceReportId || 'n/a'}</strong></div>
              <div><span>Decision</span><strong>{lineageSummary.decision_id || 'n/a'}</strong></div>
              <div><span>Order</span><strong>{lineageSummary.order_id || 'n/a'}</strong></div>
            </div>
          </section>
        ) : null}
        <section className="drawer-section">
          <h4>Excerpt</h4>
          <p>{detail.excerpt || selectedContext.preview || 'No excerpt available.'}</p>
        </section>
        <section className="drawer-section">
          <h4>Body Preview</h4>
          <p>{summarizeText(detail.content || detail.summary || detail.excerpt, 900)}</p>
        </section>
        {renderMiniProvenanceGraph()}
        <section className="drawer-section">
          <h4>Audit Timeline</h4>
          <div className="drawer-audit-list">
            {auditTimeline.map((event, index) => (
              <div key={`${event.event_id || event.timestamp || index}`} className="drawer-audit-row">
                <div>
                  <strong>{event.event_type || event.source || 'audit event'}</strong>
                  <span>{summarizeText(JSON.stringify(event.payload || {}), 120)}</span>
                </div>
                <small>{formatRelative(event.timestamp)}</small>
              </div>
            ))}
            {!auditTimeline.length && (
              <div className="context-empty">No linked audit timeline for this post yet.</div>
            )}
          </div>
        </section>
        {selectedContext.href && selectedContext.href !== '#' ? (
          <button type="button" className="drawer-open-page-btn" onClick={() => openDeliverablePage(selectedContext.href)}>
            Open full blog page <ExternalLink size={14} />
          </button>
        ) : null}
      </div>
    );
  };

  const activeNavLabel = navigationItems.find((item) => item.id === activeTab)?.label;
  const selectedTimelineItem = filteredSwarmTimeline[Math.min(timelineIndex, Math.max(filteredSwarmTimeline.length - 1, 0))] || null;

  return (
    <>
      <ToastContainer />
      <div className={`admin-container ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <aside className={`admin-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          <div className="sidebar-header">
            <div className="sidebar-logo">
              <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: '34px', width: 'auto', objectFit: 'contain' }} />
              <span>Vektor Admin</span>
              <span className={`admin-title-dot ${connectionStatus === 'connected' ? 'connected' : connectionStatus === 'connecting' ? 'connecting' : 'error'}`} />
            </div>
            <button className="sidebar-toggle-mobile" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
              <X size={20} />
            </button>
          </div>

          <div className="sidebar-command-summary">
            <div className="sidebar-summary-cell">
              <span>Live</span>
              <strong>{workerRows.filter((row) => row.status === 'running').length}</strong>
            </div>
            <div className="sidebar-summary-cell">
              <span>Tasks</span>
              <strong>{activeTasks.length}</strong>
            </div>
            <div className="sidebar-summary-cell">
              <span>KB</span>
              <strong>{knowledgeStats?.event_count ?? 'n/a'}</strong>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const count = sidebarCounts[item.id];
              return (
                <button
                  key={item.id}
                  className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => {
                    setActiveTab(item.id);
                  }}
                  title={`${item.label} · ${item.description}`}
                >
                  <Icon size={16} className="nav-icon" />
                  <span className="nav-label">{item.label}</span>
                  <span className="nav-pill">{count}</span>
                </button>
              );
            })}
          </nav>

          <div className="sidebar-footer-dense">
            <div className="sidebar-footer-block">
              <span className="sidebar-footer-label">Runtime</span>
              <strong>{runtimeControl?.runtime_started ? 'Running' : 'Paused'}</strong>
            </div>
            <div className="sidebar-footer-block">
              <span className="sidebar-footer-label">Data</span>
              <strong>{systemStatus?.data_source?.status || 'Unknown'}</strong>
            </div>
            <div className="sidebar-footer-block">
              <span className="sidebar-footer-label">Execution</span>
              <strong>{systemStatus?.execution_mode?.status || 'Unknown'}</strong>
            </div>

            <div className="sidebar-links">
              <a href="http://localhost:3000" target="_blank" rel="noreferrer" className="sidebar-link-item">
                <Globe size={14} />
                <span>Landing</span>
              </a>
              <a href="http://localhost:3001" target="_blank" rel="noreferrer" className="sidebar-link-item">
                <BookOpen size={14} />
                <span>Blog</span>
              </a>
              <a href="/" target="_blank" rel="noreferrer" className="sidebar-link-item">
                <ExternalLink size={14} />
                <span>Public PnL</span>
              </a>
            </div>
          </div>
        </aside>

        <main className="admin-main">
          <header className="admin-header">
            <div className="header-left">
              <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
                <Menu size={20} />
              </button>
              <div className="breadcrumb" role="navigation" aria-label="Breadcrumb">
                <span className="breadcrumb-item">Admin</span>
                <span className="breadcrumb-separator">/</span>
                <span className="breadcrumb-item active">{activeNavLabel}</span>
              </div>
            </div>
            <div className="header-right">
              <button className="btn-refresh" onClick={() => fetchAdminState({ manual: true })} disabled={refreshing || loading} title="Refresh metrics">
                <RefreshCw size={18} className={refreshing ? 'spinning' : ''} />
              </button>
            </div>
          </header>

          <div className="admin-content">
            {loading && !metrics ? (
              <div className="initial-load">
                <div className="load-spinner" />
                <p>Loading admin dashboard...</p>
              </div>
            ) : (
              <>
                {systemStatus?.halt?.halted && (
                  <section className="system-halt-banner" role="alert" aria-live="polite">
                    <div className="system-halt-title">System Halted</div>
                    <div className="system-halt-message">
                      {systemStatus?.halt?.message || 'Strict real-data mode halted runtime activities.'}
                    </div>
                    <div className="system-halt-reason">Reason: {systemStatus?.halt?.reason || 'unknown'}</div>
                    {haltRecoveryChecklist.length > 0 && (
                      <ul className="system-halt-checklist">
                        {haltRecoveryChecklist.map((item, idx) => (
                          <li key={`halt-check-${idx}`}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </section>
                )}

                <div className="admin-workspace">
                  <div className="admin-primary-pane">
                    {activeTab === 'warroom' && (
                      <div className="tab-dashboard">
                        <section className="content-section command-hero">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">CEO Command Room</div>
                              <h2 className="section-title">War room</h2>
                            </div>
                            <span className="command-pill">
                              <Radio size={13} />
                              {connectionStatus === 'connected' ? 'live runtime' : connectionStatus === 'connecting' ? 'reconnecting' : 'degraded'}
                            </span>
                          </div>
                          <div className="warroom-overview-grid">
                            <div className="warroom-overview-card">
                              <span>Live agents</span>
                              <strong>{hierarchyStats?.active_count ?? workerRows.filter((row) => row.status === 'running').length}</strong>
                              <small>{workerRows.length} total workers in runtime</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Live queue</span>
                              <strong>{activeTasks.length}</strong>
                              <small>{taskHistoryRows.length} events captured in trail</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Deferred</span>
                              <strong>{deferredTaskCount}</strong>
                              <small>queued until provider capacity reopens</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Paper equity</span>
                              <strong>{currency(metrics?.total_equity || paperSummary.equity)}</strong>
                              <small>{currency(paperSummary.unrealized)} unrealized</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>OpenClaw packs</span>
                              <strong>{workersStatus?.signal_packs?.length || 0}</strong>
                              <small>{workersStatus?.autopilot?.allow_cash_hold ? 'cash hold enabled' : 'cash hold disabled'}</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Next provider window</span>
                              <strong>{nextProviderWindow.label}</strong>
                              <small>{nextProviderWindow.provider}: {nextProviderWindow.detail}</small>
                            </div>
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <h2 className="section-title">Runtime status</h2>
                          </div>
                          <div className="ops-badge-grid">
                            {STATUS_KEYS.map(([key, label]) => (
                              <div key={key} className="ops-badge-card">
                                <div className="ops-badge-label">{label}</div>
                                <span className={`ops-badge ops-badge-${badgeTone(systemStatus?.[key]?.status)}`}>
                                  {systemStatus?.[key]?.status || 'Unknown'}
                                </span>
                              </div>
                            ))}
                          </div>
                          <div className="ops-role-health">
                            {(systemStatus?.llm_agent_health?.by_role || []).map((roleHealth) => (
                              <span
                                key={roleHealth.role}
                                className={`ops-role-chip ops-role-chip-${badgeTone(roleHealth.status)}`}
                                title={roleHealth.reason || ''}
                              >
                                {roleHealth.role}: {roleHealth.status}
                              </span>
                            ))}
                          </div>
                        </section>

                        <div className="content-grid two-up-tight">
                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Live queue</h3>
                            </div>
                            {renderFeedRows(recentTaskRows, 'No active tasks.', {
                              selectable: true,
                              onSelect: (row) => openTaskContext(row.data),
                              selectedId: selectedContext?.id,
                            })}
                          </section>
                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Paper portfolio snapshot</h3>
                            </div>
                            <div className="pnl-brief-grid">
                              <div className="pnl-brief-card">
                                <span>Account</span>
                                <strong>Alpaca paper</strong>
                                <small>Same source used by admin and live PnL</small>
                              </div>
                              <div className="pnl-brief-card">
                                <span>Positions</span>
                                <strong>{paperSummary.count}</strong>
                                <small>{currency(paperSummary.equity)} deployed</small>
                              </div>
                              <div className="pnl-brief-card">
                                <span>Best</span>
                                <strong>{paperSummary.biggestWinner?.symbol || 'n/a'}</strong>
                                <small>{currency(paperSummary.biggestWinner?.unrealized_pnl)}</small>
                              </div>
                              <div className="pnl-brief-card">
                                <span>Worst</span>
                                <strong>{paperSummary.biggestLoser?.symbol || 'n/a'}</strong>
                                <small>{currency(paperSummary.biggestLoser?.unrealized_pnl)}</small>
                              </div>
                            </div>
                          </section>
                        </div>

                        <div className="content-grid two-up-tight">
                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Command deck</h3>
                            </div>
                            <div className="theater-control-grid">
                              <button className="btn-secondary" onClick={() => runControlAction('pause')} disabled={controlBusy !== ''}>
                                {controlBusy === 'pause' ? 'Pausing...' : 'Pause runtime'}
                              </button>
                              <button className="btn-secondary" onClick={() => runControlAction('resume')} disabled={controlBusy !== '' || Boolean(systemStatus?.halt?.halted)}>
                                {controlBusy === 'resume' ? 'Resuming...' : 'Resume runtime'}
                              </button>
                              <button className="btn-secondary" onClick={() => runControlAction('kick_autopilot')} disabled={controlBusy !== '' || Boolean(systemStatus?.halt?.halted)}>
                                {controlBusy === 'kick_autopilot' ? 'Dispatching...' : 'Run scout cycle'}
                              </button>
                              <button className="btn-secondary" onClick={() => runControlAction('clear_halt')} disabled={controlBusy !== '' || !Boolean(systemStatus?.halt?.halted)}>
                                {controlBusy === 'clear_halt' ? 'Clearing...' : 'Clear halt'}
                              </button>
                              <button className="btn-secondary danger" onClick={() => runKnowledgeAction('reset')} disabled={kbBusy !== ''}>
                                {kbBusy === 'reset' ? 'Resetting...' : 'Reset KB'}
                              </button>
                              <button className="btn-secondary" onClick={() => runKnowledgeAction('rebuild')} disabled={kbBusy !== ''}>
                                {kbBusy === 'rebuild' ? 'Rebuilding...' : 'Rebuild projection'}
                              </button>
                            </div>
                          </section>

                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">OpenClaw oversight</h3>
                            </div>
                            <div className="openclaw-summary-grid">
                              <div className="openclaw-summary-card">
                                <span>Autopilot</span>
                                <strong>{workersStatus?.autopilot?.enabled ? 'Enabled' : 'Manual'}</strong>
                                <small>{workersStatus?.autopilot?.last_session?.reason || 'session unknown'}</small>
                              </div>
                              <div className="openclaw-summary-card">
                                <span>Scout universe</span>
                                <strong>{workersStatus?.autopilot?.last_scout?.selected_symbols?.join(', ') || 'n/a'}</strong>
                                <small>{workersStatus?.autopilot?.dynamic_universe_enabled ? 'dynamic' : 'static'} universe</small>
                              </div>
                              <div className="openclaw-summary-card">
                                <span>Real data</span>
                                <strong>{workersStatus?.data_integrity?.data_source_status || 'Unknown'}</strong>
                                <small>{workersStatus?.data_integrity?.strict_real_data_only ? 'strict mode enforced' : 'strict mode off'}</small>
                              </div>
                              <div className="openclaw-summary-card">
                                <span>LLM adapter</span>
                                <strong>{workersStatus?.ai_role_adapter?.mode || workersStatus?.ai_role_adapter?.provider || 'n/a'}</strong>
                                <small>{nextProviderWindow.provider}: {nextProviderWindow.detail}</small>
                              </div>
                            </div>
                          </section>
                        </div>

                        <div className="content-grid two-up-tight">
                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Capital policy</h3>
                            </div>
                            <div className="deliverable-list">
                              {allocationRows.length ? allocationRows.map((row) => (
                                <article key={row.assetClass} className="deliverable-card">
                                  <div className="deliverable-head">
                                    <div>
                                      <strong>{row.assetClass}</strong>
                                      <span>{percent(row.weight * 100)}</span>
                                    </div>
                                    <span className="deliverable-pill">{currency(row.remaining)} free</span>
                                  </div>
                                  <p>{currency(row.used)} used of {currency(row.allocated)}</p>
                                </article>
                              )) : <div className="empty-state">No allocation policy registered yet.</div>}
                            </div>
                          </section>

                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Discovery pipeline</h3>
                            </div>
                            <div className="deliverable-list">
                              {discoveryRows.length ? discoveryRows.slice(0, 5).map((row) => (
                                <article key={row.opportunity_id || `${row.symbol}-${row.updated_at}`} className="deliverable-card">
                                  <div className="deliverable-head">
                                    <div>
                                      <strong>{row.symbol}</strong>
                                      <span>{row.asset_class || 'equities'} · {row.direction || 'candidate'}</span>
                                    </div>
                                    <span className="deliverable-pill">{Number(row.score || 0).toFixed(2)}</span>
                                  </div>
                                  <p>{row.thesis || 'No thesis summary available.'}</p>
                                </article>
                              )) : <div className="empty-state">No discovery opportunities recorded yet.</div>}
                            </div>
                          </section>
                        </div>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <h2 className="section-title">Swarm snapshot</h2>
                          </div>
                          <div className="warroom-tree-preview">
                            {renderArchitectureBoard(hierarchyTree, { compact: true })}
                          </div>
                          <div className="content-grid two-up-tight">
                            <div>
                              <div className="section-header section-header-tight">
                                <h3 className="section-subtitle">Staged wave queue</h3>
                              </div>
                              {renderFeedRows(
                                scheduledWaveRows,
                                'No staged waves.',
                                {
                                  selectable: true,
                                  onSelect: (row) => openArtifactContext({
                                    id: row.id,
                                    title: row.title,
                                    subtitle: row.subtitle,
                                    preview: jsonPreview(row.data, 220),
                                    detail: row.detail,
                                    data: row.data,
                                    type: 'Wave Queue',
                                  }),
                                  selectedId: selectedContext?.id,
                                  openLabel: 'Pin',
                                }
                              )}
                            </div>
                            <div>
                              <div className="section-header section-header-tight">
                                <h3 className="section-subtitle">Signal pack state</h3>
                              </div>
                              {renderFeedRows(
                                signalPackRows,
                                'No active signal packs.',
                                {
                                  selectable: true,
                                  onSelect: (row) => openArtifactContext({
                                    id: row.id,
                                    title: row.title,
                                    subtitle: row.subtitle,
                                    preview: jsonPreview(row.data, 220),
                                    detail: row.detail,
                                    data: row.data,
                                    type: 'Signal Pack',
                                  }),
                                  selectedId: selectedContext?.id,
                                  openLabel: 'Inspect',
                                }
                              )}
                            </div>
                          </div>
                          <div className="feed-stack">
                            {renderFeedRows(
                              swarmActiveContexts.slice(0, 6).map((ctx) => ({
                                id: ctx.task_id,
                                type: 'task',
                                title: ctx.role || ctx.agent_id || 'active_context',
                                subtitle: [ctx.symbol, ctx.run_id].filter(Boolean).join(' · '),
                                summary: ctx.command || JSON.stringify(ctx.context || {}),
                                badge: 'Live context',
                                data: ctx,
                              })),
                              'No live agent contexts.',
                              {
                                selectable: true,
                                onSelect: openTaskContext,
                                selectedId: selectedContext?.id,
                                openLabel: 'Inspect',
                              }
                            )}
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">Knowledge Base</div>
                              <h2 className="section-title">Trace graph</h2>
                            </div>
                          </div>
                          <KnowledgeTraceGraph
                            reports={reports}
                            posts={posts}
                            lineageRows={lineageRows}
                            onSelectReport={openDeliverable}
                            onSelectPost={openDeliverable}
                          />
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <h2 className="section-title">Deliverable stream</h2>
                          </div>
                          <div className="deliverable-matrix">
                            {renderFeedRows(reportDeliverables.slice(0, 4), 'No research reports.', {
                              selectable: true,
                              onSelect: openDeliverable,
                              selectedId: selectedContext?.id,
                              openLabel: 'Inspect',
                            })}
                            {renderFeedRows(signalPackDeliverables.slice(0, 4), 'No signal packets.', {
                              selectable: true,
                              onSelect: openArtifactContext,
                              selectedId: selectedContext?.id,
                              openLabel: 'Pin',
                            })}
                          </div>
                        </section>
                      </div>
                    )}

                    {activeTab === 'agents' && (
                      <div className="tab-agents">
                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">1) Overview</div>
                              <h2 className="section-title">Live agent overview</h2>
                            </div>
                            <span className="command-pill">
                              <Bot size={13} />
                              {workerRows.filter((row) => row.status === 'running').length} active workers
                            </span>
                          </div>
                          <div className="agent-overview-list">
                            {overviewRows.map((row) => (
                              <button key={row.id} type="button" className="agent-overview-row" onClick={() => openWorkerContext(row)}>
                                <div className="agent-overview-main">
                                  <div className="agent-overview-head">
                                    <strong>{roleLabel(row.role)}</strong>
                                    <span className={`ops-role-chip ops-role-chip-${badgeTone(row.taskStatus || row.status)}`}>{row.taskStatus || row.status}</span>
                                  </div>
                                  <div className="agent-overview-focus">{row.focus}</div>
                                </div>
                                <div className="agent-overview-asset">
                                  <strong>{row.symbol}</strong>
                                  <span>{row.tickerName}</span>
                                </div>
                                <div className="agent-overview-detail">{row.overview}</div>
                              </button>
                            ))}
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">2) Swarm Broadcast</div>
                              <h2 className="section-title">Live orchestration topology</h2>
                            </div>
                            <button type="button" className="btn-secondary rail-toggle-btn" onClick={() => setTreePanelOpen((prev) => !prev)}>
                              {treePanelOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
                              {treePanelOpen ? 'Hide panel' : 'Show panel'}
                            </button>
                          </div>
                          <div className={`swarm-broadcast-layout ${treePanelOpen ? 'with-panel' : 'full-width'}`}>
                            <div className="swarm-broadcast-tree">
                              {renderArchitectureBoard(hierarchyTree, { withPanel: treePanelOpen })}
                            </div>
                            {treePanelOpen ? (
                              <aside className="swarm-broadcast-panel">
                                <div className="swarm-broadcast-panel-head">
                                  <strong>{selectedContext?.title || 'Node focus'}</strong>
                                  <span>{selectedContext?.subtitle || 'Pick a node in the orchestration board.'}</span>
                                </div>
                                {renderContextBody()}
                              </aside>
                            ) : null}
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">3) OpenClaw Layer</div>
                              <h2 className="section-title">Orchestration runtime</h2>
                            </div>
                            <span className="command-pill">
                              <Network size={13} />
                              {workersStatus?.autopilot?.running ? 'actively dispatching' : 'standing by'}
                            </span>
                          </div>
                          <div className="openclaw-layer-grid">
                            <div className="openclaw-layer-card">
                              <span>What OpenClaw is doing</span>
                              <strong>{workersStatus?.autopilot?.enabled ? 'Coordinating scout + specialist swarm + paper execution' : 'Accepting manual CEO dispatch only'}</strong>
                              <small>{workersStatus?.autopilot?.last_session?.reason || 'No market session context available'}</small>
                            </div>
                            <div className="openclaw-layer-card">
                              <span>Current scout</span>
                              <strong>{workersStatus?.autopilot?.last_scout?.selected_symbols?.join(', ') || 'n/a'}</strong>
                              <small>{workersStatus?.autopilot?.dynamic_universe_enabled ? 'Dynamic ticker discovery active' : 'Static watchlist mode'}</small>
                            </div>
                            <div className="openclaw-layer-card">
                              <span>Signal packs</span>
                              <strong>{workersStatus?.signal_packs?.length || 0}</strong>
                              <small>{workersStatus?.signal_packs?.[0]?.symbol ? `Latest ${workersStatus.signal_packs[0].symbol}` : 'No recent packs'}</small>
                            </div>
                            <div className="openclaw-layer-card">
                              <span>LLM stack</span>
                              <strong>{workersStatus?.ai_role_adapter?.provider || 'n/a'} · {workersStatus?.ai_role_adapter?.default_model || 'n/a'}</strong>
                              <small>{workersStatus?.ai_role_adapter?.last_error || 'No adapter error reported'}</small>
                            </div>
                          </div>
                          <div className="openclaw-packs-list">
                            {(workersStatus?.signal_packs || []).map((pack) => (
                              <button key={pack.signal_pack_id} type="button" className="openclaw-pack-row" onClick={() => openArtifactContext(signalPackDeliverables.find((item) => item.id === pack.signal_pack_id) || { id: pack.signal_pack_id, title: `${pack.symbol} signal pack`, subtitle: pack.run_id, preview: jsonPreview(pack, 240), detail: pack.composite_report_id || 'n/a', data: pack, type: 'JSON Packet' })}>
                                <div>
                                  <strong>{pack.symbol}</strong>
                                  <span>{pack.run_id}</span>
                                </div>
                                <div className="openclaw-pack-meta">
                                  <span>{pack.completed_roles?.length || 0}/{pack.expected_roles?.length || 0} complete</span>
                                  <span>{String(pack.composite_report_id || '').slice(0, 8) || 'no report'}</span>
                                </div>
                              </button>
                            ))}
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">4) Trail of Tasks Done</div>
                              <h2 className="section-title">Full chronology</h2>
                            </div>
                            <div className="timeline-toolbar">
                              <label className="timeline-filter">
                                <Filter size={14} />
                                <span>Role</span>
                                <select value={timelineRoleFilter} onChange={(e) => { setTimelineRoleFilter(e.target.value); setTaskTrailPage(1); }}>
                                  {timelineRoleOptions.map((option) => (
                                    <option key={option} value={option}>{option === 'all' ? 'All roles' : option}</option>
                                  ))}
                                </select>
                              </label>
                              <label className="timeline-filter">
                                <ScrollText size={14} />
                                <span>Run</span>
                                <select value={timelineRunFilter} onChange={(e) => { setTimelineRunFilter(e.target.value); setTaskTrailPage(1); }}>
                                  {timelineRunOptions.map((option) => (
                                    <option key={option} value={option}>{option === 'all' ? 'All runs' : option}</option>
                                  ))}
                                </select>
                              </label>
                              <label className="timeline-filter timeline-filter-symbol">
                                <TrendingUp size={14} />
                                <span>Symbol</span>
                                <input value={timelineSymbolFilter} onChange={(e) => { setTimelineSymbolFilter(e.target.value); setTaskTrailPage(1); }} placeholder="NVDA" />
                              </label>
                            </div>
                          </div>
                          <div className="task-trail-table">
                            {paginatedTaskTrail.map((row) => (
                                <button key={row.id} type="button" className="task-trail-row" onClick={() => openTaskContext(row.raw)}>
                                  <div className="task-trail-core">
                                    <strong>{roleLabel(row.role)}</strong>
                                    <span>{row.event}</span>
                                  </div>
                                  <div className="task-trail-symbol">
                                    <strong>{row.symbol}</strong>
                                    <span>{row.symbolName}</span>
                                  </div>
                                  <div className="task-trail-detail">{row.detail}</div>
                                  <div className="task-trail-meta">
                                    <span className={`ops-role-chip ops-role-chip-${badgeTone(row.status)}`}>{row.status}</span>
                                    <small>{formatRelative(row.timestamp)}</small>
                                    {row.event === 'deferred' && row.nextAttemptAt ? (
                                      <small className="task-trail-next-at">Retry {formatDateTime(row.nextAttemptAt)}</small>
                                    ) : null}
                                    {row.event === 'deferred' && row.retryCount ? (
                                      <small className="task-trail-next-at">Attempt {row.retryCount + 1}</small>
                                    ) : null}
                                  </div>
                                  {row.event === 'deferred' && row.deferReason ? (
                                    <div className="task-trail-defer-reason">{summarizeText(row.deferReason, 180)}</div>
                                  ) : null}
                                </button>
                              ))}
                          </div>
                          <div className="task-trail-pagination">
                            <button type="button" className="btn-secondary" onClick={() => setTaskTrailPage((prev) => Math.max(1, prev - 1))} disabled={taskTrailPage === 1}>
                              Previous
                            </button>
                            <span>Page {taskTrailPage} / {taskTrailTotalPages}</span>
                            <button type="button" className="btn-secondary" onClick={() => setTaskTrailPage((prev) => Math.min(taskTrailTotalPages, prev + 1))} disabled={taskTrailPage === taskTrailTotalPages}>
                              Next
                            </button>
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">5) Deliverables</div>
                              <h2 className="section-title">Reports, packets, math ops, editorial</h2>
                            </div>
                          </div>
                          <div className="agents-deliverables-grid">
                            <div>
                              <h3 className="section-subtitle">Research reports</h3>
                              {renderFeedRows(reportDeliverables, 'No research reports available.', {
                                selectable: true,
                                onSelect: openDeliverable,
                                selectedId: selectedContext?.id,
                                openLabel: 'Inspect',
                              })}
                            </div>
                            <div>
                              <h3 className="section-subtitle">JSON packets</h3>
                              {renderFeedRows(signalPackDeliverables, 'No signal packets available.', {
                                selectable: true,
                                onSelect: openArtifactContext,
                                selectedId: selectedContext?.id,
                                openLabel: 'Pin',
                              })}
                            </div>
                            <div>
                              <h3 className="section-subtitle">ML math ops</h3>
                              {renderFeedRows(mlMathDeliverables, 'No ML packets available.', {
                                selectable: true,
                                onSelect: openArtifactContext,
                                selectedId: selectedContext?.id,
                                openLabel: 'Pin',
                              })}
                            </div>
                            <div>
                              <h3 className="section-subtitle">Editorial output</h3>
                              {renderFeedRows(blogDeliverables, 'No blog output available.', {
                                selectable: true,
                                onSelect: openDeliverable,
                                selectedId: selectedContext?.id,
                                openLabel: 'Inspect',
                              })}
                            </div>
                          </div>
                        </section>
                      </div>
                    )}

                    {activeTab === 'performance' && (
                      <div className="tab-performance">
                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">Track Record</div>
                              <h2 className="section-title">Performance ledger</h2>
                            </div>
                            <div className="performance-action-row">
                              <button
                                type="button"
                                className="btn-primary"
                                onClick={() => runPerformanceAction('capture_checkpoint')}
                                disabled={Boolean(performanceBusy)}
                              >
                                Capture checkpoint
                              </button>
                              <button
                                type="button"
                                className="btn-secondary"
                                onClick={() => runPerformanceAction('initialize_inception')}
                                disabled={Boolean(performanceBusy)}
                              >
                                Clean inception
                              </button>
                              <button
                                type="button"
                                className="btn-secondary danger"
                                onClick={() => runPerformanceAction('reset_history')}
                                disabled={Boolean(performanceBusy)}
                              >
                                Reset history only
                              </button>
                            </div>
                          </div>
                          <div className="warroom-overview-grid">
                            <div className="warroom-overview-card">
                              <span>Sharpe ratio</span>
                              <strong>{Number(performanceTrackRecord?.sharpe_ratio || 0).toFixed(2)}</strong>
                              <small>{performanceTrackRecord?.sample_days || 0} daily samples</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Total return</span>
                              <strong>{percent(performanceTrackRecord?.total_return_pct || 0)}</strong>
                              <small>{currency(performanceLatest?.equity || 0)} latest equity</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Alpha vs benchmark</span>
                              <strong>{percent(performanceTrackRecord?.alpha_vs_primary_benchmark_pct || 0)}</strong>
                              <small>{percent(performanceTrackRecord?.primary_benchmark_return_pct || 0)} benchmark return</small>
                            </div>
                            <div className="warroom-overview-card">
                              <span>Max drawdown</span>
                              <strong>{percent(performanceTrackRecord?.max_drawdown_pct || 0)}</strong>
                              <small>{performanceSummary?.snapshot_count || 0} snapshots stored</small>
                            </div>
                          </div>
                        </section>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <h2 className="section-title">Equity and PnL curve</h2>
                          </div>
                          <div className="performance-chart-shell">
                            {performanceCurveRows.length ? (
                              <ResponsiveContainer width="100%" height={320}>
                                <AreaChart data={performanceCurveRows}>
                                  <defs>
                                    <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                                      <stop offset="5%" stopColor="#9b7fe8" stopOpacity={0.35} />
                                      <stop offset="95%" stopColor="#9b7fe8" stopOpacity={0.02} />
                                    </linearGradient>
                                    <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                                      <stop offset="5%" stopColor="#3ecf8e" stopOpacity={0.25} />
                                      <stop offset="95%" stopColor="#3ecf8e" stopOpacity={0.02} />
                                    </linearGradient>
                                  </defs>
                                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                                  <XAxis dataKey="label" stroke="#8b919e" tickLine={false} axisLine={false} />
                                  <YAxis stroke="#8b919e" tickLine={false} axisLine={false} width={90} />
                                  <Tooltip
                                    contentStyle={{
                                      background: '#111318',
                                      border: '1px solid rgba(255,255,255,0.08)',
                                      borderRadius: 10,
                                      color: '#dde1ea',
                                    }}
                                    labelStyle={{ color: '#dde1ea' }}
                                  />
                                  <Area type="monotone" dataKey="equity" stroke="#9b7fe8" fill="url(#equityFill)" strokeWidth={2} />
                                  <Area type="monotone" dataKey="totalPnl" stroke="#3ecf8e" fill="url(#pnlFill)" strokeWidth={2} />
                                </AreaChart>
                              </ResponsiveContainer>
                            ) : (
                              <div className="theater-empty">No performance snapshots recorded yet.</div>
                            )}
                          </div>
                        </section>

                        <div className="content-grid two-up-tight">
                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Benchmark baselines</h3>
                            </div>
                            <div className="theater-meta-grid">
                              {performanceBenchmarks.length ? performanceBenchmarks.map((benchmark) => (
                                <div key={benchmark.symbol} className="theater-meta-card">
                                  <span>{benchmark.symbol}</span>
                                  <strong>{percent(benchmark.return_pct || 0)}</strong>
                                  <small>{currency(benchmark.price || 0)} vs {currency(benchmark.baseline_price || 0)}</small>
                                </div>
                              )) : (
                                <div className="theater-empty">No benchmark baseline initialized yet.</div>
                              )}
                            </div>
                          </section>

                          <section className="content-section">
                            <div className="section-header section-header-tight">
                              <h3 className="section-subtitle">Inception state</h3>
                            </div>
                            <div className="theater-meta-grid">
                              <div className="theater-meta-card">
                                <span>Inception equity</span>
                                <strong>{currency(performanceSummary?.inception_snapshot?.equity || 0)}</strong>
                                <small>{formatDateTime(performanceSummary?.inception_snapshot?.recorded_at)}</small>
                              </div>
                              <div className="theater-meta-card">
                                <span>Latest cash</span>
                                <strong>{currency(performanceLatest?.cash || 0)}</strong>
                                <small>{currency(performanceLatest?.market_value || 0)} market value</small>
                              </div>
                              <div className="theater-meta-card">
                                <span>Realized PnL</span>
                                <strong>{currency(performanceLatest?.realized_pnl || 0)}</strong>
                                <small>{currency(performanceLatest?.unrealized_pnl || 0)} unrealized</small>
                              </div>
                              <div className="theater-meta-card">
                                <span>Win rate</span>
                                <strong>{percent(performanceLatest?.win_rate || 0)}</strong>
                                <small>{performanceLatest?.total_trades || 0} total trades</small>
                              </div>
                            </div>
                          </section>
                        </div>

                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <h2 className="section-title">Recent snapshots</h2>
                          </div>
                          {performanceRecentSnapshots.length ? (
                            <div className="performance-snapshot-table">
                              <div className="performance-snapshot-head">
                                <span>Recorded</span>
                                <span>Kind</span>
                                <span>Equity</span>
                                <span>Total PnL</span>
                                <span>Win Rate</span>
                                <span>Trades</span>
                              </div>
                              {performanceRecentSnapshots.map((row) => (
                                <div key={row.snapshot_id} className="performance-snapshot-row">
                                  <span>{formatDateTime(row.recorded_at)}</span>
                                  <span>{row.snapshot_kind}</span>
                                  <span>{currency(row.equity)}</span>
                                  <span>{currency(row.total_pnl)}</span>
                                  <span>{percent(row.win_rate || 0)}</span>
                                  <span>{row.total_trades || 0}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="theater-empty">No stored snapshots yet.</div>
                          )}
                        </section>
                      </div>
                    )}

                    {activeTab === 'deliverables' && (
                      <div className="tab-decisions">
                        <section className="content-section">
                          <div className="section-header section-header-tight">
                            <div>
                              <div className="theater-kicker">Knowledge Base</div>
                              <h2 className="section-title">Trace graph</h2>
                            </div>
                          </div>
                          <KnowledgeTraceGraph
                            reports={reports}
                            posts={posts}
                            lineageRows={lineageRows}
                            onSelectReport={openDeliverable}
                            onSelectPost={openDeliverable}
                          />
                        </section>
                        <section className="content-section">
                          <h2 className="section-title">KB Documents</h2>
                          {renderFeedRows(reportDeliverables, 'No KB documents available.', {
                            selectable: true,
                            onSelect: openDeliverable,
                            selectedId: selectedContext?.id,
                            openLabel: 'Inspect',
                          })}
                        </section>
                        <section className="content-section">
                          <h2 className="section-title">Editorial Output</h2>
                          {renderFeedRows(blogDeliverables, 'No blog output available.', {
                            selectable: true,
                            onSelect: openDeliverable,
                            selectedId: selectedContext?.id,
                            openLabel: 'Inspect',
                          })}
                        </section>
                      </div>
                    )}

                    {activeTab === 'decisions' && (
                      <div className="tab-decisions">
                        <section className="content-section">
                          <h2 className="section-title">Decision Queue</h2>
                          <DecisionQueue expanded />
                        </section>
                        <section className="content-section">
                          <h2 className="section-title">Lineage and Traceability</h2>
                          <LineagePanel />
                        </section>
                      </div>
                    )}

                    {activeTab === 'risk' && (
                      <div className="tab-risk">
                        <section className="content-section">
                          <h2 className="section-title">Risk Control</h2>
                          <RiskGauges metrics={metrics} expanded />
                        </section>
                        <section className="content-section">
                          <h2 className="section-title">Runtime Memory State</h2>
                          <div className="theater-meta-grid">
                            <div className="theater-meta-card">
                              <span>Canonical Store</span>
                              <strong>{knowledgeStats?.canonical_store || 'sqlite'}</strong>
                            </div>
                            <div className="theater-meta-card">
                              <span>Projection Store</span>
                              <strong>{knowledgeStats?.projection_store || 'filesystem_notes'}</strong>
                            </div>
                            <div className="theater-meta-card">
                              <span>Events</span>
                              <strong>{knowledgeStats?.event_count ?? 'n/a'}</strong>
                            </div>
                            <div className="theater-meta-card">
                              <span>Graphify Sync</span>
                              <strong>{knowledgeStats?.graphify_sync_enabled ? 'Enabled' : 'Disabled'}</strong>
                            </div>
                          </div>
                        </section>
                      </div>
                    )}

                    {activeTab === 'positions' && (
                      <div className="tab-positions">
                        <section className="content-section">
                          <h2 className="section-title">Portfolio Positions</h2>
                          <PositionsPanel />
                        </section>
                      </div>
                    )}

                    {activeTab === 'settings' && (
                      <div className="tab-settings">
                        <section className="content-section">
                          <h2 className="section-title">Runtime and Knowledge Controls</h2>
                          <div className="settings-panel">
                            <div className="setting-group">
                              <h3>Runtime</h3>
                              <div className="setting-runtime-meta">
                                <div className="setting-runtime-row">
                                  <span>Runtime</span>
                                  <strong>{runtimeControl?.runtime_started ? 'Running' : 'Paused'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Halt</span>
                                  <strong>{systemStatus?.halt?.halted ? 'Active' : 'Clear'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Autopilot</span>
                                  <strong>{runtimeControl?.autopilot?.enabled ? 'Enabled' : 'Disabled'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Last Update</span>
                                  <strong>{formatDateTime(lastUpdate)}</strong>
                                </div>
                              </div>
                            </div>

                            <div className="setting-group">
                              <h3>Knowledge Base Policy</h3>
                              <p className="setting-desc">
                                SQL is the canonical runtime memory store. Filesystem graph notes are a projection layer only.
                              </p>
                              <div className="setting-runtime-meta">
                                <div className="setting-runtime-row">
                                  <span>Canonical Store</span>
                                  <strong>{knowledgeStats?.canonical_store || 'sqlite'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Projection</span>
                                  <strong>{knowledgeStats?.projection_store || 'filesystem_notes'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Events</span>
                                  <strong>{knowledgeStats?.event_count ?? 'n/a'}</strong>
                                </div>
                                <div className="setting-runtime-row">
                                  <span>Graphify Sync</span>
                                  <strong>{knowledgeStats?.graphify_sync_enabled ? 'Enabled' : 'Disabled'}</strong>
                                </div>
                              </div>
                            </div>

                            <div className="setting-group">
                              <h3>CEO Allocation Editor</h3>
                              <p className="setting-desc">
                                This is the policy that constrains orchestration, discovery follow-through, and execution approval across asset classes.
                              </p>
                              <div className="allocation-editor-grid">
                                <label className="allocation-editor-field">
                                  <span>Total capital (USD)</span>
                                  <input
                                    type="number"
                                    min="0"
                                    value={allocationDraft.totalCapitalUsd}
                                    onChange={(e) => setAllocationDraft((prev) => ({ ...prev, totalCapitalUsd: Number(e.target.value) }))}
                                  />
                                </label>
                                <label className="allocation-editor-field">
                                  <span>Reserve cash (USD)</span>
                                  <input
                                    type="number"
                                    min="0"
                                    value={allocationDraft.reserveCashUsd}
                                    onChange={(e) => setAllocationDraft((prev) => ({ ...prev, reserveCashUsd: Number(e.target.value) }))}
                                  />
                                </label>
                              </div>
                              <div className="allocation-editor-block">
                                <h4>Asset-class weights (%)</h4>
                                <div className="allocation-editor-grid">
                                  {Object.entries(allocationDraft.assetWeights).map(([key, value]) => (
                                    <label key={key} className="allocation-editor-field">
                                      <span>{key.replace(/_/g, ' ')}</span>
                                      <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        value={value}
                                        onChange={(e) => updateAllocationDraftGroup('assetWeights', key, e.target.value)}
                                      />
                                    </label>
                                  ))}
                                </div>
                              </div>
                              <div className="allocation-editor-block">
                                <h4>Sleeve weights (%)</h4>
                                <div className="allocation-editor-grid">
                                  {Object.entries(allocationDraft.sleeveWeights).map(([key, value]) => (
                                    <label key={key} className="allocation-editor-field">
                                      <span>{key.replace(/_/g, ' ')}</span>
                                      <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        value={value}
                                        onChange={(e) => updateAllocationDraftGroup('sleeveWeights', key, e.target.value)}
                                      />
                                    </label>
                                  ))}
                                </div>
                              </div>
                              <div className="allocation-editor-block">
                                <h4>Risk constraints (%)</h4>
                                <div className="allocation-editor-grid">
                                  {Object.entries(allocationDraft.constraints).map(([key, value]) => (
                                    <label key={key} className="allocation-editor-field">
                                      <span>{key.replace(/_/g, ' ')}</span>
                                      <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        value={value}
                                        onChange={(e) => updateAllocationDraftGroup('constraints', key, e.target.value)}
                                      />
                                    </label>
                                  ))}
                                </div>
                              </div>
                              <div className="setting-actions">
                                <button type="button" className="btn-secondary" onClick={saveAllocationPolicy} disabled={allocationSaving}>
                                  {allocationSaving ? 'Saving...' : 'Save allocation policy'}
                                </button>
                              </div>
                            </div>
                          </div>
                        </section>
                      </div>
                    )}
                  </div>

                  <aside className="admin-context-rail">
                    <section className="context-panel">
                      <div className="context-panel-head">
                        <div>
                          <div className="context-kicker">Persistent Rail</div>
                          <h3>Command Context</h3>
                        </div>
                        <button type="button" className="context-clear-btn" onClick={() => setSelectedContext(null)}>
                          Clear
                        </button>
                      </div>
                      <div className="context-rail-tabs">
                        <button type="button" className={`context-rail-tab ${contextRailTab === 'focus' ? 'active' : ''}`} onClick={() => setContextRailTab('focus')}>Focus</button>
                        <button type="button" className={`context-rail-tab ${contextRailTab === 'audit' ? 'active' : ''}`} onClick={() => setContextRailTab('audit')}>Audit</button>
                        <button type="button" className={`context-rail-tab ${contextRailTab === 'memory' ? 'active' : ''}`} onClick={() => setContextRailTab('memory')}>Memory</button>
                      </div>
                      <div className="context-selected-title">
                        {contextRailTab === 'focus' ? (selectedContext?.title || 'No focus selected') : contextRailTab === 'audit' ? 'Operator audit stream' : 'Knowledge and memory'}
                      </div>
                      <div className="context-selected-subtitle">
                        {contextRailTab === 'focus'
                          ? (selectedContext?.subtitle || 'Pin any item from the main canvas')
                          : contextRailTab === 'audit'
                            ? 'Recent control decisions, halt state, and queue pressure'
                            : 'Canonical KB status, projection health, and memory load'}
                      </div>
                      {contextRailTab === 'focus' ? renderContextBody() : null}
                      {contextRailTab === 'audit' ? renderAuditRail() : null}
                      {contextRailTab === 'memory' ? renderMemoryRail() : null}
                    </section>

                    <section className="context-panel">
                      <div className="context-panel-head">
                        <div>
                          <div className="context-kicker">Pinned Streams</div>
                          <h3>Live Queue</h3>
                        </div>
                      </div>
                      {renderFeedRows(recentTaskRows.slice(0, 5), 'No active tasks.', {
                        selectable: true,
                        onSelect: (row) => openTaskContext(row.data),
                        selectedId: selectedContext?.id,
                        openLabel: 'Pin',
                      })}
                    </section>
                  </aside>
                </div>
              </>
            )}
          </div>
        </main>
      </div>
      {deliverableDrawerOpen && ['research', 'blog'].includes(selectedContext?.kind || '') ? (
        <div className="deliverable-drawer-backdrop" onClick={() => setDeliverableDrawerOpen(false)}>
          <aside className="deliverable-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="deliverable-drawer-head">
              <div>
                <div className="context-kicker">Deliverable Inspect</div>
                <h3>{selectedContext?.title || 'Deliverable'}</h3>
                <div className="context-selected-subtitle">{selectedContext?.subtitle || 'Research or blog output'}</div>
              </div>
              <button type="button" className="context-clear-btn" onClick={() => setDeliverableDrawerOpen(false)}>
                Close
              </button>
            </div>
            {renderDeliverableDrawerBody()}
          </aside>
        </div>
      ) : null}
    </>
  );
};

export default Admin;
