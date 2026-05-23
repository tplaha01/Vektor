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
  const latestScoring = scoringRows[0] || null;
  const latestApproval = approvals[0] || null;
  const latestSentiment = sentimentRows[0] || null;
  const topMlRow = mlRows[0] || null;
  const selectedCount = Number(systemStatus?.discovery?.status_counts?.selected || 0);
  const qualifiedCount = Number(systemStatus?.discovery?.status_counts?.qualified || 0);
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
            ? `Pipeline ${pipelineStatus?.running ? 'running' : 'idle'} with ${Number(pipelineStatus?.configured_symbols?.length || 0)} configured symbols and provider health telemetry.`
            : 'Pipeline is disabled, so deterministic layers cannot validate canonical freshness.',
        metrics: [
          { label: 'Ticks', value: Number(stream?.tick_count || 0).toLocaleString() },
          { label: 'News', value: Number(newsStream?.event_count || 0).toLocaleString() },
          { label: 'Providers', value: String(Object.keys(providerHealth).length || 0) },
          { label: 'Last run', value: formatRelative(pipelineStatus?.last_run?.completed_at || pipelineStatus?.last_run?.started_at || pipelineStatus?.last_run) },
        ],
      },
      {
        key: 'technical',
        step: '02',
        tone: technicalTone,
        icon: TrendingUp,
        title: 'Technical Pack',
        summary: latestScoring
          ? `${Math.round(Number(avgTechnical || 0) * 100)}% average technical confidence across ${scoringRows.length} discovery packets.`
          : disconnected
            ? 'Reconnect to inspect live technical model output.'
            : 'No technical scoring packets have been published yet.',
        metrics: [
          { label: 'Reports', value: String(reportCountsByRole.technical_analyst || 0) },
          { label: 'Regime', value: avgRegime == null ? 'n/a' : percent(avgRegime) },
          { label: 'Liquidity', value: avgLiquidity == null ? 'n/a' : percent(avgLiquidity) },
          { label: 'Volatility', value: avgVolatility == null ? 'n/a' : percent(avgVolatility) },
        ],
        note: latestScoring ? summarize(latestScoring.mathSummary) : summarize(reportByRole.technical_analyst?.preview),
      },
      {
        key: 'fundamental',
        step: '03',
        tone: fundamentalTone,
        icon: LineChart,
        title: 'Fundamental Pack',
        summary: reportCountsByRole.fundamental_analyst
          ? `${reportCountsByRole.fundamental_analyst} fundamental analyst packets are available in the KB projection.`
          : disconnected
            ? 'No live fundamental telemetry while the backend is offline.'
            : 'The backend has not emitted explicit fundamental pack telemetry into the operator surface yet.',
        metrics: [
          { label: 'Packets', value: String(reportCountsByRole.fundamental_analyst || 0) },
          { label: 'Latest', value: formatRelative(reportByRole.fundamental_analyst?.timestamp) },
          { label: 'Docs', value: String(reports.length) },
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
        summary: mlStatus?.core_engine?.active_profile
          ? `${titleize(mlStatus.core_engine.active_profile)} is the active deterministic profile across ${profiles.length} registered profiles.`
          : disconnected
            ? 'Model readiness cannot be verified while the backend is offline.'
            : 'Waiting for model readiness and profile routing telemetry.',
        metrics: [
          { label: 'LGBM', value: mlStatus?.lgbm?.ready ? 'ready' : mlStatus?.lgbm?.training ? 'training' : 'offline' },
          { label: 'Features', value: String(mlStatus?.lgbm?.features ?? 0) },
          { label: 'Profiles', value: String(profiles.length) },
          { label: 'ML context', value: String(mlEffectiveness?.count ?? mlRows.length) },
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
          : disconnected
            ? 'Fusion telemetry is unavailable while the backend is offline.'
            : 'No fused decision packets have reached the operator surface yet.',
        metrics: [
          { label: 'Selected', value: String(selectedCount) },
          { label: 'Qualified', value: String(qualifiedCount) },
          { label: 'Signal packs', value: String(workersStatus?.signal_packs?.length || 0) },
          { label: 'Top side', value: latestScoring?.direction || 'n/a' },
        ],
        note: summarize(latestScoring?.mathSummary || latestNoTradeDiscovery?.thesis),
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
              : 'No active gate blocks reported.',
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
    workersStatus?.signal_packs?.length,
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
      value: workersStatus?.ai_role_adapter?.provider || workersStatus?.ai_role_adapter?.mode || 'offline',
      detail: workersStatus?.ai_role_adapter?.default_model || 'No model configured.',
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
              AI support only
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
            <strong>{pipelineStatus?.running ? 'Streaming' : pipelineStatus?.enabled ? 'Idle' : 'Offline'}</strong>
            <small>{Number(stream?.tick_count || 0).toLocaleString()} ticks and {Number(newsStream?.event_count || 0).toLocaleString()} news events</small>
          </article>
          <article className="core-status-card">
            <span>Model readiness</span>
            <strong>{mlStatus?.lgbm?.ready ? 'Ready' : mlStatus?.lgbm?.training ? 'Training' : 'Unavailable'}</strong>
            <small>{String(mlStatus?.lgbm?.features ?? 0)} engineered features exposed</small>
          </article>
          <article className="core-status-card">
            <span>Policy boundary</span>
            <strong>{approvals.length ? `${approvals.length} waiting` : systemStatus?.halt?.halted ? 'Halted' : 'Clear'}</strong>
            <small>{money(riskStatus?.equity || paperSummary?.equity)} tracked equity</small>
          </article>
          <article className="core-status-card support">
            <span>Support layer</span>
            <strong>{workersStatus?.ai_role_adapter?.provider || workersStatus?.ai_role_adapter?.mode || 'Idle'}</strong>
            <small>Research + editorial assist, out of trade path</small>
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
