import React, { useEffect, useMemo, useState } from "react";
import { getAnalytics, getPositions } from "../api";

function currency(value) {
  const num = Number(value || 0);
  return num.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export default function PublicPnlPage() {
  const [analytics, setAnalytics] = useState(null);
  const [positions, setPositions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let canceled = false;
    const fetchAll = async () => {
      try {
        setError("");
        const [a, p] = await Promise.all([getAnalytics(), getPositions()]);
        if (canceled) return;
        setAnalytics(a || null);
        setPositions(Array.isArray(p) ? p : []);
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
    return { count: rows.length, equity, unrealized };
  }, [positions]);

  const metrics = analytics?.metrics || {};

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg0)", color: "var(--txt)" }}>
      <header style={{ borderBottom: "1px solid var(--line)", background: "var(--bg1)", position: "sticky", top: 0, zIndex: 2 }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img src="/VektorLogo.png" alt="Viktor Logo" style={{ height: '32px' }} />
            <div>
              <div className="label" style={{ marginBottom: 4 }}>Viktor Public Board</div>
              <h1 style={{ fontSize: 24 }}>Live Paper PnL</h1>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="btn btn-tab on" href="/admin">Admin Portal</a>
            <a className="btn btn-tab" href="/research">Research</a>
            <a className="btn btn-tab" href="/blog">Blog</a>
            <a className="btn btn-amber" href="/legacy">Legacy Workspace</a>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1180, margin: "0 auto", padding: 20, display: "grid", gap: 14 }}>
        {error ? (
          <section className="panel panel-pad" style={{ borderColor: "rgba(224,82,82,0.4)", background: "rgba(224,82,82,0.08)" }}>
            Data feed warning: {error}
          </section>
        ) : null}

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
          <div className="panel panel-pad"><div className="label">Total Equity</div><div className="big-num">{currency(metrics.total_equity || totals.equity)}</div></div>
          <div className="panel panel-pad"><div className="label">Unrealized PnL</div><div className={`big-num ${Number(totals.unrealized) >= 0 ? "c-green" : "c-red"}`}>{currency(totals.unrealized)}</div></div>
          <div className="panel panel-pad"><div className="label">Drawdown</div><div className="big-num">{Number(metrics.current_drawdown || 0).toFixed(2)}%</div></div>
          <div className="panel panel-pad"><div className="label">Open Positions</div><div className="big-num">{totals.count}</div></div>
        </section>

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
                <th>Price</th>
                <th>Market Value</th>
                <th>Unrealized PnL</th>
              </tr>
            </thead>
            <tbody>
              {positions.filter((p) => Number(p.qty || 0) > 0).map((row) => (
                <tr key={row.symbol}>
                  <td>{row.symbol}</td>
                  <td>{Number(row.qty || 0).toFixed(2)}</td>
                  <td>{currency(row.current_price || row.avg_price || 0)}</td>
                  <td>{currency(row.market_value || 0)}</td>
                  <td className={Number(row.unrealized_pnl || 0) >= 0 ? "c-green" : "c-red"}>{currency(row.unrealized_pnl || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
