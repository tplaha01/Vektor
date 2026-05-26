import React from 'react';
import { Activity, AlertTriangle, BarChart3, Shield, TrendingUp } from 'lucide-react';

const money = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });

const pct = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

const signedPct = (value, digits = 2) => {
  const numeric = Number(value || 0);
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(digits)}%`;
};

const statusTone = (value) => {
  const cleaned = String(value || '').toLowerCase();
  if (cleaned.includes('halt') || cleaned.includes('breach') || cleaned.includes('risk')) return 'bad';
  if (cleaned.includes('degraded') || cleaned.includes('paused') || cleaned.includes('fallback')) return 'caution';
  if (cleaned.includes('healthy') || cleaned.includes('within') || cleaned.includes('clear')) return 'good';
  return 'neutral';
};

function OverviewMetric({ icon: Icon, label, value, detail, tone = 'neutral' }) {
  return (
    <article className={`overview-metric ${tone}`}>
      <div className="overview-metric-head">
        <span className="overview-metric-label">{label}</span>
        <span className="overview-metric-icon"><Icon size={15} /></span>
      </div>
      <strong className="overview-metric-value">{value}</strong>
      <p className="overview-metric-detail">{detail}</p>
    </article>
  );
}

export default function OverviewPanel({ data, onNavigate }) {
  const nav = data?.nav || {};
  const monthlyPnl = data?.monthlyPnl || {};
  const sharpe = data?.sharpe || {};
  const drawdown = data?.drawdown || {};
  const runtime = data?.runtime || {};
  const exposure = data?.exposure || {};
  const risk = data?.risk || {};
  const alerts = Array.isArray(data?.alerts?.alerts) ? data.alerts.alerts : [];

  return (
    <section className="ops-panel overview-panel-shell">
      <div className="ops-panel-header">
        <div>
          <p className="ops-panel-eyebrow">Overview</p>
          <h2 className="ops-panel-title">Fund Status</h2>
          <p className="ops-panel-description">
            Real-time executive view of NAV, runtime, risk posture, and intervention-ready alerts.
          </p>
        </div>
      </div>

      <div className="overview-metric-grid">
        <OverviewMetric
          icon={TrendingUp}
          label="NAV"
          value={money(nav.nav_current)}
          detail={`${signedPct(nav.nav_change_pct)} vs baseline ${money(nav.nav_previous)}`}
          tone={Number(nav.nav_change_pct || 0) >= 0 ? 'good' : 'bad'}
        />
        <OverviewMetric
          icon={BarChart3}
          label="Monthly P&L"
          value={money(monthlyPnl.monthly_pnl_usd)}
          detail={`${signedPct(monthlyPnl.monthly_pnl_pct)} | vs benchmark ${signedPct(monthlyPnl.vs_benchmark_pct)}`}
          tone={Number(monthlyPnl.monthly_pnl_usd || 0) >= 0 ? 'good' : 'bad'}
        />
        <OverviewMetric
          icon={Activity}
          label="Sharpe (30d)"
          value={Number(sharpe.rolling_30d || 0).toFixed(2)}
          detail={`90d ${Number(sharpe.rolling_90d || 0).toFixed(2)} | target ${Number(sharpe.target || 1).toFixed(2)}`}
          tone={statusTone(sharpe.status)}
        />
        <OverviewMetric
          icon={Shield}
          label="Max Drawdown"
          value={pct(drawdown.current_drawdown_pct)}
          detail={`limit ${pct(drawdown.limit_pct)} | margin ${signedPct(drawdown.margin_to_limit_pct)}`}
          tone={drawdown.halted ? 'bad' : 'good'}
        />
      </div>

      <div className="overview-summary-grid">
        <article className="overview-summary-card">
          <h3>Runtime Status</h3>
          <p className={`overview-summary-state ${statusTone(runtime.runtime_status)}`}>{String(runtime.runtime_status || 'unknown').toUpperCase()}</p>
          <div className="overview-summary-list">
            <span>Orchestrator: {runtime?.orchestrator?.status || 'n/a'}</span>
            <span>Data pipeline: {runtime?.data_pipeline?.status || 'n/a'}</span>
            <span>Agents active: {runtime.agents_active || 0}/{runtime.agents_total || 0}</span>
            <span>Pending tasks: {runtime.pending_tasks || 0}</span>
          </div>
        </article>

        <article className="overview-summary-card">
          <h3>Portfolio Exposure</h3>
          <p className="overview-summary-state good">{pct(exposure.deployed_pct)} DEPLOYED</p>
          <div className="overview-summary-list">
            <span>Equities: {money(exposure.equities_usd)}</span>
            <span>Cash: {money(exposure.cash_usd)} ({pct(exposure.cash_pct)})</span>
            <span>Shorts: {money(exposure.shorts_usd)}</span>
            <span>Gross leverage: {Number(exposure.gross_leverage || 0).toFixed(2)}x</span>
          </div>
        </article>

        <article className="overview-summary-card">
          <h3>Risk Status</h3>
          <p className={`overview-summary-state ${statusTone(risk.status)}`}>
            {String(risk.status || 'unknown').replace(/_/g, ' ').toUpperCase()}
          </p>
          <div className="overview-summary-list">
            <span>VaR (95%, 1d): {money(risk.var_95_1d_usd)} ({pct(risk.var_95_1d_pct)})</span>
            <span>Drawdown: {pct(risk.max_drawdown_pct)} / {pct(risk.max_drawdown_limit_pct)}</span>
            <span>Largest concentration: {pct(risk.sector_concentration_pct)}</span>
            <span>Concentration limit: {pct(risk.sector_concentration_limit_pct)}</span>
          </div>
        </article>
      </div>

      <div className="overview-alerts-card">
        <div className="overview-alerts-head">
          <h3>Active Alerts</h3>
          <span>{alerts.length} items</span>
        </div>
        {alerts.length ? (
          <ul className="overview-alert-list">
            {alerts.slice(0, 4).map((alert, index) => (
              <li key={`${alert.type || 'alert'}-${index}`}>
                <AlertTriangle size={14} />
                <span>{alert.message || 'Alert raised.'}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="overview-empty">No pending alerts right now.</div>
        )}
      </div>

      <div className="overview-action-row">
        <button type="button" className="ops-button secondary small" onClick={() => onNavigate?.('performance')}>View Full P&L</button>
        <button type="button" className="ops-button secondary small" onClick={() => onNavigate?.('positions')}>View Holdings</button>
        <button type="button" className="ops-button secondary small" onClick={() => onNavigate?.('decisions')}>Approve Pending</button>
        <button type="button" className="ops-button small" onClick={() => onNavigate?.('runtime')}>Control Center</button>
      </div>
    </section>
  );
}
