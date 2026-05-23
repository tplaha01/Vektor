import React, { useEffect, useMemo, useState } from "react";
import { adminAPI } from "../api/adminAPI";

function pct(value, digits = 2) {
  const num = Number(value || 0);
  return `${num.toFixed(digits)}%`;
}

function usd(value) {
  const num = Number(value || 0);
  return `${num >= 0 ? "+" : "-"}$${Math.abs(num).toFixed(2)}`;
}

export default function StrategyDashboard() {
  const [performance, setPerformance] = useState(null);
  const [effectiveness, setEffectiveness] = useState(null);
  const [reviews, setReviews] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [perfPayload, mlPayload, reviewPayload] = await Promise.all([
          adminAPI.getPerformanceSummary(),
          adminAPI.getCeoMlEffectiveness(),
          adminAPI.getLatestPostTradeReviews(20),
        ]);
        if (cancelled) return;
        setPerformance(perfPayload || null);
        setEffectiveness(mlPayload || null);
        setReviews(Array.isArray(reviewPayload?.items) ? reviewPayload.items : []);
      } catch {
        // Keep last good payload.
      }
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const track = performance?.track_record || {};
  const latest = performance?.latest_snapshot || {};
  const rows = Array.isArray(effectiveness?.positions_with_ml_context) ? effectiveness.positions_with_ml_context : [];
  const confidenceBuckets = Array.isArray(effectiveness?.confidence_buckets) ? effectiveness.confidence_buckets : [];

  const aggregate = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        const pnl = Number(row?.unrealized_pnl || 0);
        if (pnl > 0) acc.wins += 1;
        if (pnl < 0) acc.losses += 1;
        return acc;
      },
      { wins: 0, losses: 0 },
    );
  }, [rows]);

  if (!performance && !effectiveness) {
    return <div style={{ padding: 20, color: "var(--txt3)", fontFamily: "var(--f-data)", fontSize: 10 }}>LOADING...</div>;
  }

  const stats = [
    { l: "Return", v: pct(track.total_return_pct), c: Number(track.total_return_pct || 0) >= 0 ? "var(--green)" : "var(--red)" },
    { l: "Alpha", v: pct(track.alpha_vs_primary_benchmark_pct), c: Number(track.alpha_vs_primary_benchmark_pct || 0) >= 0 ? "var(--green)" : "var(--red)" },
    { l: "Sharpe", v: Number(track.sharpe_ratio || 0).toFixed(2) },
    { l: "Max DD", v: pct(track.max_drawdown_pct), c: "var(--red)" },
    { l: "Equity", v: `$${Number(latest.equity || 0).toFixed(2)}` },
    { l: "ML Rows", v: rows.length },
    { l: "Winners", v: aggregate.wins, c: "var(--green)" },
    { l: "Losers", v: aggregate.losses, c: "var(--red)" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="panel panel-pad">
        <div className="label" style={{ marginBottom: 12 }}>Core Engine Performance</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }} className="stat-grid-8">
          {stats.map(({ l, v, c }) => (
            <div key={l} style={{ background: "var(--bg3)", border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "9px 11px" }}>
              <div className="label" style={{ marginBottom: 4, fontSize: 8 }}>{l}</div>
              <div style={{ fontFamily: "var(--f-data)", fontSize: 14, fontWeight: 600, color: c || "var(--txt)" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel panel-pad">
        <div className="label" style={{ marginBottom: 10 }}>Open Positions with ML Context</div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>SYMBOL</th>
              <th style={{ textAlign: "left" }}>ASSET</th>
              <th style={{ textAlign: "left" }}>STRATEGY</th>
              <th>SCORE</th>
              <th>CONF</th>
              <th>PNL</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length ? (
              <tr><td colSpan={6} style={{ padding: "20px 0", textAlign: "center", color: "var(--txt3)" }}>No core-engine tagged positions</td></tr>
            ) : rows.map((row) => (
              <tr key={`${row.symbol}-${row.strategy_family}`}>
                <td style={{ fontWeight: 600 }}>{row.symbol}</td>
                <td>{row.asset_class}</td>
                <td>{row.strategy_family}</td>
                <td>{Number(row.score || 0).toFixed(3)}</td>
                <td>{Number(row.confidence || 0).toFixed(3)}</td>
                <td style={{ color: Number(row.unrealized_pnl || 0) >= 0 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                  {usd(row.unrealized_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel panel-pad">
        <div className="label" style={{ marginBottom: 10 }}>Confidence Buckets</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
          {confidenceBuckets.map((bucket) => (
            <div key={bucket.confidence_bucket} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "9px 11px" }}>
              <div className="label">{bucket.confidence_bucket}</div>
              <div style={{ fontFamily: "var(--f-data)", fontSize: 14, fontWeight: 600 }}>{bucket.count} rows</div>
              <div style={{ color: Number(bucket.unrealized_pnl || 0) >= 0 ? "var(--green)" : "var(--red)", fontFamily: "var(--f-data)", fontSize: 11 }}>
                {usd(bucket.unrealized_pnl)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel panel-pad">
        <div className="label" style={{ marginBottom: 10 }}>Recent Post-Trade Reviews</div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>TIME</th>
              <th style={{ textAlign: "left" }}>SYMBOL</th>
              <th style={{ textAlign: "left" }}>OUTCOME</th>
              <th style={{ textAlign: "left" }}>VERDICT</th>
            </tr>
          </thead>
          <tbody>
            {!reviews.length ? (
              <tr><td colSpan={4} style={{ padding: "20px 0", textAlign: "center", color: "var(--txt3)" }}>No post-trade reviews yet</td></tr>
            ) : reviews.slice(0, 12).map((item) => (
              <tr key={item.review_id}>
                <td style={{ color: "var(--txt3)" }}>{new Date(item.reviewed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                <td style={{ fontWeight: 600 }}>{item.symbol || "N/A"}</td>
                <td>{String(item.outcome || "unknown").replace(/_/g, " ")}</td>
                <td>{item.verdict || "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
