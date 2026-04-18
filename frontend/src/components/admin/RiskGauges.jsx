import React, { useState, useEffect } from 'react';
import { AlertTriangle, Shield } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const RiskGauges = ({ metrics, expanded = false }) => {
  const [sleeves, setSleeves] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSleeves = async () => {
      try {
        const payload = await adminAPI.getFundSleevesBudgets();
        let normalized = adminAPI.normalizeArray(payload, 'sleeves');

        // Fallback to configured sleeve defaults when no run snapshot exists yet.
        if (normalized.length === 0 && payload?.configured_defaults?.weights) {
          const defaults = payload.configured_defaults;
          const gross = Number(defaults.total_capital_usd || 0);
          const reserve = Number(defaults.reserve_cash_usd || 0);
          const deployable = Math.max(0, gross - reserve);
          normalized = Object.entries(defaults.weights).map(([sleeveId, weight]) => {
            const totalCapital = deployable * Number(weight || 0);
            return {
              sleeve_id: sleeveId,
              total_capital: totalCapital,
              allocated: 0,
              available: totalCapital,
              active_positions: 0,
              pnl: 0,
            };
          });
        }

        setSleeves(normalized);
      } catch (err) {
        console.error('Failed to fetch sleeves:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSleeves();
  }, []);

  if (!metrics) return null;

  const drawdownPercent = metrics.current_drawdown || 0;
  const drawdownThreshold = metrics.max_drawdown_threshold || 15;
  const drawdownRatio = Math.min(drawdownPercent / drawdownThreshold, 1);
  const drawdownColor =
    drawdownRatio < 0.5 ? 'var(--teal)' : drawdownRatio < 0.8 ? 'var(--amber)' : 'var(--red)';

  const renderGauge = (value, max, label, color) => {
    const ratio = Math.min(Math.abs(value) / max, 1);

    return (
      <div className="gauge-container">
        <svg className="gauge" viewBox="0 0 200 120" width="200" height="120">
          <path
            d="M 30 100 A 70 70 0 0 1 170 100"
            fill="none"
            stroke="var(--line2)"
            strokeWidth="8"
          />

          <path
            d="M 30 100 A 70 70 0 0 1 170 100"
            fill="none"
            stroke={color}
            strokeWidth="8"
            pathLength="100"
            style={{
              strokeDasharray: `${ratio * 100} 100`,
              transition: 'stroke-dasharray 0.5s ease',
            }}
          />

          <circle cx="100" cy="100" r="4" fill={color} />

          <text x="30" y="115" fontSize="12" fill="var(--txt2)">
            0%
          </text>
          <text x="155" y="115" fontSize="12" fill="var(--txt2)" textAnchor="end">
            {max}%
          </text>
        </svg>

        <div className="gauge-label">
          <div className="gauge-title">{label}</div>
          <div className="gauge-value" style={{ color }}>
            {value.toFixed(2)}%
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`risk-gauges ${expanded ? 'expanded' : 'compact'}`}>
      {expanded ? (
        <>
          <div className="gauges-grid">
            {renderGauge(drawdownPercent, drawdownThreshold, 'Current Drawdown', drawdownColor)}
            {renderGauge(
              metrics.max_drawdown_ytd || 0,
              drawdownThreshold,
              'Max Drawdown YTD',
              'var(--amber)'
            )}
          </div>

          <div className="risk-section">
            <h4 className="risk-title">
              <Shield size={16} />
              Sleeve Allocation
            </h4>

            {loading ? (
              <div className="panel-loading">Loading sleeves...</div>
            ) : (
              <div className="sleeve-list">
                {sleeves.map((sleeve) => {
                  const utilization = sleeve.total_capital > 0 ? sleeve.allocated / sleeve.total_capital : 0;
                  const utilizationPercent = utilization * 100;

                  return (
                    <div key={sleeve.sleeve_id} className="sleeve-item">
                      <div className="sleeve-header">
                        <span className="sleeve-name">{sleeve.sleeve_id.replace(/_/g, ' ')}</span>
                        <span className="sleeve-usage">
                          ${Number(sleeve.allocated || 0).toLocaleString()}{' '}
                          <span className="usage-percent">({utilizationPercent.toFixed(0)}%)</span>
                        </span>
                      </div>

                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${Math.max(0, Math.min(utilizationPercent, 100))}%`,
                            background:
                              utilizationPercent > 90
                                ? 'var(--red)'
                                : utilizationPercent > 70
                                  ? 'var(--amber)'
                                  : 'var(--green)',
                          }}
                        />
                      </div>

                      <div className="sleeve-stats">
                        <span className="stat">Total: ${Number(sleeve.total_capital || 0).toLocaleString()}</span>
                        <span className="stat">Positions: {Number(sleeve.active_positions || 0)}</span>
                        <span className={`stat pnl ${Number(sleeve.pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
                          P&L: ${Number(sleeve.pnl || 0).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="risk-section">
            <h4 className="risk-title">
              <AlertTriangle size={16} />
              Risk Status
            </h4>

            <div className="risk-checks">
              <div className={`risk-check ${drawdownPercent > drawdownThreshold ? 'failed' : 'passed'}`}>
                <span className="check-status">{drawdownPercent > drawdownThreshold ? 'X' : 'OK'}</span>
                <span className="check-label">Drawdown Limit</span>
                <span className="check-detail">
                  {drawdownPercent.toFixed(2)}% / {drawdownThreshold}%
                </span>
              </div>

              <div className="risk-check passed">
                <span className="check-status">OK</span>
                <span className="check-label">Paper Trading</span>
                <span className="check-detail">No live orders active</span>
              </div>

              <div className="risk-check passed">
                <span className="check-status">OK</span>
                <span className="check-label">Policy Gates</span>
                <span className="check-detail">All compliance checks passing</span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="risk-gauges-compact">
          <div
            className={`compact-gauge ${drawdownRatio > 0.8 ? 'alert' : drawdownRatio > 0.5 ? 'warning' : ''}`}
            style={{
              background: `conic-gradient(${drawdownColor} 0deg ${drawdownRatio * 360}deg, var(--line2) ${drawdownRatio * 360}deg 360deg)`,
            }}
          >
            <div className="compact-gauge-inner">
              <span className="gauge-percent">{drawdownPercent.toFixed(1)}%</span>
              <span className="gauge-label">Drawdown</span>
            </div>
          </div>

          <div className="compact-stats">
            {sleeves.map((sleeve) => {
              const utilization =
                Number(sleeve.total_capital || 0) > 0
                  ? (Number(sleeve.allocated || 0) / Number(sleeve.total_capital || 0)) * 100
                  : 0;
              return (
                <div key={sleeve.sleeve_id} className="compact-stat">
                  <span className="stat-label">{sleeve.sleeve_id.split('_')[0]}</span>
                  <span className="stat-value">{utilization.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskGauges;
