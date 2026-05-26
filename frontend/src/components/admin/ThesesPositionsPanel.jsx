import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const usd = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });

const convictionTone = (value) => {
  const score = Number(value || 0);
  if (score >= 60) return 'ops-positive';
  if (score < 40) return 'ops-negative';
  return '';
};

const pnlTone = (value) => (Number(value || 0) >= 0 ? 'ops-positive' : 'ops-negative');

export default function ThesesPositionsPanel({ onNavigate }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState('');
  const [filters, setFilters] = useState({ status: 'ACTIVE', sort: 'conviction_desc' });

  const loadTheses = async () => {
    setLoading(true);
    try {
      const payload = await adminAPI.getAdminTheses({ ...filters, limit: 120 });
      setRows(adminAPI.normalizeArray(payload, 'theses'));
    } catch (err) {
      console.error('Failed to load theses:', err);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTheses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.status, filters.sort]);

  const selectedRow = useMemo(() => rows.find((item) => item.thesis_id === selectedId) || null, [rows, selectedId]);

  const inspect = async (thesisId) => {
    setSelectedId(thesisId);
    setDetailLoading(true);
    try {
      const payload = await adminAPI.getAdminThesisDetail(thesisId);
      setDetail(payload || null);
    } catch (err) {
      console.error('Failed to load thesis detail:', err);
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const updateConviction = async (thesis) => {
    const current = Number(thesis?.conviction_pct || 0);
    const nextValue = Number.isFinite(current) ? Math.min(100, Math.max(0, current + 5)) : 50;
    setBusy(`conviction-${thesis.thesis_id}`);
    try {
      await adminAPI.updateAdminThesisConviction(thesis.thesis_id, {
        convictionPct: nextValue,
        reason: 'increment_from_admin_panel',
      });
      await loadTheses();
      await inspect(thesis.thesis_id);
    } catch (err) {
      console.error('Failed to update conviction:', err);
    } finally {
      setBusy('');
    }
  };

  const increaseAllocation = async (thesis) => {
    const nextK = Math.ceil((Number(thesis?.allocation_usd || 0) + 50000) / 1000);
    setBusy(`allocation-${thesis.thesis_id}`);
    try {
      await adminAPI.updateAdminThesisAllocation(thesis.thesis_id, {
        allocationK: nextK,
        reason: 'increase_from_admin_panel',
      });
      await loadTheses();
      await inspect(thesis.thesis_id);
    } catch (err) {
      console.error('Failed to update allocation:', err);
    } finally {
      setBusy('');
    }
  };

  const closeThesis = async (thesis) => {
    setBusy(`close-${thesis.thesis_id}`);
    try {
      await adminAPI.updateAdminThesisStatus(thesis.thesis_id, {
        status: 'CLOSED',
        reason: 'manual_close_from_admin_panel',
        notes: 'Closed from theses panel',
      });
      await loadTheses();
      await inspect(thesis.thesis_id);
      if (onNavigate) onNavigate('orders');
    } catch (err) {
      console.error('Failed to close thesis:', err);
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="ops-grid ops-grid-overview">
      <section className="ops-panel">
        <div className="ops-panel-header">
          <div>
            <p className="ops-panel-eyebrow">Thesis Tracking</p>
            <h2 className="ops-panel-title">Theses & Positions</h2>
            <p className="ops-panel-description">Track conviction, allocation, live PnL, and exit pressure for active bets.</p>
          </div>
        </div>
        <div className="ops-panel-body">
          <div className="ops-form-grid">
            <label className="ops-field">
              <span>Status</span>
              <select className="ops-input" value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}>
                <option value="ACTIVE">Active</option>
                <option value="CLOSING">Closing</option>
                <option value="CLOSED">Closed</option>
                <option value="ALL">All</option>
              </select>
            </label>
            <label className="ops-field">
              <span>Sort</span>
              <select className="ops-input" value={filters.sort} onChange={(event) => setFilters((prev) => ({ ...prev, sort: event.target.value }))}>
                <option value="conviction_desc">Conviction</option>
                <option value="pnl_desc">PnL</option>
                <option value="allocation_desc">Allocation</option>
                <option value="exit_signal">Exit Signal</option>
              </select>
            </label>
          </div>

          {loading ? (
            <div className="ops-empty">Loading theses...</div>
          ) : rows.length === 0 ? (
            <div className="ops-empty">No theses available for the selected filters.</div>
          ) : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Conviction</th>
                    <th>Allocation</th>
                    <th>PnL</th>
                    <th>Exit</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.thesis_id}>
                      <td className="ops-symbol-cell">{String(row.thesis_id || '').slice(0, 12)}</td>
                      <td>{row.title || row.statement || 'Untitled thesis'}</td>
                      <td className={convictionTone(row.conviction_pct)}>{Number(row.conviction_pct || 0).toFixed(1)}%</td>
                      <td>{usd(row.allocation_usd)}</td>
                      <td className={pnlTone(row.pnl_usd)}>{usd(row.pnl_usd)}</td>
                      <td>{row.exit_signal || 'HOLD'}</td>
                      <td>
                        <button type="button" className="ops-button secondary small" onClick={() => inspect(row.thesis_id)}>
                          Inspect
                        </button>
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
            <p className="ops-panel-eyebrow">Thesis Detail</p>
            <h2 className="ops-panel-title">{selectedRow?.title || 'Select a thesis'}</h2>
            <p className="ops-panel-description">Adjust conviction, allocation, and close thesis-linked holdings.</p>
          </div>
        </div>
        <div className="ops-panel-body">
          {detailLoading ? (
            <div className="ops-empty">Loading thesis detail...</div>
          ) : detail ? (
            <>
              <div className="ops-kv-grid">
                <div className="ops-kv"><span className="ops-kv-label">Conviction</span><strong className="ops-kv-value">{Number(detail.conviction_pct || 0).toFixed(1)}%</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Allocation</span><strong className="ops-kv-value">{usd(detail.allocation_usd)}</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Max Allocation</span><strong className="ops-kv-value">{usd(detail.max_allocation_usd)}</strong></div>
                <div className="ops-kv"><span className="ops-kv-label">Exit Signal</span><strong className="ops-kv-value">{detail.exit_signal || 'HOLD'}</strong></div>
              </div>
              <p className="ops-note">{detail.statement || 'No thesis statement available.'}</p>

              <div className="ops-button-row">
                <button
                  type="button"
                  className="ops-button secondary"
                  disabled={busy === `conviction-${detail.thesis_id}`}
                  onClick={() => updateConviction(detail)}
                >
                  Edit Conviction (+5%)
                </button>
                <button
                  type="button"
                  className="ops-button secondary"
                  disabled={busy === `allocation-${detail.thesis_id}`}
                  onClick={() => increaseAllocation(detail)}
                >
                  Increase Allocation (+$50K)
                </button>
                <button
                  type="button"
                  className="ops-button danger"
                  disabled={busy === `close-${detail.thesis_id}`}
                  onClick={() => closeThesis(detail)}
                >
                  Close Thesis
                </button>
              </div>

              <div className="ops-task-list">
                {(detail.holdings || []).length ? (
                  detail.holdings.map((holding) => (
                    <article key={holding.position_id || holding.symbol} className="ops-task-row">
                      <div className="ops-task-head">
                        <strong>{holding.symbol}</strong>
                        <span className={pnlTone(holding.unrealized_pnl)}>{usd(holding.unrealized_pnl)}</span>
                      </div>
                      <div className="ops-task-meta">
                        <span>Qty {Number(holding.quantity || 0).toFixed(2)}</span>
                        <span>{usd(holding.market_value)}</span>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="ops-empty">No linked holdings found for this thesis.</div>
                )}
              </div>
            </>
          ) : (
            <div className="ops-empty">
              <AlertCircle size={16} /> Select a thesis from the table to inspect and manage it.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

