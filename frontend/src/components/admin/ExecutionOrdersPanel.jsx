import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';
import { useToast } from '../common/Toast';

const currency = (value, digits = 0) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

const percentBps = (value) => `${Number(value || 0).toFixed(2)} bps`;

const shortDateTime = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleString();
};

const statusTone = (value) => {
  const normalized = String(value || '').toUpperCase();
  if (normalized === 'FILLED' || normalized === 'EXECUTED') return 'ops-positive';
  if (normalized === 'PENDING') return '';
  if (normalized === 'CANCELLED' || normalized === 'BLOCKED') return 'ops-negative';
  return '';
};

const slippageTone = (value) => {
  const current = Number(value || 0);
  if (current <= -1) return 'ops-positive';
  if (current >= 1) return 'ops-negative';
  return '';
};

const toPayload = (form) => ({
  symbol: String(form.symbol || '').trim().toUpperCase(),
  side: String(form.side || 'buy').toLowerCase(),
  quantity: Number(form.quantity || 0),
  order_type: String(form.orderType || 'MARKET').toUpperCase(),
  limit_price: form.limitPrice === '' ? null : Number(form.limitPrice),
  time_in_force: String(form.timeInForce || 'IOC').toUpperCase(),
  reason: String(form.reason || '').trim() || 'manual_admin_order',
  thesis_id: form.thesisId || null,
  override: Boolean(form.override),
});

export default function ExecutionOrdersPanel() {
  const { success, error: showError, info, warning } = useToast();
  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState(null);
  const [tapeRows, setTapeRows] = useState([]);
  const [brokerConfig, setBrokerConfig] = useState(null);
  const [executionPriority, setExecutionPriority] = useState(null);
  const [theses, setTheses] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [fills, setFills] = useState([]);
  const [quality, setQuality] = useState(null);
  const [auditTimeline, setAuditTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState('');
  const [priorityForm, setPriorityForm] = useState('QUALITY');
  const [validation, setValidation] = useState(null);
  const [filters, setFilters] = useState({
    status: 'ALL',
    time: 'ALL',
    side: 'ALL',
  });
  const [form, setForm] = useState({
    symbol: 'AAPL',
    orderType: 'MARKET',
    side: 'buy',
    quantity: '10',
    limitPrice: '',
    timeInForce: 'IOC',
    reason: 'manual alpha expression',
    thesisId: '',
    override: false,
  });

  const loadPanel = async () => {
    setLoading(true);
    try {
      const [ordersPayload, tapePayload, brokerPayload, priorityPayload, thesesPayload] = await Promise.all([
        adminAPI.getAdminOrders({ ...filters, limit: 120 }),
        adminAPI.getAdminOrderTape({ side: filters.side, days: filters.time === 'TODAY' ? 1 : filters.time === 'THIS_WEEK' ? 7 : filters.time === 'THIS_MONTH' ? 31 : 90 }),
        adminAPI.getAdminBrokerConfig(),
        adminAPI.getAdminExecutionPriority(),
        adminAPI.getAdminTheses({ status: 'ALL', sort: 'conviction_desc', limit: 80 }),
      ]);
      setOrders(adminAPI.normalizeArray(ordersPayload, 'orders'));
      setSummary(ordersPayload?.summary || null);
      setTapeRows(adminAPI.normalizeArray(tapePayload, 'rows'));
      setBrokerConfig(brokerPayload || null);
      setExecutionPriority(priorityPayload || null);
      setPriorityForm(String(priorityPayload?.priority || 'QUALITY').toUpperCase());
      setTheses(adminAPI.normalizeArray(thesesPayload, 'theses'));
    } catch (err) {
      console.error('Failed to load execution orders panel:', err);
      setOrders([]);
      setTapeRows([]);
      showError(`Failed to load execution surface: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadOrderDetail = async (orderId) => {
    if (!orderId) return;
    setSelectedOrderId(orderId);
    setDetailLoading(true);
    try {
      const [detailPayload, fillsPayload, qualityPayload, auditPayload] = await Promise.all([
        adminAPI.getAdminOrderDetail(orderId),
        adminAPI.getAdminOrderFills(orderId),
        adminAPI.getAdminOrderExecutionQuality(orderId),
        adminAPI.getOrderAuditTimeline(orderId),
      ]);
      setSelectedOrder(detailPayload || null);
      setFills(adminAPI.normalizeArray(fillsPayload, 'fills'));
      setQuality(qualityPayload || null);
      setAuditTimeline(adminAPI.normalizeArray(auditPayload, 'events'));
    } catch (err) {
      console.error('Failed to load order detail:', err);
      setSelectedOrder(null);
      setFills([]);
      setQuality(null);
      setAuditTimeline([]);
      showError(`Failed to load order detail: ${err.message}`);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadPanel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.status, filters.time, filters.side]);

  useEffect(() => {
    if (!orders.length) {
      setSelectedOrderId('');
      setSelectedOrder(null);
      setFills([]);
      setQuality(null);
      setAuditTimeline([]);
      return;
    }
    if (!selectedOrderId || !orders.some((order) => order.order_id === selectedOrderId)) {
      loadOrderDetail(orders[0].order_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders, selectedOrderId]);

  const activeOrder = useMemo(
    () => orders.find((item) => item.order_id === selectedOrderId) || selectedOrder || null,
    [orders, selectedOrder, selectedOrderId]
  );

  const handleValidate = async () => {
    try {
      setBusy('validate');
      const payload = await adminAPI.validateAdminOrder(toPayload(form));
      setValidation(payload || null);
      if ((payload?.errors || []).length) {
        showError(payload.errors.join(', '));
      } else if (payload?.requires_override) {
        warning('Order requires manual override before submit.');
      } else {
        info('Risk check passed.');
      }
    } catch (err) {
      showError(`Validation failed: ${err.message}`);
    } finally {
      setBusy('');
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      setBusy('submit');
      const payload = await adminAPI.submitAdminOrder(toPayload(form));
      setValidation(payload?.validation || validation);
      if (payload?.approved === false) {
        showError((payload?.reasons || []).join(', ') || payload?.error || 'order_blocked');
        return;
      }
      const orderId = payload?.order?.order_id;
      success(payload?.message || `Order ${orderId || ''} executed`);
      await loadPanel();
      if (orderId) {
        await loadOrderDetail(orderId);
      }
    } catch (err) {
      showError(`Submit failed: ${err.message}`);
    } finally {
      setBusy('');
    }
  };

  const handleCancel = async () => {
    if (!activeOrder?.order_id) return;
    try {
      setBusy(`cancel-${activeOrder.order_id}`);
      await adminAPI.updateAdminOrder(activeOrder.order_id, {
        status: 'CANCELLED',
        reason: 'desk_pull_from_execution_panel',
      });
      success(`Order ${activeOrder.order_id} cancelled`);
      await loadPanel();
      await loadOrderDetail(activeOrder.order_id);
    } catch (err) {
      showError(`Cancel failed: ${err.message}`);
    } finally {
      setBusy('');
    }
  };

  const handlePrioritySave = async () => {
    try {
      setBusy('priority');
      const payload = await adminAPI.updateAdminExecutionPriority({
        priority: priorityForm,
        reason: 'updated_from_execution_orders_panel',
      });
      setExecutionPriority(payload || null);
      success(`Execution priority set to ${payload?.priority || priorityForm}`);
    } catch (err) {
      showError(`Priority update failed: ${err.message}`);
    } finally {
      setBusy('');
    }
  };

  if (loading) {
    return <div className="ops-empty">Loading execution and orders surface...</div>;
  }

  return (
    <>
      <div className="ops-metric-grid ops-metric-grid-control">
        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Orders</span>
              <strong className="ops-metric-value">{Number(orders.length || 0)}</strong>
            </div>
          </div>
          <p className="ops-metric-detail">{Number(summary?.filled || 0)} filled / {Number(summary?.pending || 0)} pending</p>
        </article>
        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Gross Notional</span>
              <strong className="ops-metric-value">{currency(summary?.gross_notional_usd)}</strong>
            </div>
          </div>
          <p className="ops-metric-detail">Paper execution footprint</p>
        </article>
        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Avg Slippage</span>
              <strong className={`ops-metric-value ${slippageTone(summary?.avg_slippage_bps)}`}>{percentBps(summary?.avg_slippage_bps)}</strong>
            </div>
          </div>
          <p className="ops-metric-detail">Reference price vs avg fill</p>
        </article>
        <article className="ops-metric">
          <div className="ops-metric-head">
            <div>
              <span className="ops-metric-label">Priority</span>
              <strong className="ops-metric-value">{executionPriority?.priority || 'QUALITY'}</strong>
            </div>
          </div>
          <p className="ops-metric-detail">{brokerConfig?.broker || 'Paper broker'} / {brokerConfig?.status || 'ready'}</p>
        </article>
      </div>

      <div className="ops-grid ops-grid-overview">
        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Orders Management</p>
              <h2 className="ops-panel-title">Execution & Orders</h2>
              <p className="ops-panel-description">Recent orders, fill status, and slippage-ranked execution review.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Status</span>
                <select className="ops-input" value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}>
                  <option value="ALL">All</option>
                  <option value="FILLED">Filled</option>
                  <option value="PENDING">Pending</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Time</span>
                <select className="ops-input" value={filters.time} onChange={(event) => setFilters((prev) => ({ ...prev, time: event.target.value }))}>
                  <option value="ALL">All</option>
                  <option value="TODAY">Today</option>
                  <option value="THIS_WEEK">This Week</option>
                  <option value="THIS_MONTH">This Month</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Side</span>
                <select className="ops-input" value={filters.side} onChange={(event) => setFilters((prev) => ({ ...prev, side: event.target.value }))}>
                  <option value="ALL">All</option>
                  <option value="BUY">Buy</option>
                  <option value="SELL">Sell</option>
                  <option value="SHORT">Short</option>
                </select>
              </label>
            </div>

            {orders.length === 0 ? (
              <div className="ops-empty">No orders match the current filters.</div>
            ) : (
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Status</th>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th>Size</th>
                      <th>Price</th>
                      <th>Time</th>
                      <th>Slippage</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.order_id}>
                        <td className="ops-symbol-cell">{order.order_id}</td>
                        <td className={statusTone(order.status)}>{order.status}</td>
                        <td>{order.symbol}</td>
                        <td>{order.side}</td>
                        <td>{Number(order.quantity || 0).toFixed(2)}</td>
                        <td>{currency(order.price, 2)}</td>
                        <td>{shortDateTime(order.time)}</td>
                        <td className={slippageTone(order.slippage_bps)}>{percentBps(order.slippage_bps)}</td>
                        <td>
                          <button type="button" className="ops-button secondary small" onClick={() => loadOrderDetail(order.order_id)}>
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
              <p className="ops-panel-eyebrow">Order Detail</p>
              <h2 className="ops-panel-title">{activeOrder?.order_id || 'Select an order'}</h2>
              <p className="ops-panel-description">Context, fills, audit trail, and execution-quality readout.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            {detailLoading ? (
              <div className="ops-empty">Loading order detail...</div>
            ) : selectedOrder ? (
              <>
                <div className="ops-kv-grid">
                  <div className="ops-kv"><span className="ops-kv-label">Symbol</span><strong className="ops-kv-value">{selectedOrder.symbol}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Approval</span><strong className="ops-kv-value">{selectedOrder.execution_context?.approval_status || 'auto'}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Conviction</span><strong className="ops-kv-value">{Number(selectedOrder.execution_context?.signal_conviction_pct || 0).toFixed(1)}%</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Broker</span><strong className="ops-kv-value">{selectedOrder.execution?.broker || 'Paper broker'}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Order Type</span><strong className="ops-kv-value">{selectedOrder.order_details?.order_type || 'MARKET'}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Time In Force</span><strong className="ops-kv-value">{selectedOrder.order_details?.time_in_force || 'IOC'}</strong></div>
                </div>

                <p className="ops-note">{selectedOrder.notes || 'No operator notes recorded for this order.'}</p>

                <div className="ops-inline-chips">
                  <span className="ops-chip">Thesis {selectedOrder.execution_context?.thesis_id || 'none'}</span>
                  <span className="ops-chip">Decision {selectedOrder.execution_context?.decision_id || 'n/a'}</span>
                  <span className={`ops-chip ${slippageTone(quality?.slippage_bps)}`}>{quality?.interpretation || 'In line'}</span>
                </div>

                <div className="ops-kv-grid">
                  <div className="ops-kv"><span className="ops-kv-label">Reference / VWAP</span><strong className="ops-kv-value">{currency(quality?.reference_price, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Avg Fill</span><strong className="ops-kv-value">{currency(quality?.actual_avg_fill_price, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Slippage</span><strong className={`ops-kv-value ${slippageTone(quality?.slippage_bps)}`}>{percentBps(quality?.slippage_bps)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Commission</span><strong className="ops-kv-value">{currency(selectedOrder.execution?.commission_usd, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Total Cost</span><strong className="ops-kv-value">{currency(selectedOrder.cost_breakdown?.total_cost_usd, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Submitted</span><strong className="ops-kv-value">{shortDateTime(selectedOrder.execution?.submitted_at)}</strong></div>
                </div>

                <p className="ops-note">{quality?.root_cause || 'No execution-quality commentary available.'}</p>

                <div className="ops-button-row">
                  <button type="button" className="ops-button secondary" onClick={() => loadOrderDetail(selectedOrder.order_id)}>View fills</button>
                  <button type="button" className="ops-button secondary" onClick={() => loadOrderDetail(selectedOrder.order_id)}>Audit trail</button>
                  <button
                    type="button"
                    className="ops-button danger"
                    disabled={String(selectedOrder.status || '').toUpperCase() !== 'PENDING' || busy === `cancel-${selectedOrder.order_id}`}
                    onClick={handleCancel}
                  >
                    Cancel pending order
                  </button>
                </div>

                <div className="ops-task-list">
                  {fills.length ? (
                    fills.map((fill) => (
                      <article key={fill.fill_id} className="ops-task-row">
                        <div className="ops-task-head">
                          <strong>{fill.fill_id}</strong>
                          <span>{currency(fill.price, 2)}</span>
                        </div>
                        <div className="ops-task-meta">
                          <span>{shortDateTime(fill.timestamp)}</span>
                          <span>Qty {Number(fill.quantity || 0).toFixed(2)}</span>
                          <span>{fill.venue}</span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="ops-empty">No fills found for this order.</div>
                  )}
                </div>

                <div className="ops-task-list">
                  {auditTimeline.length ? (
                    auditTimeline.slice(0, 8).map((event, index) => (
                      <article key={`${event.event_id || event.timestamp}-${index}`} className="ops-task-row">
                        <div className="ops-task-head">
                          <strong>{event.event_type || 'event'}</strong>
                          <span>{shortDateTime(event.timestamp)}</span>
                        </div>
                        <div className="ops-task-meta">
                          <span>{JSON.stringify(event.details || event.payload || {}).slice(0, 160)}</span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="ops-empty">No audit events available.</div>
                  )}
                </div>
              </>
            ) : (
              <div className="ops-empty">
                <AlertCircle size={16} /> Select an order from the table to inspect fills, tape, and audit context.
              </div>
            )}
          </div>
        </section>
      </div>

      <div className="ops-grid ops-grid-overview">
        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Manual Submission</p>
              <h2 className="ops-panel-title">Submit manual order</h2>
              <p className="ops-panel-description">Ticket entry with policy preview, override support, and thesis linkage.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            <form className="ops-form-stack" onSubmit={handleSubmit}>
              <div className="ops-form-grid">
                <label className="ops-field">
                  <span>Symbol</span>
                  <input
                    className="ops-input ops-input-uppercase"
                    type="text"
                    value={form.symbol}
                    onChange={(event) => setForm((prev) => ({ ...prev, symbol: event.target.value.toUpperCase() }))}
                  />
                </label>
                <label className="ops-field">
                  <span>Type</span>
                  <select className="ops-input" value={form.orderType} onChange={(event) => setForm((prev) => ({ ...prev, orderType: event.target.value }))}>
                    <option value="MARKET">Market</option>
                    <option value="LIMIT">Limit</option>
                  </select>
                </label>
                <label className="ops-field">
                  <span>Side</span>
                  <select className="ops-input" value={form.side} onChange={(event) => setForm((prev) => ({ ...prev, side: event.target.value }))}>
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </label>
                <label className="ops-field">
                  <span>Quantity</span>
                  <input className="ops-input" type="number" min="1" step="1" value={form.quantity} onChange={(event) => setForm((prev) => ({ ...prev, quantity: event.target.value }))} />
                </label>
                <label className="ops-field">
                  <span>Limit Price</span>
                  <input className="ops-input" type="number" min="0" step="0.01" value={form.limitPrice} onChange={(event) => setForm((prev) => ({ ...prev, limitPrice: event.target.value }))} />
                </label>
                <label className="ops-field">
                  <span>Time In Force</span>
                  <select className="ops-input" value={form.timeInForce} onChange={(event) => setForm((prev) => ({ ...prev, timeInForce: event.target.value }))}>
                    <option value="IOC">IOC</option>
                    <option value="DAY">DAY</option>
                    <option value="GTC">GTC</option>
                  </select>
                </label>
                <label className="ops-field">
                  <span>Linked Thesis</span>
                  <select className="ops-input" value={form.thesisId} onChange={(event) => setForm((prev) => ({ ...prev, thesisId: event.target.value }))}>
                    <option value="">None</option>
                    {theses.slice(0, 40).map((thesis) => (
                      <option key={thesis.thesis_id} value={thesis.thesis_id}>
                        {String(thesis.title || thesis.thesis_id).slice(0, 48)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ops-field">
                  <span>Reason / Notes</span>
                  <input className="ops-input" type="text" value={form.reason} onChange={(event) => setForm((prev) => ({ ...prev, reason: event.target.value }))} />
                </label>
              </div>

              <label className="ops-check">
                <input type="checkbox" checked={form.override} onChange={(event) => setForm((prev) => ({ ...prev, override: event.target.checked }))} />
                <span>Override approval threshold if required</span>
              </label>

              <div className="ops-button-row">
                <button type="button" className="ops-button secondary" disabled={busy === 'validate'} onClick={handleValidate}>
                  Run risk check
                </button>
                <button type="submit" className="ops-button" disabled={busy === 'submit'}>
                  {validation?.requires_override || form.override ? 'Override & Submit' : 'Submit Order'}
                </button>
              </div>
            </form>

            {validation ? (
              <>
                <div className="ops-kv-grid">
                  <div className="ops-kv"><span className="ops-kv-label">Market Price</span><strong className="ops-kv-value">{currency(validation.market_price, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Notional</span><strong className="ops-kv-value">{currency(validation.notional_usd, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Cash After</span><strong className="ops-kv-value">{currency(validation.risk_checks?.cash_after_usd, 2)}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Sector</span><strong className="ops-kv-value">{validation.risk_checks?.sector || 'Other'}</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Sector After</span><strong className="ops-kv-value">{Number(validation.risk_checks?.sector_concentration_pct_after || 0).toFixed(2)}%</strong></div>
                  <div className="ops-kv"><span className="ops-kv-label">Override</span><strong className="ops-kv-value">{validation.requires_override ? 'Required' : 'Not required'}</strong></div>
                </div>

                <div className="ops-task-list">
                  {(validation.warnings || []).map((item) => (
                    <article key={item} className="ops-task-row">
                      <div className="ops-task-head">
                        <strong>Warning</strong>
                      </div>
                      <div className="ops-task-meta">
                        <span>{item}</span>
                      </div>
                    </article>
                  ))}
                  {(validation.errors || []).map((item) => (
                    <article key={item} className="ops-task-row">
                      <div className="ops-task-head">
                        <strong className="ops-negative">Blocker</strong>
                      </div>
                      <div className="ops-task-meta">
                        <span>{item}</span>
                      </div>
                    </article>
                  ))}
                  {!validation.warnings?.length && !validation.errors?.length ? (
                    <div className="ops-empty">No policy warnings. Manual ticket is clear to submit.</div>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="ops-empty">Run the risk check to preview notional, reserve, concentration, and correlation proxies.</div>
            )}
          </div>
        </section>

        <section className="ops-panel">
          <div className="ops-panel-header">
            <div>
              <p className="ops-panel-eyebrow">Execution Settings</p>
              <h2 className="ops-panel-title">Broker config and routing priority</h2>
              <p className="ops-panel-description">Current paper venue assumptions plus the desk-level execution preference.</p>
            </div>
          </div>
          <div className="ops-panel-body">
            <div className="ops-kv-grid">
              <div className="ops-kv"><span className="ops-kv-label">Broker</span><strong className="ops-kv-value">{brokerConfig?.broker || 'Paper broker'}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Status</span><strong className="ops-kv-value">{brokerConfig?.status || 'ready'}</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Commission</span><strong className="ops-kv-value">{Number(brokerConfig?.commission_bps || 0).toFixed(2)} bps</strong></div>
              <div className="ops-kv"><span className="ops-kv-label">Slippage Model</span><strong className="ops-kv-value">{Number(brokerConfig?.slippage_bps || 0).toFixed(2)} bps</strong></div>
            </div>
            <p className="ops-note">{brokerConfig?.slippage_model || 'Single-venue paper execution model.'}</p>

            <div className="ops-form-grid">
              <label className="ops-field">
                <span>Execution Priority</span>
                <select className="ops-input" value={priorityForm} onChange={(event) => setPriorityForm(event.target.value)}>
                  <option value="SPEED">Speed</option>
                  <option value="QUALITY">Quality</option>
                  <option value="COST">Cost</option>
                </select>
              </label>
            </div>
            <div className="ops-button-row compact">
              <button type="button" className="ops-button" disabled={busy === 'priority'} onClick={handlePrioritySave}>
                Save Priority
              </button>
            </div>

            <div className="ops-mini-list">
              <div className="ops-mini-row">
                <div><strong>Settlement</strong></div>
                <div className="ops-mini-value"><strong>{brokerConfig?.settlement || 'T+2'}</strong></div>
              </div>
              <div className="ops-mini-row">
                <div><strong>Routing</strong></div>
                <div className="ops-mini-value"><strong>{brokerConfig?.routing || 'single_venue_simulation'}</strong></div>
              </div>
              <div className="ops-mini-row">
                <div><strong>Last update</strong></div>
                <div className="ops-mini-value"><strong>{shortDateTime(executionPriority?.updated_at || brokerConfig?.updated_at)}</strong></div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="ops-panel">
        <div className="ops-panel-header">
          <div>
            <p className="ops-panel-eyebrow">Order Tape</p>
            <h2 className="ops-panel-title">Historical fills</h2>
            <p className="ops-panel-description">Recent fill tape with price, venue, and slippage history.</p>
          </div>
        </div>
        <div className="ops-panel-body">
          {tapeRows.length ? (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Order</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>Venue</th>
                    <th>Slippage</th>
                  </tr>
                </thead>
                <tbody>
                  {tapeRows.slice(0, 18).map((row) => (
                    <tr key={`${row.order_id}-${row.timestamp}`}>
                      <td>{shortDateTime(row.timestamp)}</td>
                      <td className="ops-symbol-cell">{row.order_id}</td>
                      <td>{row.symbol}</td>
                      <td>{row.side}</td>
                      <td>{Number(row.quantity || 0).toFixed(2)}</td>
                      <td>{currency(row.price, 2)}</td>
                      <td>{row.venue}</td>
                      <td className={slippageTone(row.slippage_bps)}>{percentBps(row.slippage_bps)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ops-empty">No fill tape available.</div>
          )}
        </div>
      </section>
    </>
  );
}
