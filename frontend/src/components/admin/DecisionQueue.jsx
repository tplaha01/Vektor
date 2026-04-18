import React, { useState, useEffect } from 'react';
import { Check, X, AlertCircle, TrendingUp, TrendingDown, Clock } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const DecisionQueue = ({ expanded = false }) => {
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const payload = await adminAPI.getFundPendingDecisions();
        const parsed = adminAPI.normalizeArray(payload, 'decisions');
        setDecisions(parsed);
      } catch (err) {
        console.error('Failed to fetch decisions:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchDecisions();
    const interval = setInterval(fetchDecisions, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (decisionId) => {
    try {
      await adminAPI.approveFundDecision(decisionId);
      setDecisions((prev) => prev.filter((d) => d.decision_id !== decisionId));
    } catch (err) {
      console.error('Failed to approve decision:', err);
    }
  };

  const handleReject = async (decisionId) => {
    try {
      await adminAPI.rejectFundDecision(decisionId);
      setDecisions((prev) => prev.filter((d) => d.decision_id !== decisionId));
    } catch (err) {
      console.error('Failed to reject decision:', err);
    }
  };

  if (loading) {
    return <div className="panel-loading">Loading decisions...</div>;
  }

  if (decisions.length === 0) {
    return (
      <div className="empty-state">
        <Clock size={32} />
        <p>No pending decisions</p>
      </div>
    );
  }

  return (
    <div className={`decision-queue ${expanded ? 'expanded' : 'compact'}`}>
      <div className="decision-list">
        {decisions.map((decision) => (
          <div key={decision.decision_id} className="decision-card">
            <div className="decision-header">
              <div className="decision-title">
                <span className="symbol">{decision.symbol || 'N/A'}</span>
                <span className={`side ${decision.side || 'buy'}`}>
                  {(decision.side || '').toLowerCase() === 'buy' ? (
                    <TrendingUp size={16} />
                  ) : (
                    <TrendingDown size={16} />
                  )}
                  {(decision.side || 'unknown').toUpperCase()}
                </span>
              </div>
              <div className="decision-confidence">
                <span
                  className="confidence-badge"
                  style={{
                    background:
                      (decision.confidence || 0) > 0.7
                        ? 'rgba(62, 207, 142, 0.1)'
                        : (decision.confidence || 0) > 0.4
                          ? 'rgba(245, 166, 35, 0.1)'
                          : 'rgba(224, 82, 82, 0.1)',
                    color:
                      (decision.confidence || 0) > 0.7
                        ? 'var(--green)'
                        : (decision.confidence || 0) > 0.4
                          ? 'var(--amber)'
                          : 'var(--red)',
                  }}
                >
                  {(((decision.confidence || 0) * 100).toFixed(0))}% confidence
                </span>
              </div>
            </div>

            <div className="decision-body">
              <div className="decision-details">
                <div className="detail-row">
                  <span className="detail-label">Quantity:</span>
                  <strong>{decision.quantity || decision.qty || 0} shares</strong>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Sleeve:</span>
                  <strong>{decision.sleeve || 'tactical'}</strong>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Agent:</span>
                  <strong>{(decision.agent_id || 'system').slice(0, 8)}</strong>
                </div>
              </div>

              <div className="decision-thesis">
                <p className="thesis-label">Thesis:</p>
                <p className="thesis-text">{decision.thesis || 'No thesis provided.'}</p>
              </div>

              <div className="decision-timeline">
                <span className="time">
                  Created:{' '}
                  {decision.created_at
                    ? new Date(decision.created_at).toLocaleTimeString()
                    : 'n/a'}
                </span>
                <span className="expires">
                  Expires:{' '}
                  {decision.expires_at
                    ? new Date(decision.expires_at).toLocaleTimeString()
                    : 'n/a'}
                </span>
              </div>
            </div>

            <div className="decision-actions">
              <button
                className="btn-approve"
                onClick={() => handleApprove(decision.decision_id)}
                title="Approve and execute"
              >
                <Check size={16} />
                Approve
              </button>
              <button
                className="btn-reject"
                onClick={() => handleReject(decision.decision_id)}
                title="Reject decision"
              >
                <X size={16} />
                Reject
              </button>
              <a href={`/audit/${decision.decision_id}`} className="btn-audit">
                <AlertCircle size={16} />
                Audit Trail
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DecisionQueue;
