import React, { useEffect, useMemo, useState } from "react";
import { adminAPI } from "../api/adminAPI";
import { getAnalytics } from "../api";
import WorkspaceNav from "../components/common/WorkspaceNav";

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function percent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

export default function PublicPnlPage() {
  const [analytics, setAnalytics] = useState(null);
  const [positions, setPositions] = useState([]);
  const [workersStatus, setWorkersStatus] = useState(null);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    let canceled = false;
    const fetchAll = async () => {
      try {
        setError("");
        const [metricsPayload, positionsPayload, workersPayload] = await Promise.all([
          getAnalytics(),
          adminAPI.getPaperPositions(),
          adminAPI.getFundWorkersStatus(),
        ]);
        if (canceled) return;
        setAnalytics(metricsPayload || null);
        setPositions(Array.isArray(positionsPayload) ? positionsPayload : []);
        setWorkersStatus(workersPayload || null);
        setLastUpdate(new Date());
      } catch (e) {
        if (!canceled) setError(String(e?.message || e));
      }
    };

    fetchAll();
    const id = setInterval(fetchAll, 15000);
    return () => {
      canceled = true;
      clearInterval(id);
    };
  }, []);

  const totals = useMemo(() => {
    const rows = positions.filter((p) => Number(p.qty || 0) > 0);
    const equity = rows.reduce((sum, row) => sum + Number(row.market_value || 0), 0);
    const unrealized = rows.reduce((sum, row) => sum + Number(row.unrealized_pnl || 0), 0);
    const grossExposure = rows.reduce((sum, row) => sum + Math.abs(Number(row.market_value || 0)), 0);
    const winners = [...rows].sort((a, b) => Number(b.unrealized_pnl || 0) - Number(a.unrealized_pnl || 0));
    return {
      count: rows.length,
      equity,
      unrealized,
      grossExposure,
      biggestWinner: winners[0] || null,
      biggestLoser: winners[winners.length - 1] || null,
    };
  }, [positions]);

  const metrics = analytics?.metrics || analytics || {};
  const lastScout = workersStatus?.autopilot?.last_scout || null;
  const signalPacks = Array.isArray(workersStatus?.signal_packs) ? workersStatus.signal_packs : [];

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg0)", color: "var(--txt)" }}>
      <main style={{ maxWidth: 1320, margin: "0 auto", padding: 20, display: "grid", gap: 16 }}>
        <WorkspaceNav
          eyebrow="Vektor Public Board"
          title="Live Paper PnL"
          summary="Public-facing portfolio posture sourced from the paper broker, scout runtime, and live signal packs."
          meta={
            <>
              <div className="label">Source: Alpaca paper portfolio</div>
              <div style={{ color: "var(--txt2)", fontSize: 12 }}>
                Last refresh {lastUpdate.toLocaleTimeString()}
              </div>
            </>
          }
        />
        {error ? (
          <section className="panel panel-pad" style={{ borderColor: "rgba(224,82,82,0.4)", background: "rgba(224,82,82,0.08)" }}>
            Data feed warning: {error}
          </section>
        ) : null}

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
          <div className="panel panel-pad"><div className="label">Total Equity</div><div className="big-num">{currency(metrics.total_equity || totals.equity)}</div></div>
          <div className="panel panel-pad"><div className="label">Unrealized PnL</div><div className={`big-num ${Number(totals.unrealized) >= 0 ? "c-green" : "c-red"}`}>{currency(totals.unrealized)}</div></div>
          <div className="panel panel-pad"><div className="label">Gross Exposure</div><div className="big-num">{currency(totals.grossExposure)}</div></div>
          <div className="panel panel-pad"><div className="label">Drawdown</div><div className="big-num">{percent(metrics.current_drawdown || 0)}</div></div>
          <div className="panel panel-pad"><div className="label">Open Positions</div><div className="big-num">{totals.count}</div></div>
          <div className="panel panel-pad"><div className="label">Signal Packs</div><div className="big-num">{signalPacks.length}</div></div>
        </section>

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>
          <section className="panel panel-pad">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h2 style={{ fontSize: 18 }}>Current Holdings</h2>
              <div className="label">Auto refresh: 15s</div>
            </div>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Avg</th>
                  <th>Market</th>
                  <th>Value</th>
                  <th>Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {positions.filter((p) => Number(p.qty || 0) > 0).map((row) => (
                  <tr key={row.symbol}>
                    <td>{row.symbol}</td>
                    <td>{Number(row.qty || 0).toFixed(2)}</td>
                    <td>{currency(row.avg_price || 0)}</td>
                    <td>{currency(row.market_price || row.current_price || 0)}</td>
                    <td>{currency(row.market_value || 0)}</td>
                    <td className={Number(row.unrealized_pnl || 0) >= 0 ? "c-green" : "c-red"}>{currency(row.unrealized_pnl || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section style={{ display: "grid", gap: 16 }}>
            <div className="panel panel-pad">
              <h2 style={{ fontSize: 18, marginBottom: 12 }}>Portfolio posture</h2>
              <div style={{ display: "grid", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Best contributor</span><strong>{totals.biggestWinner?.symbol || 'n/a'} · {currency(totals.biggestWinner?.unrealized_pnl)}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Worst contributor</span><strong>{totals.biggestLoser?.symbol || 'n/a'} · {currency(totals.biggestLoser?.unrealized_pnl)}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Realized PnL</span><strong>{currency(metrics.realized_pnl || 0)}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">External flows</span><strong>{currency(metrics.external_capital_flow_usd || 0)}</strong></div>
              </div>
            </div>

            <div className="panel panel-pad">
              <h2 style={{ fontSize: 18, marginBottom: 12 }}>OpenClaw scout</h2>
              <div style={{ display: "grid", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Autopilot</span><strong>{workersStatus?.autopilot?.enabled ? 'Enabled' : 'Manual'}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Cash hold</span><strong>{workersStatus?.autopilot?.allow_cash_hold ? 'Allowed' : 'Disabled'}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Latest scout</span><strong>{lastScout?.selected_symbols?.join(', ') || 'n/a'}</strong></div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span className="label">Data mode</span><strong>{workersStatus?.data_integrity?.data_source_status || 'Unknown'}</strong></div>
              </div>
            </div>
          </section>
        </div>

        <section className="panel panel-pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ fontSize: 18 }}>Latest signal packs</h2>
            <div className="label">Research and execution context used by the admin console</div>
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {signalPacks.length ? signalPacks.map((pack) => (
              <div key={pack.signal_pack_id} style={{ display: "grid", gridTemplateColumns: "180px 1fr 180px", gap: 12, padding: 12, border: "1px solid var(--line)", borderRadius: 10, background: "rgba(255,255,255,0.015)" }}>
                <div>
                  <div className="label">Symbol</div>
                  <strong>{pack.symbol}</strong>
                </div>
                <div>
                  <div className="label">Completed roles</div>
                  <div>{(pack.completed_roles || []).join(', ') || 'none'}</div>
                </div>
                <div>
                  <div className="label">Composite report</div>
                  <strong>{String(pack.composite_report_id || '').slice(0, 12) || 'pending'}</strong>
                </div>
              </div>
            )) : <div className="label">No recent signal packs</div>}
          </div>
        </section>
      </main>
    </div>
  );
}


