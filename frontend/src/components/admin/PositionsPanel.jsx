import React, { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, DollarSign, X } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const PositionsPanel = () => {
  const [positions, setPositions] = useState([]);
  const [prices, setPrices] = useState({});
  const [loading, setLoading] = useState(true);

  const fetchPositions = useCallback(async () => {
    try {
      const [positionsPayload, pricesPayload] = await Promise.all([
        adminAPI.getPaperPositions(),
        adminAPI.getMarketPrices(),
      ]);
      setPositions(adminAPI.normalizeArray(positionsPayload, 'positions'));
      setPrices(pricesPayload || {});
    } catch (err) {
      console.error('Failed to fetch positions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, [fetchPositions]);

  const handleClosePosition = async (symbol, qty) => {
    try {
      const quantity = Math.abs(Number(qty || 0));
      if (quantity <= 0) return;
      await adminAPI.placePaperOrder({ symbol, side: qty >= 0 ? 'sell' : 'buy', quantity });
      await fetchPositions();
    } catch (err) {
      console.error('Failed to close position:', err);
    }
  };

  if (loading) {
    return <div className="panel-loading">Loading positions...</div>;
  }

  if (positions.length === 0) {
    return (
      <div className="empty-state">
        <DollarSign size={32} />
        <p>No open positions</p>
      </div>
    );
  }

  const totalMarketValue = positions.reduce((sum, p) => sum + Number(p.market_value || 0), 0);
  const totalUnrealized = positions.reduce((sum, p) => sum + Number(p.unrealized_pnl || 0), 0);

  return (
    <div className="positions-panel">
      <div className="positions-table-container">
        <table className="positions-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Quantity</th>
              <th>Avg Cost</th>
              <th>Current Price</th>
              <th>Market Value</th>
              <th>Unrealized P&L</th>
              <th>Return %</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => {
              const quantity = Number(position.qty || position.quantity || 0);
              const avgPrice = Number(position.avg_price || position.cost_basis || 0);
              const currentPrice = Number(prices[position.symbol] || position.market_price || avgPrice);
              const marketValue = Number(position.market_value || quantity * currentPrice);
              const unrealizedPnL = Number(position.unrealized_pnl || marketValue - quantity * avgPrice);
              const costValue = quantity * avgPrice;
              const returnPercent = costValue !== 0 ? (unrealizedPnL / Math.abs(costValue)) * 100 : 0;
              const isGain = unrealizedPnL >= 0;

              return (
                <tr key={position.symbol} className={`position-row ${isGain ? 'gain' : 'loss'}`}>
                  <td className="symbol-cell">
                    <strong>{position.symbol}</strong>
                  </td>
                  <td className="qty-cell">{quantity.toLocaleString()}</td>
                  <td className="price-cell">${avgPrice.toFixed(2)}</td>
                  <td className="price-cell">${currentPrice.toFixed(2)}</td>
                  <td className="value-cell">
                    ${marketValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </td>
                  <td className={`pnl-cell ${isGain ? 'positive' : 'negative'}`}>
                    <span className="pnl-icon">
                      {isGain ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    </span>
                    ${unrealizedPnL.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </td>
                  <td className={`return-cell ${isGain ? 'positive' : 'negative'}`}>
                    {isGain ? '+' : ''}
                    {returnPercent.toFixed(2)}%
                  </td>
                  <td className="actions-cell">
                    <button
                      className="btn-close-position"
                      onClick={() => handleClosePosition(position.symbol, quantity)}
                      title="Close position"
                    >
                      <X size={16} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="positions-summary">
        <div className="summary-stat">
          <span className="stat-label">Total Market Value</span>
          <strong className="stat-value">
            ${totalMarketValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </strong>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Total Unrealized P&L</span>
          <strong
            className="stat-value"
            style={{ color: totalUnrealized >= 0 ? 'var(--green)' : 'var(--red)' }}
          >
            ${totalUnrealized.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </strong>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Active Positions</span>
          <strong className="stat-value">{positions.length}</strong>
        </div>
      </div>
    </div>
  );
};

export default PositionsPanel;
