import React, { useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const currency = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });

const percent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

const ratio = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}x`;

const tone = (value, limit, invert = false) => {
  const current = Number(value || 0);
  const boundary = Number(limit || 0);
  if (invert) {
    return current >= boundary ? 'ops-positive' : current >= boundary * 0.8 ? '' : 'ops-negative';
  }
  return current > boundary ? 'ops-negative' : current > boundary * 0.8 ? '' : 'ops-positive';
};

export default function RiskPolicyPanel() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [varData, setVarData] = useState(null);
  const [cvarData, setCvarData] = useState(null);
  const [drawdownData, setDrawdownData] = useState(null);
  const [leverageData, setLeverageData] = useState(null);
  const [sharpeData, setSharpeData] = useState(null);
  const [sectorLimits, setSectorLimits] = useState([]);
  const [positionLimits, setPositionLimits] = useState(null);
  const [approvalThresholds, setApprovalThresholds] = useState(null);
  const [breachHistory, setBreachHistory] = useState([]);
  const [form, setForm] = useState({
    maxOrderNotionalUsd: '',
    minCashReservePct: '',
    maxAssetClassExposurePct: '',
  });

  const loadPanel = async () => {
    setLoading(true);
    try {
      const [
        varPayload,
        cvarPayload,
        drawdownPayload,
        leveragePayload,
        sharpePayload,
        sectorPayload,
        positionPayload,
        thresholdPayload,
        breachPayload,
      ] = await Promise.all([
        adminAPI.getAdminRiskVar(),
        adminAPI.getAdminRiskCvar(),
        adminAPI.getAdminRiskDrawdown(),
        adminAPI.getAdminRiskLeverage(),
        adminAPI.getAdminRiskSharpe(),
        adminAPI.getAdminPolicySectorLimits(),
        adminAPI.getAdminPolicyPositionLimits(),
        adminAPI.getAdminPolicyApprovalThresholds(),
        adminAPI.getAdminRiskBreachHistory(10),
      ]);
      setVarData(varPayload || null);
      setCvarData(cvarPayload || null);
      setDrawdownData(drawdownPayload || null);
      setLeverageData(leveragePayload || null);
      setSharpeData(sharpePayload || null);
      setSectorLimits(adminAPI.normalizeArray(sectorPayload, 'rows'));
      setPositionLimits(positionPayload || null);
      setApprovalThresholds(thresholdPayload || null);
      setBreachHistory(adminAPI.normalizeArray(breachPayload, 'items'));
      setForm({
        maxOrderNotionalUsd: Number(thresholdPayload?.max_order_notional_usd || 0),
        minCashReservePct: Number(thresholdPayload?.min_cash_reserve_pct || 0) * 100,
        maxAssetClassExposurePct: Number(thresholdPayload?.max_asset_class_exposure_pct || 0) * 100,
      });
    } catch (err) {
      console.error('Failed to load risk policy panel:', err);
      setSectorLimits([]);
      setBreachHistory([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPanel();
  }, []);

  const saveThresholds = async () => {
    setSaving(true);
    try {
      const payload = await adminAPI.updateAdminPolicyApprovalThresholds({
        maxOrderNotionalUsd: Number(form.maxOrderNotionalUsd || 0),
        minCashReservePct: Number(form.minCashReservePct || 0) / 100,
        maxAssetClassExposurePct: Number(form.maxAssetClassExposurePct || 0) / 100,
        reason: 'risk_policy_panel_save',
      });
      setApprovalThresholds(payload || null);
    } catch (err) {
      console.error('Failed to update policy thresholds:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="ops-empty">Loading risk policy surface...</div>;
  }

  return (
    <>
      <div className="ops-metric-grid ops-metric-grid-control">
        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">VaR (1d, 95%)</span>
              <strong className="ops-metric-value">{currency(varData?.current_var_usd)}</strong>
            </div>
          </div>
          <p className={`ops-metric-detail ${tone(varData?.current_var_pct, varData?.max_allowed_pct)}`}>
            {percent(varData?.current_var_pct)} vs limit {percent(varData?.max_allowed_pct)}
          </p>
        </article>

        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">CVaR</span>
              <strong className="ops-metric-value">{currency(cvarData?.current_cvar_usd)}</strong>
            </div>
          </div>
          <p className={`ops-metric-detail ${tone(cvarData?.current_cvar_pct, cvarData?.max_allowed_pct)}`}>
            {percent(cvarData?.current_cvar_pct)} worst-tail average
          </p>
        </article>

        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Drawdown</span>
              <strong className="ops-metric-value">{percent(drawdownData?.current_drawdown_pct)}</strong>
            </div>
          </div>
          <p className={`ops-metric-detail ${tone(drawdownData?.current_drawdown_pct, drawdownData?.max_allowed_pct)}`}>
            Limit {percent(drawdownData?.max_allowed_pct)}
          </p>
        </article>

        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Gross Leverage</span>
              <strong className="ops-metric-value">{ratio(leverageData?.current_gross_leverage)}</strong>
            </div>
          </div>
          <p className={`ops-metric-detail ${tone(leverageData?.current_gross_leverage, leverageData?.max_allowed_leverage)}`}>
            Limit {ratio(leverageData?.max_allowed_leverage)}
          </p>
        </article>

        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Sharpe (30d)</span>
              <strong className="ops-metric-value">{Number(sharpeData?.rolling_30d || 0).toFixed(2)}</strong>
            </div>
          </div>
          <p className={`ops-metric-detail ${tone(sharpeData?.rolling_30d, sharpeData?.target, true)}`}>
            Return {percent(sharpeData?.return_30d_pct)} | Vol {percent(sharpeData?.volatility_30d_pct)}
          </p>
        </article>
      </div>

      <div className="ops-grid ops-grid-overview">
        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Risk Dashboard</p>
              <h2 className="ops-panel-title">Portfolio risk posture</h2>
              <p className="ops-panel-description">Daily downside, high-water-mark pressure, and leverage headroom.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            <div className="ops-kv-grid">
              <div className="ops-kv"><span className="ops-kv-label">Historical avg VaR</span><strong className="ops-kv-value">{currency(varData?.historical_avg_var_usd)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Margin to VaR limit</span><strong className="ops-kv-value">{currency(varData?.margin_usd)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">High water mark</span><strong className="ops-kv-value">{currency(drawdownData?.high_water_mark_usd)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Current NAV</span><strong className="ops-kv-value">{currency(drawdownData?.current_nav_usd)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Long gross</span><strong className="ops-kv-value">{ratio(leverageData?.long_gross)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Short gross</span><strong className="ops-kv-value">{ratio(leverageData?.short_gross)}</strong></div>
            </div>
            <p className="ops-note">{cvarData?.interpretation || 'No tail-risk interpretation available.'}</p>
          </div>
        </section>

        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Policy Enforcement</p>
              <h2 className="ops-panel-title">Sector and position limits</h2>
              <p className="ops-panel-description">Concentration checks plus current single-name size pressure.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            {sectorLimits.length ? (
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Sector</th>
                      <th>Allocation</th>
                      <th>Max</th>
                      <th>Margin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectorLimits.map((row) => (
                      <tr key={row.sector}>
                        <td>{row.sector}</td>
                        <td className={tone(row.allocation_pct, row.max_pct)}>{percent(row.allocation_pct)}</td>
                        <td>{percent(row.max_pct)}</td>
                        <td>{percent(row.margin_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="ops-empty">No sector concentration data is available.</div>
            )}

            <div className="ops-kv-grid">
              <div className="ops-kv"><span className="ops-kv-label">Max single position</span><strong className="ops-kv-value">{percent(positionLimits?.max_single_position_pct)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Current max</span><strong className="ops-kv-value">{percent(positionLimits?.current_max_position_pct)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Min trade notional</span><strong className="ops-kv-value">{currency(positionLimits?.min_trade_notional_usd)}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Current min position</span><strong className="ops-kv-value">{currency(positionLimits?.current_min_position_usd)}</strong></div>
            </div>
          </div>
        </section>
      </div>

      <div className="ops-grid ops-grid-overview">
        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Approval Rules</p>
              <h2 className="ops-panel-title">Threshold controls</h2>
              <p className="ops-panel-description">Manual approval floor plus reserve and exposure guardrails.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Approval threshold ($)</span>
                <input
                  className="ops-input"
                  type="number"
                  value={form.maxOrderNotionalUsd}
                  onChange={(event) => setForm((prev) => ({ ...prev, maxOrderNotionalUsd: event.target.value }))}
                />
              </label>
              <label className="ops-field">
                <span>Min cash reserve (%)</span>
                <input
                  className="ops-input"
                  type="number"
                  step="0.1"
                  value={form.minCashReservePct}
                  onChange={(event) => setForm((prev) => ({ ...prev, minCashReservePct: event.target.value }))}
                />
              </label>
              <label className="ops-field">
                <span>Max asset exposure (%)</span>
                <input
                  className="ops-input"
                  type="number"
                  step="0.1"
                  value={form.maxAssetClassExposurePct}
                  onChange={(event) => setForm((prev) => ({ ...prev, maxAssetClassExposurePct: event.target.value }))}
                />
              </label>
            </div>
            <div className="ops-button-row">
              <button type="button" className="ops-button" disabled={saving} onClick={saveThresholds}>
                Save Thresholds
              </button>
            </div>
            <div className="ops-inline-chips">
              {(approvalThresholds?.approval_logic || []).map((item) => (
                <span key={item} className="ops-chip">{item}</span>
              ))}
            </div>
          </div>
        </section>

        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Breach Log</p>
              <h2 className="ops-panel-title">Recent policy blocks</h2>
              <p className="ops-panel-description">Latest blocked trades and concentration breaches recorded by the backend.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            {breachHistory.length ? (
              <div className="ops-task-list">
                {breachHistory.map((item, index) => (
                  <article key={`${item.timestamp || 'breach'}-${index}`} className="ops-task-row">
                    <div className="ops-task-head">
                      <strong>{item.symbol || 'Portfolio policy'}</strong>
                      <span>{item.status || 'blocked'}</span>
                    </div>
                    <div className="ops-task-meta">
                      <span>{String(item.timestamp || '').slice(0, 16).replace('T', ' ') || 'n/a'}</span>
                      <span>{item.reason || 'No reason provided.'}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="ops-empty">
                <AlertCircle size={16} /> No recent risk breaches are published by the backend.
              </div>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

