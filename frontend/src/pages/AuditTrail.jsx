import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import '../styles/audit.css';

const AuditTrail = () => {
  const { decisionId } = useParams();
  const navigate = useNavigate();
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data - replace with actual API call
    setTimeout(() => {
      setAuditData({
        id: decisionId,
        title: 'Trading Decision Audit Trail',
        timestamp: new Date().toISOString(),
        status: 'approved',
        events: [
          {
            timestamp: new Date(Date.now() - 3600000).toISOString(),
            actor: 'Research Director',
            action: 'created_decision',
            details: 'Initial trading decision created based on market analysis'
          },
          {
            timestamp: new Date(Date.now() - 1800000).toISOString(),
            actor: 'Risk Auditor',
            action: 'reviewed',
            details: 'Risk assessment passed - within acceptable parameters'
          },
          {
            timestamp: new Date(Date.now() - 900000).toISOString(),
            actor: 'Compliance Officer',
            action: 'approved',
            details: 'Compliance gates passed - decision approved for execution'
          },
          {
            timestamp: new Date(Date.now() - 300000).toISOString(),
            actor: 'Trading System',
            action: 'executed',
            details: 'Trade executed successfully'
          }
        ],
        metadata: {
          decisionType: 'BUY_SIGNAL',
          assets: ['AAPL', 'MSFT', 'GOOGL'],
          expectedReturn: '3.2%',
          riskScore: 2.1,
          confidence: 0.87
        }
      });
      setLoading(false);
    }, 800);
  }, [decisionId]);

  if (loading) {
    return (
      <div className="audit-container">
        <div className="audit-loading">Loading audit trail...</div>
      </div>
    );
  }

  return (
    <div className="audit-container">
      <button className="audit-back-btn" onClick={() => navigate(-1)}>
        <ArrowLeft size={20} />
        Back
      </button>

      <div className="audit-header">
        <h1>{auditData.title}</h1>
        <span className={`audit-status ${auditData.status}`}>
          {auditData.status.toUpperCase()}
        </span>
      </div>

      <div className="audit-metadata">
        <div className="metadata-item">
          <span className="label">Decision ID</span>
          <span className="value">{auditData.id}</span>
        </div>
        <div className="metadata-item">
          <span className="label">Decision Type</span>
          <span className="value">{auditData.metadata.decisionType}</span>
        </div>
        <div className="metadata-item">
          <span className="label">Confidence</span>
          <span className="value">{(auditData.metadata.confidence * 100).toFixed(1)}%</span>
        </div>
        <div className="metadata-item">
          <span className="label">Risk Score</span>
          <span className="value">{auditData.metadata.riskScore}</span>
        </div>
      </div>

      <div className="audit-timeline">
        <h2>Decision Timeline</h2>
        <div className="timeline-events">
          {auditData.events.map((event, idx) => (
            <div key={idx} className="timeline-event">
              <div className="event-marker">
                {event.action === 'approved' ? (
                  <CheckCircle size={24} className="event-icon success" />
                ) : event.action === 'rejected' ? (
                  <AlertCircle size={24} className="event-icon error" />
                ) : (
                  <Clock size={24} className="event-icon info" />
                )}
              </div>
              <div className="event-content">
                <div className="event-header">
                  <span className="event-actor">{event.actor}</span>
                  <span className="event-action">{event.action.replace(/_/g, ' ').toUpperCase()}</span>
                </div>
                <p className="event-details">{event.details}</p>
                <span className="event-time">
                  {new Date(event.timestamp).toLocaleString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {auditData.metadata.assets && (
        <div className="audit-section">
          <h2>Assets Involved</h2>
          <div className="assets-list">
            {auditData.metadata.assets.map((asset, idx) => (
              <span key={idx} className="asset-badge">{asset}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditTrail;
