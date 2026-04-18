import React, { useEffect, useMemo, useState } from "react";
import {
  getFundActiveTasks,
  getFundBlockedTrades,
  getFundKnowledgeStats,
  getFundPendingDecisions,
  getFundSleeveBudgets,
  getFundWorkerStatus,
  kickFundAutopilot,
} from "../api";

function StatCard({ label, value }) {
  return (
    <div
      style={{
        background: "var(--bg1)",
        border: "1px solid var(--line)",
        borderRadius: 8,
        padding: "10px 12px",
        minWidth: 150,
      }}
    >
      <div style={{ fontFamily: "var(--f-data)", fontSize: 10, color: "var(--txt3)", letterSpacing: "0.08em" }}>{label}</div>
      <div style={{ fontFamily: "var(--f-data)", fontSize: 20, color: "var(--txt)", marginTop: 4 }}>{value}</div>
    </div>
  );
}

function CompactList({ title, items, renderItem }) {
  return (
    <section style={{ background: "var(--bg1)", border: "1px solid var(--line)", borderRadius: 8, padding: 12 }}>
      <div style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt2)", marginBottom: 8 }}>{title}</div>
      {items.length === 0 ? (
        <div style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt3)" }}>No items</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{items.map(renderItem)}</div>
      )}
    </section>
  );
}

export default function OpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [workers, setWorkers] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [pending, setPending] = useState([]);
  const [blocked, setBlocked] = useState([]);
  const [knowledge, setKnowledge] = useState(null);
  const [budgets, setBudgets] = useState([]);

  async function refresh() {
    try {
      setError("");
      const [workerRes, taskRes, pendingRes, blockedRes, knowledgeRes, budgetRes] = await Promise.all([
        getFundWorkerStatus(),
        getFundActiveTasks(),
        getFundPendingDecisions(),
        getFundBlockedTrades(20),
        getFundKnowledgeStats(),
        getFundSleeveBudgets(),
      ]);
      setWorkers(workerRes);
      setTasks(taskRes);
      setPending(pendingRes);
      setBlocked(blockedRes);
      setKnowledge(knowledgeRes);
      setBudgets(budgetRes?.runs || []);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  const workerCounts = useMemo(() => {
    const rows = workers?.workers || [];
    return {
      completed: rows.reduce((sum, row) => sum + Number(row.completed_count || 0), 0),
      blocked: rows.reduce((sum, row) => sum + Number(row.blocked_count || 0), 0),
      failed: rows.reduce((sum, row) => sum + Number(row.failed_count || 0), 0),
    };
  }, [workers]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn btn-amber" onClick={() => kickFundAutopilot().then(refresh)} style={{ padding: "6px 12px" }}>
          Kick Autopilot
        </button>
        <button className="btn btn-tab on" onClick={refresh} style={{ padding: "6px 12px" }}>
          Refresh Ops
        </button>
        {error ? <span style={{ color: "var(--red)", fontSize: 11 }}>{error}</span> : null}
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <StatCard label="Active Tasks" value={tasks.length} />
        <StatCard label="Pending Decisions" value={pending.length} />
        <StatCard label="Blocked Trades" value={blocked.length} />
        <StatCard label="KG Events" value={knowledge?.event_count || 0} />
        <StatCard label="Workers Completed" value={workerCounts.completed} />
        <StatCard label="Workers Failed" value={workerCounts.failed} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
        <CompactList
          title="Active Agent Tasks"
          items={tasks.slice(0, 8)}
          renderItem={(item) => (
            <div key={item.task_id} style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt2)" }}>
              <strong>{item.role}</strong> · {item.status} · {item.run_id}
            </div>
          )}
        />

        <CompactList
          title="Blocked Trades (Recent)"
          items={blocked.slice(-8).reverse()}
          renderItem={(item, idx) => (
            <div key={`${item.event_id || idx}`} style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt2)" }}>
              {item.event_ts || item.timestamp || "n/a"} · {item.payload?.decision_id || item.decision_id || "unknown"} ·{" "}
              {(item.payload?.blocked_reasons || item.payload?.reasons || []).join(", ") || "blocked"}
            </div>
          )}
        />

        <CompactList
          title="Sleeve Budgets"
          items={budgets.slice(0, 3)}
          renderItem={(run) => (
            <div key={run.run_id} style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt2)" }}>
              <div style={{ color: "var(--amber)", marginBottom: 4 }}>{run.run_id}</div>
              {Object.entries(run.sleeves || {}).map(([name, row]) => (
                <div key={name}>
                  {name}: ${row.remaining_usd?.toFixed ? row.remaining_usd.toFixed(2) : row.remaining_usd} remaining
                </div>
              ))}
            </div>
          )}
        />
      </div>

      {loading ? <div style={{ fontFamily: "var(--f-data)", fontSize: 11, color: "var(--txt3)" }}>Loading operations data...</div> : null}
    </div>
  );
}
