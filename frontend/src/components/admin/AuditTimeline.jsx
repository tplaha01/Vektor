import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, FileText, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const AuditTimeline = ({ expanded = false, orderId = null }) => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedEvent, setExpandedEvent] = useState(null);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const payload = orderId
          ? await adminAPI.getFundOrderAuditTimeline(orderId)
          : await adminAPI.getFundKnowledgeEvents(50, 'development');

        const rawEvents = adminAPI.normalizeArray(payload, 'events');
        const normalized = rawEvents
          .map((event, idx) => ({
            event_id: event.event_id || event.id || `event-${idx}`,
            timestamp: event.timestamp || event.occurred_at || new Date().toISOString(),
            event_type: event.event_type || event.status || 'event',
            details: event.details || event.payload || {},
          }))
          .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

        setEvents(normalized);
      } catch (err) {
        console.error('Failed to fetch audit events:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvents();
    const interval = setInterval(fetchEvents, 10000);
    return () => clearInterval(interval);
  }, [orderId]);

  const getEventIcon = (eventType) => {
    const normalized = String(eventType || '').toLowerCase();
    if (normalized.includes('decision') || normalized.includes('execute') || normalized.includes('complete')) {
      return <CheckCircle size={16} className="event-icon success" />;
    }
    if (normalized.includes('error') || normalized.includes('reject') || normalized.includes('blocked')) {
      return <AlertCircle size={16} className="event-icon error" />;
    }
    if (normalized.includes('pending') || normalized.includes('queued') || normalized.includes('running')) {
      return <Clock size={16} className="event-icon pending" />;
    }
    return <FileText size={16} className="event-icon" />;
  };

  if (loading) {
    return <div className="panel-loading">Loading audit trail...</div>;
  }

  if (events.length === 0) {
    return (
      <div className="empty-state">
        <FileText size={32} />
        <p>No audit events found</p>
      </div>
    );
  }

  return (
    <div className={`audit-timeline ${expanded ? 'expanded' : 'compact'}`}>
      <div className="timeline">
        {events.map((event, idx) => {
          const isExpanded = expandedEvent === event.event_id;
          const timestamp = new Date(event.timestamp);

          return (
            <div key={event.event_id || idx} className="timeline-item">
              <div className="timeline-marker">
                <div className="marker-dot" />
                {idx < events.length - 1 && <div className="marker-line" />}
              </div>

              <div className="timeline-content">
                <button
                  className="timeline-header"
                  onClick={() => setExpandedEvent(isExpanded ? null : event.event_id)}
                >
                  <div className="header-left">
                    {getEventIcon(event.event_type)}
                    <div className="event-info">
                      <span className="event-type">{event.event_type}</span>
                      <span className="event-time">{timestamp.toLocaleTimeString()}</span>
                    </div>
                  </div>

                  <div className="header-right">
                    {expanded && event.details && (
                      isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </button>

                {isExpanded && event.details && (
                  <div className="timeline-details">
                    <div className="detail-row">
                      <span className="detail-key">Event ID:</span>
                      <code className="detail-value">{event.event_id}</code>
                    </div>

                    {event.details.actor && (
                      <div className="detail-row">
                        <span className="detail-key">Actor:</span>
                        <span className="detail-value">{event.details.actor}</span>
                      </div>
                    )}

                    {event.details.symbol && (
                      <div className="detail-row">
                        <span className="detail-key">Symbol:</span>
                        <span className="detail-value">{event.details.symbol}</span>
                      </div>
                    )}

                    {event.details.side && (
                      <div className="detail-row">
                        <span className="detail-key">Side:</span>
                        <span className={`detail-value ${event.details.side}`}>
                          {String(event.details.side).toUpperCase()}
                        </span>
                      </div>
                    )}

                    {event.details.quantity && (
                      <div className="detail-row">
                        <span className="detail-key">Quantity:</span>
                        <span className="detail-value">{event.details.quantity}</span>
                      </div>
                    )}

                    {event.details.reason && (
                      <div className="detail-row reason">
                        <span className="detail-key">Reason:</span>
                        <p className="detail-value">{event.details.reason}</p>
                      </div>
                    )}

                    {event.details.policy_gate && (
                      <div className="detail-row">
                        <span className="detail-key">Policy Gate:</span>
                        <span className="detail-value">{event.details.policy_gate}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AuditTimeline;
