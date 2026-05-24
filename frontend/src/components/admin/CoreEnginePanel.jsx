import React, { useMemo } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bot,
  Database,
  LineChart,
  Shield,
  Sigma,
  TrendingUp,
  Workflow,
} from 'lucide-react';

const titleize = (value) =>
  String(value || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const money = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });

const percent = (value, digits = 0) => `${(Number(value || 0) * 100).toFixed(digits)}%`;

const signed = (value, digits = 2) => {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${number.toFixed(digits)}`;
};

const average = (rows, getter) => {
  const values = rows
    .map((row) => Number(getter(row)))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
};

const compactList = (values, limit = 3) => {
  const items = Array.from(
    new Set(
      (Array.isArray(values) ? values : [])
        .map((value) => String(value || '').trim())
        .filter(Boolean)
    )
  );
  if (!items.length) return '';
  const head = items.slice(0, limit).join(', ');
  return items.length > limit ? `${head} +${items.length - limit}` : head;
};

const summarize = (value, max = 140) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return 'No operator note published yet.';
  return text.length > max ? `${text.slice(0, max)}...` : text;
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

const toneClass = (tone) => {
  if (tone === 'ok') return 'is-good';
  if (tone === 'bad') return 'is-bad';
  return 'is-wait';
};

const statusLabel = (tone) => {
  if (tone === 'ok') return 'Live';
  if (tone === 'bad') return 'Blocked';
  return 'Pending';
};

const describeNewsGuard = (newsStream) => {
  const reason = String(newsStream?.disable_reason || '').trim();
  if (!reason) return '';
  if (reason === 'parallel_alpaca_ws_disabled') {
    return 'News stream is intentionally parked while the market websocket owns the Alpaca connection budget.';
  }
  return `${titleize(reason)} is constraining the parallel news feed.`;
};

export default function CoreEnginePanel({
  backendTarget,
  connectionStatus,
  systemStatus,
  workersStatus,
  pipelineStatus,
  mlStatus,
  riskStatus,
  mlEffectiveness,
  currentSentiment,
  decisionScoringRows,
  pendingApprovalRows,
  latestNoTradeDiscovery,
  paperSummary,
  performanceLatest,
  reportDeliverables,
  blogDeliverables,
  onOpenApproval,
  onOpenDeliverable,
}) {
  const disconnected = connectionStatus !== 'connected';
  const reports = Array.isArray(reportDeliverables) ? reportDeliverables : [];
  const approvals = Array.isArray(pendingApprovalRows) ? pendingApprovalRows : [];
  const scoringRows = Array.isArray(decisionScoringRows) ? decisionScoringRows : [];
  const mlRows = Array.isArray(mlEffectiveness?.positions_with_ml_context)
    ? mlEffectiveness.positions_with_ml_context
    : [];
  const sentimentRows = Array.isArray(currentSentiment?.snapshots) ? currentSentiment.snapshots : [];
  const profiles = Array.isArray(mlStatus?.core_engine?.available_profiles)
    ? mlStatus.core_engine.available_profiles
    : [];
  const providerHealth = pipelineStatus?.provider_health || {};
  const stream = pipelineStatus?.stream || {};
  const newsStream = pipelineStatus?.news_stream || {};
  const latestRun = pipelineStatus?.last_run || {};
  const latestRunCounts = latestRun?.counts || {};
  const latestScoring = scoringRows[0] || null;
  const latestApproval = approvals[0] || null;
  const latestSentiment = sentimentRows[0] || null;
  const topMlRow = mlRows[0] || null;
  const selectedCount = Number(systemStatus?.discovery?.status_counts?.selected || 0);
  const qualifiedCount = Number(systemStatus?.discovery?.status_counts?.qualified || 0);
  const latestRunQualityRows = useMemo(
    () =>
      Object.entries(latestRun?.quality || {})
        .map(([symbol, row]) => ({
          symbol,
          featureCategory: row?.features?.category || row?.status || 'unknown',
          featureScore: Number(row?.features?.score || 0),
          row,
        }))
        .sort((left, right) => right.featureScore - left.featureScore),
    [latestRun]
  );
  const tradeCandidateRows = latestRunQualityRows.filter((row) => row.featureCategory === 'trade_candidate');
  const watchlistRows = latestRunQualityRows.filter((row) => row.featureCategory === 'watchlist');
  const activeProfileConfig = profiles.find((row) => row?.name === mlStatus?.core_engine?.active_profile) || null;
  const newsGuardSummary = describeNewsGuard(newsStream);
  const supportLayerState = workersStatus?.ai_role_adapter?.enabled
    ? titleize(workersStatus?.ai_role_adapter?.provider || workersStatus?.ai_role_adapter?.mode || 'configured')
    : 'Standby';
  const supportLayerDetail = workersStatus?.ai_role_adapter?.enabled
    ? `${workersStatus?.ai_role_adapter?.default_model || 'model pending'} for research and editorial support.`
    : `Configured through ${workersStatus?.ai_role_adapter?.provider || 'router'} and kept off the trade path.`;
  const reportByRole = useMemo(() => {
    const bucket = {
      technical_analyst: null,
      fundamental_analyst: null,
      sentiment_analyst: null,
      ml_timeseries_analyst: null,
    };
    for (const report of reports) {
      const role = report?.data?.agent_role || report?.data?.agentRole;
      if (role && bucket[role] == null) {
        bucket[role] = report;
      }
    }
    return bucket;
  }, [reports]);

  const reportCountsByRole = useMemo(
    () =>
      reports.reduce((acc, report) => {
        const role = report?.data?.agent_role || report?.data?.agentRole || 'unknown';
        acc[role] = Number(acc[role] || 0) + 1;
        return acc;
      }, {}),
    [reports]
  );

  const avgTechnical = average(scoringRows, (row) => row?.raw?.ml?.technical_confidence);
  const avgRegime = average(scoringRows, (row) => row?.raw?.ml?.regime_alignment);
  const avgLiquidity = average(scoringRows, (row) => row?.raw?.ml?.liquidity_score);
  const avgVolatility = average(scoringRows, (row) => row?.raw?.ml?.volatility_score);
  const avgScore = average(scoringRows, (row) => row?.score);
  const avgConfidence = average(scoringRows, (row) => row?.confidence);
  const avgSentiment = average(sentimentRows, (row) => row?.sentiment_score);

  const stageRows = useMemo(() => {
    const pipelineTone = disconnected
      ? 'bad'
      : pipelineStatus?.enabled && (pipelineStatus?.running || stream?.subscribed || newsStream?.started)
        ? 'ok'
        : pipelineStatus?.enabled
          ? 'wait'
          : 'bad';

    const technicalTone = disconnected
      ? 'bad'
      : reportCountsByRole.technical_analyst || scoringRows.length
        ? 'ok'
        : 'wait';

    const fundamentalTone = disconnected
      ? 'bad'
      : reportCountsByRole.fundamental_analyst
        ? 'ok'
        : 'wait';

    const sentimentTone = disconnected
      ? 'bad'
      : sentimentRows.length || reportCountsByRole.sentiment_analyst
        ? 'ok'
        : 'wait';

    const routerTone = disconnected
      ? 'bad'
      : mlStatus?.lgbm?.ready || mlStatus?.core_engine?.active_profile
        ? 'ok'
        : mlStatus?.lgbm?.training
          ? 'wait'
          : 'wait';

    const fusionTone = disconnected
      ? 'bad'
      : latestScoring
        ? 'ok'
        : 'wait';

    const policyTone = systemStatus?.halt?.halted
      ? 'bad'
      : latestNoTradeDiscovery || approvals.length
        ? 'wait'
        : disconnected
          ? 'bad'
          : 'ok';

    const intentTone = disconnected
      ? 'bad'
      : paperSummary?.count || performanceLatest?.total_trades
        ? 'ok'
        : 'wait';

    return [
      {
        key: 'data',
        step: '01',
        tone: pipelineTone,
        icon: Database,
        title: 'Data Integrity',
        summary: disconnected
          ? 'Backend unreachable. The surface is preserving the operating contract but cannot verify live freshness.'
          : pipelineStatus?.enabled
            ? `Scheduler ${pipelineStatus?.running ? 'running' : 'idle'} across ${Number(pipelineStatus?.configured_symbols?.length || 0)} symbols, with ${Number(latestRunCounts?.prices || 0)} price refreshes and ${Number(latestRunCounts?.text_events || 0)} text events in the latest run.`
            : 'Pipeline is disabled, so deterministic layers cannot validate canonical freshness.',
        metrics: [
          { label: 'Universe', value: String(pipelineStatus?.configured_symbols?.length || 0) },
          { label: 'Prices', value: Number(latestRunCounts?.prices || stream?.tick_count || 0).toLocaleString() },
          { label: 'Providers', value: String(Object.keys(providerHealth).length || 0) },
          { label: 'Last run', value: formatRelative(pipelineStatus?.last_run?.completed_at || pipelineStatus?.last_run?.started_at || pipelineStatus?.last_run) },
        ],
        note: newsGuardSummary ? summarize(newsGuardSummary) : '',
      },
      {
        key: 'technical',
        step: '02',
        tone: technicalTone,
        icon: TrendingUp,
        title: 'Technical Pack',
        summary: latestScoring
          ? `${Math.round(Number(avgTechnical || 0) * 100)}% average technical confidence across ${scoringRows.length} discovery packets.`
          : tradeCandidateRows.length
            ? `${tradeCandidateRows.length} trade candidates surfaced in the latest scheduled pass led by ${compactList(tradeCandidateRows.map((row) => row.symbol), 3)}.`
          : disconnected
            ? 'Reconnect to inspect live technical model output.'
            : 'No technical scoring packets have been published yet.',
        metrics: latestScoring
          ? [
              { label: 'Reports', value: String(reportCountsByRole.technical_analyst || 0) },
              { label: 'Regime', value: avgRegime == null ? 'n/a' : percent(avgRegime) },
              { label: 'Liquidity', value: avgLiquidity == null ? 'n/a' : percent(avgLiquidity) },
              { label: 'Volatility', value: avgVolatility == null ? 'n/a' : percent(avgVolatility) },
            ]
          : [
              { label: 'Reports', value: String(reportCountsByRole.technical_analyst || 0) },
              { label: 'Candidates', value: String(tradeCandidateRows.length) },
              { label: 'Watchlist', value: String(watchlistRows.length) },
              { label: 'Last run', value: formatRelative(latestRun?.finished_at || latestRun?.started_at) },
            ],
        note: latestScoring
          ? summarize(latestScoring.mathSummary)
          : summarize(reportByRole.technical_analyst?.preview || `Latest ranked symbols: ${compactList(tradeCandidateRows.map((row) => row.symbol), 4) || 'no ranked symbols yet'}.`),
      },
      {
        key: 'fundamental',
        step: '03',
        tone: fundamentalTone,
        icon: LineChart,
        title: 'Fundamental Pack',
        summary: reportCountsByRole.fundamental_analyst
          ? `${reportCountsByRole.fundamental_analyst} fundamental analyst packets are available in the KB projection.`
          : Number(latestRunCounts?.fundamentals || 0) === 0 && latestRunQualityRows.length
            ? 'Fundamental refresh is cadence-controlled, so the latest run reused the valuation base instead of forcing a stale pass.'
          : disconnected
            ? 'No live fundamental telemetry while the backend is offline.'
            : 'The backend has not emitted explicit fundamental pack telemetry into the operator surface yet.',
        metrics: [
          { label: 'Packets', value: String(reportCountsByRole.fundamental_analyst || 0) },
          { label: 'Latest', value: formatRelative(reportByRole.fundamental_analyst?.timestamp) },
          { label: 'Cadence', value: Number(latestRunCounts?.fundamentals || 0) > 0 ? 'refreshed' : 'deferred' },
          { label: 'Sleeves', value: String(Object.keys(systemStatus?.allocation_policy?.asset_classes || {}).length) },
        ],
        note: summarize(reportByRole.fundamental_analyst?.preview || 'Fundamental insight remains visible through research packets until dedicated pack diagnostics are exposed.'),
      },
      {
        key: 'sentiment',
        step: '04',
        tone: sentimentTone,
        icon: Activity,
        title: 'Sentiment Pack',
        summary: latestSentiment
          ? `${latestSentiment.symbol} leads recent sentiment at ${signed(latestSentiment.sentiment_score)} with ${percent(latestSentiment.confidence)} confidence.`
          : Number(latestRunCounts?.text_events || 0) > 0
            ? `${Number(latestRunCounts.text_events || 0)} text events were ingested in the latest run even though no aggregate sentiment snapshot has been published yet.`
          : disconnected
            ? 'Sentiment snapshots are unavailable while the backend is disconnected.'
            : 'No current sentiment snapshots have been published yet.',
        metrics: [
          { label: 'Snapshots', value: String(sentimentRows.length) },
          { label: 'Net score', value: avgSentiment == null ? 'n/a' : signed(avgSentiment, 3) },
          { label: 'News flow', value: String(newsStream?.event_count || 0) },
          { label: 'Reports', value: String(reportCountsByRole.sentiment_analyst || 0) },
        ],
        note: summarize(reportByRole.sentiment_analyst?.preview || `Latest source: ${latestSentiment?.source || 'no sentiment source reported'}.`),
      },
      {
        key: 'router',
        step: '05',
        tone: routerTone,
        icon: Sigma,
        title: 'Model Router',
        summary: activeProfileConfig
          ? `${titleize(activeProfileConfig.name)} is active with ${percent(activeProfileConfig.min_confidence)} minimum confidence and ${percent(activeProfileConfig.min_expected_utility)} expected-utility floor.`
          : disconnected
            ? 'Model readiness cannot be verified while the backend is offline.'
            : 'Waiting for model readiness and profile routing telemetry.',
        metrics: [
          { label: 'LGBM', value: mlStatus?.lgbm?.ready ? 'ready' : mlStatus?.lgbm?.training ? 'training' : 'offline' },
          { label: 'Features', value: String(mlStatus?.lgbm?.features ?? 0) },
          { label: 'Profiles', value: String(profiles.length) },
          { label: 'Min conf', value: activeProfileConfig ? percent(activeProfileConfig.min_confidence) : 'n/a' },
        ],
        note: topMlRow
          ? summarize(`${topMlRow.symbol} is the current lead ML context row with ${topMlRow.strategy_family} and ${money(topMlRow.unrealized_pnl)} unrealized PnL.`)
          : summarize('Champion and challenger routing still needs live rows before the operator surface can rank effectiveness.'),
      },
      {
        key: 'fusion',
        step: '06',
        tone: fusionTone,
        icon: Workflow,
        title: 'Fusion And Scoring',
        summary: latestScoring
          ? `${selectedCount} selected candidates with ${avgScore == null ? 'n/a' : Number(avgScore).toFixed(3)} average score and ${avgConfidence == null ? 'n/a' : percent(avgConfidence)} confidence.`
          : tradeCandidateRows.length
            ? `${tradeCandidateRows.length} names cleared raw candidate scoring, but no fused decision packet has been emitted yet.`
          : disconnected
            ? 'Fusion telemetry is unavailable while the backend is offline.'
            : 'No fused decision packets have reached the operator surface yet.',
        metrics: [
          { label: 'Selected', value: String(selectedCount) },
          { label: 'Qualified', value: String(qualifiedCount) },
          { label: 'Signal packs', value: String(workersStatus?.signal_packs?.length || 0) },
          { label: 'Top side', value: latestScoring?.direction || 'n/a' },
        ],
        note: summarize(
          latestScoring?.mathSummary ||
          latestNoTradeDiscovery?.thesis ||
          (tradeCandidateRows.length
            ? `Current candidate queue: ${compactList(tradeCandidateRows.map((row) => row.symbol), 4)}.`
            : '')
        ),
      },
      {
        key: 'policy',
        step: '07',
        tone: policyTone,
        icon: Shield,
        title: 'Policy Gate',
        summary: systemStatus?.halt?.halted
          ? `Runtime halted: ${systemStatus?.halt?.reason || 'quality gate engaged'}.`
          : latestNoTradeDiscovery
            ? `Cash hold directive active because ${latestNoTradeDiscovery?.metadata?.discovery_reason || 'thresholds were not met'}.`
            : approvals.length
              ? `${approvals.length} approvals are waiting at the deterministic policy boundary.`
              : 'No active gate blocks or pending approvals are reported.',
        metrics: [
          { label: 'Approvals', value: String(approvals.length) },
          { label: 'Drawdown', value: percent(riskStatus?.drawdown_breaker?.current_drawdown, 2) },
          { label: 'Stops', value: String((riskStatus?.open_stops || []).length) },
          { label: 'Halt', value: systemStatus?.halt?.halted ? 'active' : 'clear' },
        ],
        note: latestApproval
          ? summarize(latestApproval.preview)
          : summarize(latestNoTradeDiscovery?.thesis || 'Gate thresholds remain explicit even when no approvals or blocks are currently active.'),
      },
      {
        key: 'intent',
        step: '08',
        tone: intentTone,
        icon: Bot,
        title: 'Intent And Execution',
        summary: paperSummary?.count
          ? `${paperSummary.count} paper positions are live with ${money(paperSummary.equity)} deployed.`
          : performanceLatest?.total_trades
            ? `${performanceLatest.total_trades} paper trades recorded with ${money(performanceLatest.total_pnl)} total PnL.`
            : disconnected
              ? 'Execution telemetry is unavailable while the backend is offline.'
              : 'No emitted intents have reached paper execution yet.',
        metrics: [
          { label: 'Positions', value: String(paperSummary?.count || 0) },
          { label: 'Equity', value: money(paperSummary?.equity || performanceLatest?.equity) },
          { label: 'PnL', value: money(performanceLatest?.total_pnl || paperSummary?.unrealized) },
          { label: 'Trades', value: String(performanceLatest?.total_trades || 0) },
        ],
      },
    ];
  }, [
    approvals.length,
    avgConfidence,
    avgLiquidity,
    avgRegime,
    avgScore,
    avgSentiment,
    avgTechnical,
    avgVolatility,
    connectionStatus,
    disconnected,
    latestApproval,
    latestRun,
    latestRunCounts,
    latestRunQualityRows.length,
    latestNoTradeDiscovery,
    latestScoring,
    latestSentiment,
    mlEffectiveness?.count,
    mlRows.length,
    mlStatus,
    newsStream?.event_count,
    paperSummary,
    performanceLatest,
    pipelineStatus,
    profiles.length,
    providerHealth,
    qualifiedCount,
    reportByRole.fundamental_analyst,
    reportByRole.sentiment_analyst,
    reportByRole.technical_analyst,
    reportCountsByRole.fundamental_analyst,
    reportCountsByRole.sentiment_analyst,
    reportCountsByRole.technical_analyst,
    riskStatus,
    scoringRows.length,
    selectedCount,
    sentimentRows.length,
    stream?.subscribed,
    stream?.tick_count,
    systemStatus,
    topMlRow,
    tradeCandidateRows,
    watchlistRows.length,
    workersStatus?.signal_packs?.length,
    activeProfileConfig,
    newsGuardSummary,
  ]);

  const supportLayerRows = [
    {
      label: 'Research support',
      value: String(reports.length),
      detail: reportByRole.fundamental_analyst?.title || reportByRole.technical_analyst?.title || 'No research packet ready.',
      action: reportByRole.fundamental_analyst || reportByRole.technical_analyst,
      actionLabel: 'Open packet',
    },
    {
      label: 'Editorial outputs',
      value: String(blogDeliverables?.length || 0),
      detail: blogDeliverables?.[0]?.title || 'No blog output queued.',
      action: blogDeliverables?.[0] || null,
      actionLabel: 'Open draft',
    },
      {
        label: 'AI adapter',
        value: supportLayerState,
        detail: supportLayerDetail,
        action: null,
        actionLabel: '',
      },
  ];

  const signalLaneRows = scoringRows.slice(0, 4);

  return (
    <div className="tab-core-engine">
      <section className="content-section core-engine-hero">
        <div className="section-header section-header-tight core-engine-hero-head">
          <div>
            <div className="theater-kicker">Deterministic ML-Native Console</div>
            <h2 className="section-title">Core Engine</h2>
            <p className="core-engine-hero-copy">
              Trade intent flows through deterministic layers only. The AI layer stays in the app for research,
              memory, and publication support, but not for trade-side decision authority.
            </p>
          </div>
          <div className="core-engine-hero-pills">
            <span className={`command-pill ${disconnected ? 'is-bad' : 'is-good'}`}>
              <Sigma size={13} />
              {mlStatus?.core_engine?.active_profile ? titleize(mlStatus.core_engine.active_profile) : 'profile pending'}
            </span>
            <span className={`command-pill ${systemStatus?.halt?.halted ? 'is-bad' : 'is-good'}`}>
              <Shield size={13} />
              {systemStatus?.halt?.halted ? 'gate halted' : 'gate clear'}
            </span>
            <span className="command-pill">
              <Bot size={13} />
              AI assist off trade path
            </span>
          </div>
        </div>

        <div className="core-engine-route">
          {[
            'Data',
            'Technical',
            'Fundamental',
            'Sentiment',
            'Model Router',
            'Fusion',
            'Policy',
            'Intent',
          ].map((step, index, rows) => (
            <React.Fragment key={step}>
              <div className="core-engine-route-step">{step}</div>
              {index < rows.length - 1 ? <ArrowRight size={14} className="core-engine-route-arrow" /> : null}
            </React.Fragment>
          ))}
          <div className="core-engine-route-divider" />
          <div className="core-engine-route-support">AI Support Layer</div>
        </div>

        <div className="core-status-strip">
          <article className="core-status-card">
            <span>Pipeline</span>
            <strong>{pipelineStatus?.running ? 'Scheduler live' : pipelineStatus?.enabled ? 'Idle' : 'Offline'}</strong>
            <small>
              {String(pipelineStatus?.configured_symbols?.length || 0)} symbols | {Number(latestRunCounts?.prices || stream?.tick_count || 0).toLocaleString()} prices | {Number(latestRunCounts?.text_events || newsStream?.event_count || 0).toLocaleString()} text
            </small>
          </article>
          <article className="core-status-card">
            <span>Model readiness</span>
            <strong>{activeProfileConfig ? titleize(activeProfileConfig.name) : mlStatus?.lgbm?.ready ? 'Ready' : mlStatus?.lgbm?.training ? 'Training' : 'Unavailable'}</strong>
            <small>
              {String(mlStatus?.lgbm?.features ?? 0)} features | {activeProfileConfig ? `${percent(activeProfileConfig.min_confidence)} min conf` : 'profile pending'}
            </small>
          </article>
          <article className="core-status-card">
            <span>Policy boundary</span>
            <strong>{approvals.length ? `${approvals.length} waiting` : systemStatus?.halt?.halted ? 'Halted' : 'Clear'}</strong>
            <small>{money(riskStatus?.equity || paperSummary?.equity)} equity | {percent(riskStatus?.drawdown_breaker?.current_drawdown, 2)} drawdown</small>
          </article>
          <article className="core-status-card support">
            <span>Support layer</span>
            <strong>{supportLayerState}</strong>
            <small>{supportLayerDetail}</small>
          </article>
        </div>

        {disconnected ? (
          <div className="core-engine-alert">
            <AlertCircle size={16} />
            <div>
              <strong>Backend unreachable</strong>
              <p>
                Live deterministic telemetry is unavailable because the admin surface cannot reach{' '}
                <code>{backendTarget}</code>. The UI is staying honest about unknown state instead of painting false green checks.
              </p>
            </div>
          </div>
        ) : null}
      </section>

      <section className="content-section">
        <div className="section-header section-header-tight">
          <div>
            <div className="theater-kicker">Layer Telemetry</div>
            <h2 className="section-title">Deterministic decision path</h2>
          </div>
        </div>
        <div className="core-stage-grid">
          {stageRows.map((row) => {
            const Icon = row.icon;
            return (
              <article key={row.key} className="core-stage-card">
                <div className="core-stage-head">
                  <div className="core-stage-title-wrap">
                    <span className="core-stage-step">{row.step}</span>
                    <Icon size={18} />
                    <div>
                      <h3>{row.title}</h3>
                      <p>{row.summary}</p>
                    </div>
                  </div>
                  <span className={`core-stage-tone ${toneClass(row.tone)}`}>{statusLabel(row.tone)}</span>
                </div>
                <div className="core-stage-metrics">
                  {row.metrics.map((metric) => (
                    <div key={`${row.key}-${metric.label}`} className="core-stage-metric">
                      <span>{metric.label}</span>
                      <strong>{metric.value}</strong>
                    </div>
                  ))}
                </div>
                {row.note ? <div className="core-stage-note">{row.note}</div> : null}
              </article>
            );
          })}
        </div>
      </section>

      <div className="content-grid two-up-tight">
        <section className="content-section">
          <div className="section-header section-header-tight">
            <div>
              <div className="theater-kicker">Operator Focus</div>
              <h2 className="section-title">Signal lane</h2>
            </div>
          </div>
          <div className="core-focus-list">
            {signalLaneRows.length ? (
              signalLaneRows.map((row) => (
                <article key={row.id} className="core-focus-card">
                  <div className="core-focus-head">
                    <div>
                      <strong>{row.symbol}</strong>
                      <span>{row.assetClass} · {row.direction}</span>
                    </div>
                    <span className="deliverable-pill">{Number(row.score || 0).toFixed(3)}</span>
                  </div>
                  <p>{row.mathSummary}</p>
                  <div className="core-focus-meta">
                    <span className="deliverable-pill subdued">Confidence {percent(row.confidence)}</span>
                    <span className="deliverable-pill subdued">Regime {row.metrics?.[2]?.value || 'n/a'}</span>
                    <span className="deliverable-pill subdued">Liquidity {row.metrics?.[3]?.value || 'n/a'}</span>
                  </div>
                </article>
              ))
            ) : (
              <div className="core-empty-state">
                No fused signal packets are available yet. Once the backend emits deterministic discovery rows, the lead lane will show score math here.
              </div>
            )}

            {latestApproval ? (
              <div className="core-inline-action">
                <div>
                  <strong>Latest approval boundary</strong>
                  <span>{latestApproval.title}</span>
                </div>
                <button type="button" className="btn-secondary" onClick={() => onOpenApproval?.(latestApproval)}>
                  Open approval
                </button>
              </div>
            ) : null}
          </div>
        </section>

        <section className="content-section">
          <div className="section-header section-header-tight">
            <div>
              <div className="theater-kicker">Support Layer</div>
              <h2 className="section-title">AI stays in the app</h2>
            </div>
          </div>
          <div className="core-support-summary">
            <div className="core-support-banner">
              <Bot size={16} />
              <p>
                Support agents can draft research, enrich memory, and prepare editorial output. They do not replace the deterministic
                trade path.
              </p>
            </div>
            <div className="core-support-grid">
              {supportLayerRows.map((row) => (
                <article key={row.label} className="core-support-card">
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                  <p>{row.detail}</p>
                  {row.action ? (
                    <button type="button" className="btn-secondary" onClick={() => onOpenDeliverable?.(row.action)}>
                      {row.actionLabel}
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="core-support-rail">
              <article className="core-support-detail">
                <span>Sentiment lead</span>
                <strong>{latestSentiment ? `${latestSentiment.symbol} ${signed(latestSentiment.sentiment_score)}` : 'No sentiment snapshot'}</strong>
                <small>{latestSentiment ? `${percent(latestSentiment.confidence)} confidence from ${latestSentiment.source}` : 'Awaiting research sentiment feed.'}</small>
              </article>
              <article className="core-support-detail">
                <span>ML effectiveness</span>
                <strong>{topMlRow ? `${topMlRow.symbol} ${money(topMlRow.unrealized_pnl)}` : 'No open-position ML context'}</strong>
                <small>{topMlRow ? `${titleize(topMlRow.strategy_family)} · ${topMlRow.score_bucket}` : 'Waiting for executed paper orders with ML context.'}</small>
              </article>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
