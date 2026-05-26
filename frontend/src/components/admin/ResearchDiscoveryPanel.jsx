import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Search } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const toneClass = (conviction) => {
  const value = Number(conviction || 0);
  if (value >= 60) return 'ops-positive';
  if (value < 40) return 'ops-negative';
  return '';
};

const shortDate = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleDateString();
};

export default function ResearchDiscoveryPanel({ onNavigate }) {
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIdeaId, setSelectedIdeaId] = useState('');
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    type: '',
    convictionBand: '',
    source: '',
    search: '',
  });

  const loadIdeas = async () => {
    setLoading(true);
    try {
      const payload = await adminAPI.getAdminResearchIdeas({ ...filters, limit: 80 });
      setIdeas(adminAPI.normalizeArray(payload, 'ideas'));
    } catch (err) {
      console.error('Failed to load research ideas:', err);
      setIdeas([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIdeas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.status, filters.type, filters.convictionBand, filters.source, filters.search]);

  const selectedIdeaRow = useMemo(
    () => ideas.find((item) => item.idea_id === selectedIdeaId) || null,
    [ideas, selectedIdeaId]
  );

  const inspectIdea = async (ideaId) => {
    setSelectedIdeaId(ideaId);
    setDetailLoading(true);
    try {
      const payload = await adminAPI.getAdminResearchIdeaDetail(ideaId);
      setSelectedIdea(payload || null);
    } catch (err) {
      console.error('Failed to load idea detail:', err);
      setSelectedIdea(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const archiveIdea = async (ideaId) => {
    setActionLoading(`archive-${ideaId}`);
    try {
      await adminAPI.updateAdminResearchIdea(ideaId, { status: 'ARCHIVED', reason: 'archived_from_admin_panel' });
      await loadIdeas();
      if (selectedIdeaId === ideaId) {
        await inspectIdea(ideaId);
      }
    } catch (err) {
      console.error('Failed to archive idea:', err);
    } finally {
      setActionLoading('');
    }
  };

  const createThesis = async (idea) => {
    if (!idea?.report_id) return;
    setActionLoading(`thesis-${idea.report_id}`);
    try {
      await adminAPI.createAdminThesis({
        report_id: idea.report_id,
        run_id: idea.run_id || null,
        agent_id: 'ceo',
        sleeve: 'tactical',
        statement: idea.summary || idea.title || 'Create thesis from admin idea',
        conviction: Math.max(0, Math.min(1, Number(idea.conviction || 0) / 100)),
      });
      if (onNavigate) onNavigate('decisions');
    } catch (err) {
      console.error('Failed to create thesis from idea:', err);
    } finally {
      setActionLoading('');
    }
  };

  return (
    <div className="ops-grid ops-grid-overview">
      <section className="ops-panel">
        <div className="ops-panel-header">
          <div>
            <p className="ops-panel-eyebrow">Research & Discovery</p>
            <h2 className="ops-panel-title">Ideas Queue</h2>
            <p className="ops-panel-description">Filter active ideas, inspect context, archive noise, and promote to thesis.</p>
          </div>
        </div>
        <div className="ops-panel-body">
          <div className="ops-form-grid">
            <label className="ops-field">
              <span>Status</span>
              <select className="ops-input" value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}>
                <option value="">All</option>
                <option value="ACTIVE">Active</option>
                <option value="ARCHIVED">Archived</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </label>
            <label className="ops-field">
              <span>Type</span>
              <select className="ops-input" value={filters.type} onChange={(event) => setFilters((prev) => ({ ...prev, type: event.target.value }))}>
                <option value="">All</option>
                <option value="MACRO">Macro</option>
                <option value="SECTOR">Sector</option>
                <option value="FUNDAMENTAL">Fundamental</option>
                <option value="TECHNICAL">Technical</option>
                <option value="EVENT">Event</option>
              </select>
            </label>
            <label className="ops-field">
              <span>Conviction</span>
              <select className="ops-input" value={filters.convictionBand} onChange={(event) => setFilters((prev) => ({ ...prev, convictionBand: event.target.value }))}>
                <option value="">All</option>
                <option value="HIGH">High (&gt;=60%)</option>
                <option value="MEDIUM">Medium (40-60%)</option>
                <option value="LOW">Low (&lt;40%)</option>
              </select>
            </label>
            <label className="ops-field">
              <span>Source</span>
              <select className="ops-input" value={filters.source} onChange={(event) => setFilters((prev) => ({ ...prev, source: event.target.value }))}>
                <option value="">All</option>
                <option value="AGENT_DISCOVERY">Agent Discovery</option>
                <option value="CEO_INPUT">CEO Input</option>
                <option value="MARKET_SCAN">Market Scan</option>
              </select>
            </label>
          </div>

          <label className="ops-field">
            <span>Search</span>
            <div className="ops-search-wrap">
              <Search size={14} />
              <input
                className="ops-input"
                type="text"
                value={filters.search}
                onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))}
                placeholder="Fed pivot, earnings revision, sector rotation..."
              />
            </div>
          </label>

          {loading ? (
            <div className="ops-empty">Loading research ideas...</div>
          ) : ideas.length === 0 ? (
            <div className="ops-empty">No ideas match current filters.</div>
          ) : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Conviction</th>
                    <th>Days</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {ideas.map((idea) => (
                    <tr key={idea.idea_id}>
                      <td className="ops-symbol-cell">{String(idea.idea_id || '').slice(0, 10)}</td>
                      <td>{idea.title || 'Untitled'}</td>
                      <td>{idea.type || 'n/a'}</td>
                      <td className={toneClass(idea.conviction)}>{Number(idea.conviction || 0).toFixed(1)}%</td>
                      <td>{idea.days_live || 0}</td>
                      <td>{idea.status || 'ACTIVE'}</td>
                      <td>
                        <div className="ops-button-row compact">
                          <button type="button" className="ops-button secondary small" onClick={() => inspectIdea(idea.idea_id)}>Inspect</button>
                          <button
                            type="button"
                            className="ops-button secondary small"
                            disabled={actionLoading === `archive-${idea.idea_id}`}
                            onClick={() => archiveIdea(idea.idea_id)}
                          >
                            Archive
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="ops-panel">
        <div className="ops-panel-header">
          <div>
            <p className="ops-panel-eyebrow">Idea Detail</p>
            <h2 className="ops-panel-title">{selectedIdeaRow?.title || 'Select an idea'}</h2>
            <p className="ops-panel-description">Source context, signal notes, and thesis conversion controls.</p>
          </div>
        </div>
        <div className="ops-panel-body">
          {detailLoading ? (
            <div className="ops-empty">Loading idea detail...</div>
          ) : selectedIdea ? (
            <>
              <div className="ops-kv-grid">
                <div className="ops-kv"><span className="ops-kv-label">Type</span><strong className="ops-kv-value">{selectedIdea.type || 'n/a'}</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Source</span><strong className="ops-kv-value">{selectedIdea.source || 'n/a'}</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Conviction</span><strong className="ops-kv-value">{Number(selectedIdea.conviction || 0).toFixed(1)}%</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Created</span><strong className="ops-kv-value">{shortDate(selectedIdea.created_at)}</strong></div>
              </div>
              <p className="ops-note">{selectedIdea.summary || 'No summary provided.'}</p>
              <div className="ops-inline-chips">
                {(selectedIdea.asset_universe || []).slice(0, 12).map((asset) => (
                  <span key={asset} className="ops-chip">{asset}</span>
                ))}
              </div>
              <div className="ops-task-list">
                {(selectedIdea.signals || []).slice(0, 6).map((signal, index) => (
                  <article key={`${signal}-${index}`} className="ops-task-row">
                    <div className="ops-task-head">
                      <strong>Signal {index + 1}</strong>
                    </div>
                    <div className="ops-task-meta">
                      <span>{String(signal || 'n/a')}</span>
                    </div>
                  </article>
                ))}
              </div>
              <div className="ops-button-row">
                <button
                  type="button"
                  className="ops-button"
                  disabled={actionLoading === `thesis-${selectedIdea.report_id}`}
                  onClick={() => createThesis(selectedIdea)}
                >
                  Create Thesis
                </button>
              </div>
            </>
          ) : (
            <div className="ops-empty">
              <AlertCircle size={16} /> Choose a row from the idea queue to inspect details.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
