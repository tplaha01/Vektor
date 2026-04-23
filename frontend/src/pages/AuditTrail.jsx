import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import '../styles/audit.css';
import { adminAPI } from '../api/adminAPI';
import WorkspaceNav from '../components/common/WorkspaceNav';

const AuditTrail = () => {
  const { decisionId } = useParams();
  const navigate = useNavigate();
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        setError('');
        const payload = await adminAPI.getLineageRunDetail(decisionId, 300);
        const timeline = Array.isArray(payload?.audit_timeline) ? payload.audit_timeline : [];
        const taskEvents = Array.isArray(payload?.task_events) ? payload.task_events : [];

        const events = [...timeline, ...taskEvents]
          .map((event, idx) => ({
            id: event.event_id || event.task_id || `evt-${idx}`,
            timestamp: event.timestamp || event.ts || event.created_at || new Date().toISOString(),
            actor: event.agent_id || event.actor || event.role || 'system',
            action: event.event_type || event.status || event.task_type || 'event',
            details:
              event.details?.reason ||
              event.payload?.reason ||
              event.reason ||
              JSON.stringify(event.details || event.payload || event).slice(0, 200),
          }))
          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

        if (!mounted) return;
        setAuditData({
          id: decisionId,
          title: 'Decision / Run Audit Trail',
          status: payload?.decision?.status || 'unknown',
          metadata: {
            decisionType: payload?.decision?.status || 'unknown',
            confidence: Number(payload?.decision?.confidence || 0),
            riskScore: Number(payload?.decision?.risk_score || 0),
            assets: payload?.decision?.symbol ? [payload.decision.symbol] : [],
          },
          events,
        });
      } catch (e) {
        if (!mounted) return;
        setError(String(e?.message || e));
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => {
      mounted = false;
    };
  }, [decisionId]);

  if (loading) {
    return (
      <div className="audit-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Audit"
          title="Decision Audit Trail"
          summary="Run-level events, approvals, and execution traces for a single decision context."
        />
        <div className="audit-loading">Loading audit trail...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="audit-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Audit"
          title="Decision Audit Trail"
          summary="Run-level events, approvals, and execution traces for a single decision context."
        />
        <button className="audit-back-btn" onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
          Back
        </button>
        <div className="audit-loading">Unable to load audit trail: {error}</div>
      </div>
    );
  }

  if (!auditData) {
    return (
      <div className="audit-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Audit"
          title="Decision Audit Trail"
          summary="Run-level events, approvals, and execution traces for a single decision context."
        />
        <button className="audit-back-btn" onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
          Back
        </button>
        <div className="audit-loading">No audit record for this run yet.</div>
      </div>
    );
  }

  return (
    <div className="audit-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Audit"
          title="Decision Audit Trail"
          summary="Run-level events, approvals, and execution traces for a single decision context."
        />
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
                {String(event.action).toLowerCase().includes('approved') || String(event.action).toLowerCase().includes('executed') ? (
                  <CheckCircle size={24} className="event-icon success" />
                ) : String(event.action).toLowerCase().includes('reject') || String(event.action).toLowerCase().includes('blocked') || String(event.action).toLowerCase().includes('failed') ? (
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
