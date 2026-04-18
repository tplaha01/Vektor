import React from 'react';
import { TrendingUp, TrendingDown, AlertCircle, Check } from 'lucide-react';
import SparkChart from '../common/SparkChart';

const KPIGrid = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="kpi-grid">
        {Array(6).fill(0).map((_, i) => (
          <div key={i} className="kpi-card skeleton-card">
            <div className="skeleton-line skeleton-line-label"></div>
            <div className="skeleton-line skeleton-line-value"></div>
          </div>
        ))}
      </div>
    );
  }

  const kpiCards = [
    {
      label: 'Total Equity',
      value: `$${(metrics.total_equity || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`,
      change: metrics.equity_change || 0,
      color: 'var(--blue)',
      icon: null,
      sparkData: [980, 990, 1000, 995, 1010, 1020],
    },
    {
      label: 'Realized P&L',
      value: `$${(metrics.realized_pnl || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`,
      change: metrics.pnl_change || 0,
      color: metrics.realized_pnl >= 0 ? 'var(--green)' : 'var(--red)',
      icon: metrics.realized_pnl >= 0 ? TrendingUp : TrendingDown,
      sparkData: metrics.realized_pnl >= 0 ? [100, 150, 200, 250, 300] : [300, 250, 200, 150, 100],
    },
    {
      label: 'Current Drawdown',
      value: `${(metrics.current_drawdown || 0).toFixed(2)}%`,
      change: -(metrics.current_drawdown || 0),
      color: metrics.current_drawdown > 5 ? 'var(--amber)' : 'var(--teal)',
      icon: metrics.current_drawdown > 5 ? AlertCircle : Check,
      alert: metrics.current_drawdown > 10,
      sparkData: [3.2, 4.1, 5.3, 4.8, 3.5],
    },
    {
      label: 'Win Rate',
      value: `${(metrics.win_rate || 0).toFixed(1)}%`,
      change: metrics.win_rate_change || 0,
      color: 'var(--purple)',
      icon: null,
      sparkData: [55, 58, 60, 62, 65],
    },
    {
      label: 'Active Positions',
      value: (metrics.active_positions || 0).toString(),
      change: 0,
      color: 'var(--blue)',
      icon: null,
      sparkData: [4, 5, 6, 5, 5],
    },
    {
      label: 'Sharpe Ratio',
      value: (metrics.sharpe_ratio || 0).toFixed(2),
      change: metrics.sharpe_change || 0,
      color: metrics.sharpe_ratio > 1 ? 'var(--green)' : 'var(--amber)',
      icon: null,
      sparkData: [0.8, 1.1, 1.3, 1.2, 1.4],
    },
  ];

  return (
    <div className="kpi-grid">
      {kpiCards.map((card, idx) => {
        const Icon = card.icon;
        const isPositive = card.change >= 0;

        return (
          <div
            key={idx}
            className={`kpi-card ${card.alert ? 'alert' : ''}`}
            style={{ borderLeftColor: card.color }}
            role="region"
            aria-label={`${card.label}: ${card.value}`}
          >
            <div className="kpi-header">
              <span className="kpi-label">{card.label}</span>
              {Icon && <Icon size={16} style={{ color: card.color }} />}
            </div>

            <div className="kpi-value" style={{ color: card.color }}>
              {card.value}
            </div>

            <SparkChart 
              values={card.sparkData}
              color={card.color}
              height={24}
            />

            {card.change !== 0 && (
              <div className="kpi-change" style={{ color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                <span className="change-value">
                  {isPositive ? '+' : ''}{card.change.toFixed(2)}%
                </span>
                <span className="change-icon">
                  {isPositive ? '↑' : '↓'}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default KPIGrid;
