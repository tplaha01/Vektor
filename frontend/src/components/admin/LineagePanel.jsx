import React, { useEffect, useState } from 'react';
import { GitBranch, CircleAlert, CircleCheck, Clock } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const POLL_MS = 5000;

function statusClass(value) {
  const v = String(value || '').toLowerCase();
  if (v === 'completed' || v === 'approved' || v === 'executed') return 'ok';
  if (v === 'blocked' || v === 'failed' || v === 'rejected') return 'bad';
  if (v === 'running' || v === 'queued' || v === 'pending') return 'wait';
  return 'neutral';
}

function shortId(value, size = 16) {
  const text = String(value || '');
  if (text.length <= size) return text || 'n/a';
  return `${text.slice(0, size)}...`;
}

function reportHref(id) {
  return `/research?report=${encodeURIComponent(id)}`;
}

function blogHref(id) {
  return `/blog?id=${encodeURIComponent(id)}`;
}

const LineagePanel = ({ limit = 20 }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const payload = await adminAPI.getRecentLineage(limit);
        const nextRows = adminAPI.normalizeArray(payload, 'rows');
        if (mounted) {
          setRows(nextRows);
        }
      } catch (err) {
        console.error('Failed to fetch lineage rows:', err);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [limit]);

  const handleInspectRun = async (runId) => {
    const nextId = String(runId || '').trim();
    if (!nextId) return;
    setSelectedRunId(nextId);
    setDetailLoading(true);
    try {
      const payload = await adminAPI.getLineageRunDetail(nextId, 300);
      setDetail(payload || null);
    } catch (err) {
      console.error('Failed to fetch lineage run detail:', err);
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) {
    return <div className="panel-loading">Loading lineage...</div>;
  }

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <GitBranch size={30} />
        <p>No lineage data yet</p>
      </div>
    );
  }

  return (
    <div className="lineage-panel">
      <div className="lineage-header">
        <div className="lineage-title-wrap">
          <GitBranch size={16} />
          <span className="lineage-title">Signal to Execution Lineage</span>
        </div>
        <span className="lineage-count">{rows.length} runs</span>
      </div>

      <div className="lineage-table-wrap">
        <table className="lineage-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Symbol</th>
              <th>Analysts</th>
              <th>Fund Manager</th>
              <th>Trader</th>
              <th>Decision</th>
              <th>Order</th>
              <th>Blocked</th>
              <th>Blog</th>
              <th>Updated</th>
              <th>Inspect</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const blocked = Array.isArray(row.blocked_reasons) ? row.blocked_reasons : [];
              const blogPosts = Array.isArray(row.blog_post_ids) ? row.blog_post_ids : [];
              const analystCompleted = Number(row.analyst_completed || 0);
              const analystExpected = Number(row.analyst_expected || 0);
              const analystPct = analystExpected > 0 ? Math.round((analystCompleted / analystExpected) * 100) : 0;

              return (
                <tr key={row.run_id}>
                  <td className="lineage-id" title={row.run_id}>
                    {shortId(row.run_id, 20)}
                  </td>
                  <td>{row.symbol || 'n/a'}</td>
                  <td>
                    <div className="lineage-analyst-cell">
                      <span>{analystCompleted}/{analystExpected}</span>
                      <span className="lineage-muted">{analystPct}%</span>
                    </div>
                  </td>
                  <td>
                    <span className={`lineage-chip ${statusClass(row.fund_manager_status)}`}>
                      {row.fund_manager_status || 'unknown'}
                    </span>
                  </td>
                  <td>
                    <span className={`lineage-chip ${statusClass(row.trader_status)}`}>
                      {row.trader_status || 'unknown'}
                    </span>
                  </td>
                  <td className="lineage-id" title={row.decision_id || ''}>
                    {shortId(row.decision_id || 'n/a', 14)}
                  </td>
                  <td className="lineage-id">{row.order_id || 'n/a'}</td>
                  <td>
                    {blocked.length ? (
                      <span className="lineage-badge blocked" title={blocked.join(', ')}>
                        <CircleAlert size={12} />
                        {blocked.length}
                      </span>
                    ) : (
                      <span className="lineage-badge clear">
                        <CircleCheck size={12} />
                        0
                      </span>
                    )}
                  </td>
                  <td>{blogPosts.length}</td>
                  <td className="lineage-muted">
                    <span className="lineage-time">
                      <Clock size={12} />
                      {row.updated_at ? new Date(row.updated_at).toLocaleTimeString() : 'n/a'}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`lineage-inspect-btn ${selectedRunId === row.run_id ? 'active' : ''}`}
                      onClick={() => handleInspectRun(row.run_id)}
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {(selectedRunId || detailLoading || detail) && (
        <div className="lineage-detail">
          <div className="lineage-detail-head">
            <h4>Run Drill-Down</h4>
            <span className="lineage-detail-run">{selectedRunId || 'n/a'}</span>
          </div>

          {detailLoading ? (
            <div className="panel-loading">Loading run detail...</div>
          ) : detail ? (
            <div className="lineage-detail-grid">
              <section className="lineage-detail-card">
                <h5>Decision</h5>
                <div className="lineage-detail-kv"><span>ID</span><code>{detail?.decision?.decision_id || 'n/a'}</code></div>
                <div className="lineage-detail-kv"><span>Status</span><strong>{detail?.decision?.status || 'unknown'}</strong></div>
                <div className="lineage-detail-kv"><span>Sleeve</span><strong>{detail?.decision?.sleeve || 'n/a'}</strong></div>
                <div className="lineage-detail-kv"><span>Intent</span><code>{shortId(detail?.decision?.intent_id || 'n/a', 22)}</code></div>
              </section>

              <section className="lineage-detail-card">
                <h5>Related IDs</h5>
                <div className="lineage-id-list">
                  <div className="lineage-id-block">
                    <span>Research Reports</span>
                    <div className="lineage-pill-list">
                      {(detail.related_research_report_ids || []).slice(0, 15).map((id) => (
                        <a key={id} className="lineage-pill lineage-pill-link" href={reportHref(id)} target="_blank" rel="noreferrer">
                          {shortId(id, 20)}
                        </a>
                      ))}
                    </div>
                  </div>
                  <div className="lineage-id-block">
                    <span>Blog Posts</span>
                    <div className="lineage-pill-list">
                      {(detail.related_blog_post_ids || []).slice(0, 15).map((id) => (
                        <a key={id} className="lineage-pill lineage-pill-link" href={blogHref(id)} target="_blank" rel="noreferrer">
                          {shortId(id, 20)}
                        </a>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="lineage-detail-card lineage-detail-wide">
                <h5>Audit Timeline</h5>
                <div className="lineage-event-list">
                  {(detail.audit_timeline || []).slice(-20).map((evt) => (
                    <div key={`${evt.event_id}-${evt.timestamp}`} className="lineage-event-row">
                      <code>{evt.event_type || 'event'}</code>
                      <span>{evt.timestamp ? new Date(evt.timestamp).toLocaleString() : 'n/a'}</span>
                    </div>
                  ))}
                  {(!detail.audit_timeline || detail.audit_timeline.length === 0) && (
                    <div className="lineage-empty">No audit events for this run yet.</div>
                  )}
                </div>
              </section>

              <section className="lineage-detail-card lineage-detail-wide">
                <h5>Task Events</h5>
                <div className="lineage-event-list">
                  {(detail.task_events || []).slice(0, 40).map((evt) => (
                    <div key={`${evt.task_id}-${evt.timestamp}-${evt.event}`} className="lineage-event-row">
                      <span>{evt.role} · {evt.status}</span>
                      <span>{evt.event}</span>
                      <span>{evt.timestamp ? new Date(evt.timestamp).toLocaleString() : 'n/a'}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <div className="lineage-empty">Run detail unavailable.</div>
          )}
        </div>
      )}
    </div>
  );
};

export default LineagePanel;
