import React, { useEffect, useMemo, useRef, useState } from "react";
import { adminAPI } from "../../api/adminAPI";

const GRAPH_PREFS_KEY = "admin.graph.prefs.v1";

const NODE_LAYOUT = [
  { id: "ceo", label: "CEO", role: "ceo", x: 50, y: 10, group: "control" },
  { id: "openclaw", label: "OpenClaw", role: "openclaw_orchestrator", x: 50, y: 24, group: "control" },
  { id: "research_director", label: "Research Director", role: "research_director", x: 20, y: 40, group: "research" },
  { id: "fund_manager", label: "Fund Manager", role: "fund_manager", x: 50, y: 40, group: "execution" },
  { id: "risk_auditor", label: "Risk Auditor", role: "risk_auditor", x: 80, y: 40, group: "execution" },
  { id: "technical_analyst", label: "Technical", role: "technical_analyst", x: 8, y: 60, group: "research" },
  { id: "fundamental_analyst", label: "Fundamental", role: "fundamental_analyst", x: 20, y: 60, group: "research" },
  { id: "sentiment_analyst", label: "Sentiment", role: "sentiment_analyst", x: 32, y: 60, group: "research" },
  { id: "ml_timeseries_analyst", label: "ML", role: "ml_timeseries_analyst", x: 44, y: 60, group: "research" },
  { id: "insight_researcher", label: "Insight", role: "insight_researcher", x: 56, y: 60, group: "research" },
  { id: "hedge_fund_researcher", label: "Hedge Fund", role: "hedge_fund_researcher", x: 68, y: 60, group: "research" },
  { id: "trader", label: "Trader", role: "trader", x: 50, y: 80, group: "execution" },
  { id: "blog_writer", label: "Blog Writer", role: "blog_writer", x: 80, y: 80, group: "execution" },
];

const EDGES = [
  ["ceo", "openclaw"],
  ["openclaw", "research_director"],
  ["openclaw", "fund_manager"],
  ["openclaw", "risk_auditor"],
  ["research_director", "technical_analyst"],
  ["research_director", "fundamental_analyst"],
  ["research_director", "sentiment_analyst"],
  ["research_director", "ml_timeseries_analyst"],
  ["research_director", "insight_researcher"],
  ["research_director", "hedge_fund_researcher"],
  ["technical_analyst", "fund_manager"],
  ["fundamental_analyst", "fund_manager"],
  ["sentiment_analyst", "fund_manager"],
  ["ml_timeseries_analyst", "fund_manager"],
  ["insight_researcher", "fund_manager"],
  ["hedge_fund_researcher", "fund_manager"],
  ["fund_manager", "risk_auditor"],
  ["risk_auditor", "trader"],
  ["fund_manager", "blog_writer"],
];

const ENTITY_NODES = [
  { id: "decision", label: "Decision", x: 22, y: 92 },
  { id: "intent", label: "Intent", x: 38, y: 92 },
  { id: "order", label: "Order", x: 54, y: 92 },
  { id: "position", label: "Position", x: 70, y: 92 },
  { id: "blog_post", label: "Blog", x: 86, y: 92 },
];

const ENTITY_EDGES = [
  ["fund_manager", "decision"],
  ["decision", "intent"],
  ["intent", "order"],
  ["order", "position"],
  ["fund_manager", "blog_post"],
  ["blog_writer", "blog_post"],
];

function roleStatus(worker) {
  if (!worker) return "idle";
  if (worker.last_error) return "error";
  if (worker.running) return "running";
  return "idle";
}

export default function AgentGraphCanvas({ onRefresh }) {
  const [workers, setWorkers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [pendingDecisions, setPendingDecisions] = useState([]);
  const [knowledgeEvents, setKnowledgeEvents] = useState([]);
  const [selectedRole, setSelectedRole] = useState("");
  const [hoveredRole, setHoveredRole] = useState("");
  const [laneFilter, setLaneFilter] = useState(() => {
    try {
      const raw = localStorage.getItem(GRAPH_PREFS_KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      return parsed?.laneFilter || "all";
    } catch {
      return "all";
    }
  });
  const [timelineIndex, setTimelineIndex] = useState(0);
  const [timelinePlaying, setTimelinePlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [workersPayload, tasksPayload, decisionsPayload, eventsPayload] = await Promise.all([
          adminAPI.getFundWorkersStatus(),
          adminAPI.getFundActiveTasks(),
          adminAPI.getFundPendingDecisions(),
          adminAPI.getFundKnowledgeEvents(30, "development"),
        ]);
        if (!mounted) return;
        setWorkers(Array.isArray(workersPayload?.workers) ? workersPayload.workers : []);
        setTasks(adminAPI.normalizeArray(tasksPayload, "tasks"));
        setPendingDecisions(Array.isArray(decisionsPayload) ? decisionsPayload : []);
        setKnowledgeEvents(adminAPI.normalizeArray(eventsPayload, "events"));
      } catch (err) {
        console.error("Failed to load graph data", err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    const id = setInterval(load, 6000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const byRole = useMemo(() => new Map(workers.map((w) => [w.role, w])), [workers]);

  useEffect(() => {
    try {
      localStorage.setItem(
        GRAPH_PREFS_KEY,
        JSON.stringify({
          laneFilter,
        })
      );
    } catch {
      // noop if localStorage is unavailable
    }
  }, [laneFilter]);

  const activeTaskByRole = useMemo(() => {
    const map = new Map();
    tasks.forEach((task) => {
      const role = String(task.role || "");
      if (!role) return;
      map.set(role, (map.get(role) || 0) + 1);
    });
    return map;
  }, [tasks]);

  const selectedTasks = useMemo(() => {
    if (!selectedRole) return [];
    return tasks.filter((task) => String(task.role || "") === selectedRole).slice(0, 8);
  }, [selectedRole, tasks]);

  const normalizedEvents = useMemo(() => {
    const out = [...knowledgeEvents]
      .map((evt, idx) => {
        const rawTs = evt.timestamp || evt.ts || evt.created_at || evt.time || "";
        const ms = rawTs ? Date.parse(rawTs) : NaN;
        return {
          ...evt,
          _eventKey: evt.event_id || evt.id || `${rawTs}-${idx}`,
          _eventMs: Number.isFinite(ms) ? ms : 0,
        };
      })
      .sort((a, b) => a._eventMs - b._eventMs);
    return out;
  }, [knowledgeEvents]);

  useEffect(() => {
    if (!normalizedEvents.length) {
      setTimelineIndex(0);
      return;
    }
    setTimelineIndex((prev) => {
      const max = normalizedEvents.length - 1;
      return prev > max ? max : prev;
    });
  }, [normalizedEvents]);

  useEffect(() => {
    if (!timelinePlaying || normalizedEvents.length <= 1) return;
    const max = normalizedEvents.length - 1;
    const id = setInterval(() => {
      setTimelineIndex((prev) => {
        if (prev >= max) {
          setTimelinePlaying(false);
          return max;
        }
        return prev + 1;
      });
    }, 700);
    return () => clearInterval(id);
  }, [timelinePlaying, normalizedEvents]);

  const visibleEvents = useMemo(() => {
    if (!normalizedEvents.length) return [];
    const safeIdx = Math.min(Math.max(timelineIndex, 0), normalizedEvents.length - 1);
    return normalizedEvents.slice(0, safeIdx + 1);
  }, [normalizedEvents, timelineIndex]);

  const liveFlow = useMemo(() => {
    const eventTypes = new Set(
      visibleEvents.map((evt) => String(evt.event_type || evt.type || "").toLowerCase())
    );
    return {
      decision: pendingDecisions.length > 0 || eventTypes.has("decision.created") || eventTypes.has("decision.approved"),
      intent: eventTypes.has("intent.created") || eventTypes.has("execution.intent"),
      order: eventTypes.has("order.submitted") || eventTypes.has("order.filled") || eventTypes.has("trade.executed"),
      position: eventTypes.has("position.updated") || eventTypes.has("portfolio.updated"),
      blog: eventTypes.has("blog.created") || eventTypes.has("blog.published"),
    };
  }, [visibleEvents, pendingDecisions]);

  const rolesInOrder = NODE_LAYOUT.map((n) => n.role);
  const selectedIndex = rolesInOrder.indexOf(selectedRole);

  const selectPrevRole = () => {
    if (rolesInOrder.length === 0) return;
    const next = selectedIndex <= 0 ? rolesInOrder[rolesInOrder.length - 1] : rolesInOrder[selectedIndex - 1];
    setSelectedRole(next);
  };

  const selectNextRole = () => {
    if (rolesInOrder.length === 0) return;
    const next = selectedIndex < 0 || selectedIndex >= rolesInOrder.length - 1 ? rolesInOrder[0] : rolesInOrder[selectedIndex + 1];
    setSelectedRole(next);
  };

  const selectedTaskPreview = selectedTasks[0] || null;
  const hoveredWorker = hoveredRole ? byRole.get(hoveredRole) : null;
  const timelineCurrent = normalizedEvents.length ? normalizedEvents[timelineIndex] : null;

  useEffect(() => {
    const onKeyDown = (event) => {
      const target = event.target;
      const tag = String(target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) return;
      const key = String(event.key || "").toLowerCase();
      if (key === "g") {
        event.preventDefault();
        containerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if (key === "r") {
        event.preventDefault();
        if (typeof onRefresh === "function") onRefresh();
      }
      if (key === "a") {
        event.preventDefault();
        selectPrevRole();
      }
      if (key === "d") {
        event.preventDefault();
        selectNextRole();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onRefresh, selectedIndex, rolesInOrder.length]);

  const shouldShowNode = (node) => {
    if (laneFilter === "all") return true;
    if (laneFilter === "entity") return false;
    return node.group === laneFilter;
  };

  return (
    <section className="agent-graph-canvas" ref={containerRef}>
      <div className="agent-graph-header">
        <h3>Live Orchestration Map</h3>
        <p>Click any role to inspect active workload and runtime health overlays. Shortcuts: G focus, R refresh, A/D navigate roles.</p>
        <div className="agent-graph-legend">
          <button className={`agent-graph-legend-btn ${laneFilter === "all" ? "active" : ""}`} onClick={() => setLaneFilter("all")}>All</button>
          <button className={`agent-graph-legend-btn ${laneFilter === "control" ? "active" : ""}`} onClick={() => setLaneFilter("control")}>Control</button>
          <button className={`agent-graph-legend-btn ${laneFilter === "research" ? "active" : ""}`} onClick={() => setLaneFilter("research")}>Research</button>
          <button className={`agent-graph-legend-btn ${laneFilter === "execution" ? "active" : ""}`} onClick={() => setLaneFilter("execution")}>Execution</button>
          <button className={`agent-graph-legend-btn ${laneFilter === "entity" ? "active" : ""}`} onClick={() => setLaneFilter("entity")}>Entity Flow</button>
        </div>
        <div className="agent-graph-timeline-controls">
          <button
            className="agent-graph-nav-btn"
            onClick={() => {
              if (timelineIndex >= normalizedEvents.length - 1) {
                setTimelineIndex(0);
              }
              setTimelinePlaying((prev) => !prev);
            }}
            disabled={normalizedEvents.length <= 1}
            aria-label="Play timeline"
          >
            {timelinePlaying ? "Pause Timeline" : "Play Timeline"}
          </button>
          <input
            className="agent-graph-timeline-range"
            type="range"
            min={0}
            max={Math.max(normalizedEvents.length - 1, 0)}
            value={Math.min(timelineIndex, Math.max(normalizedEvents.length - 1, 0))}
            onChange={(e) => {
              setTimelinePlaying(false);
              setTimelineIndex(Number(e.target.value) || 0);
            }}
            aria-label="Scrub knowledge-event timeline"
          />
          <span className="agent-graph-timeline-meta">
            {normalizedEvents.length
              ? `${timelineIndex + 1}/${normalizedEvents.length} events`
              : "No events"}
          </span>
        </div>
      </div>

      <div className="agent-graph-body">
        {loading ? (
          <div className="agent-graph-skeleton" aria-hidden="true">
            <div className="skeleton-block tall" />
            <div className="skeleton-block" />
            <div className="skeleton-block" />
          </div>
        ) : null}
        <svg viewBox="0 0 100 100" className="agent-graph-svg" role="img" aria-label="Agent orchestration graph">
          {EDGES.map(([from, to]) => {
            const a = NODE_LAYOUT.find((n) => n.id === from);
            const b = NODE_LAYOUT.find((n) => n.id === to);
            if (!a || !b) return null;
            if (!shouldShowNode(a) || !shouldShowNode(b)) return null;
            const highlighted = selectedRole && (a.role === selectedRole || b.role === selectedRole);
            return (
              <line
                key={`${from}-${to}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                className={`agent-graph-edge ${highlighted ? "highlight" : ""}`}
              />
            );
          })}

          {NODE_LAYOUT.map((node) => {
            if (!shouldShowNode(node)) return null;
            const worker = byRole.get(node.role);
            const status = roleStatus(worker);
            const taskCount = activeTaskByRole.get(node.role) || 0;
            const isSelected = selectedRole === node.role;
            return (
              <g
                key={node.id}
                className={`agent-graph-node ${status} ${isSelected ? "selected" : ""}`}
                onClick={() => setSelectedRole((prev) => (prev === node.role ? "" : node.role))}
                onMouseEnter={() => setHoveredRole(node.role)}
                onMouseLeave={() => setHoveredRole("")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedRole((prev) => (prev === node.role ? "" : node.role));
                  }
                }}
              >
                <circle cx={node.x} cy={node.y} r={status === "running" ? 3.7 : 3.2} />
                <text x={node.x} y={node.y + 7} textAnchor="middle" className="agent-graph-label">{node.label}</text>
                {taskCount > 0 && (
                  <text x={node.x} y={node.y - 5} textAnchor="middle" className="agent-graph-task-count">{taskCount}</text>
                )}
              </g>
            );
          })}

          {ENTITY_EDGES.map(([from, to]) => {
            if (laneFilter !== "all" && laneFilter !== "entity") return null;
            const a = NODE_LAYOUT.find((n) => n.id === from) || ENTITY_NODES.find((n) => n.id === from);
            const b = NODE_LAYOUT.find((n) => n.id === to) || ENTITY_NODES.find((n) => n.id === to);
            if (!a || !b) return null;
            const isLive =
              (to === "decision" && liveFlow.decision) ||
              (to === "intent" && liveFlow.intent) ||
              (to === "order" && liveFlow.order) ||
              (to === "position" && liveFlow.position) ||
              (to === "blog_post" && liveFlow.blog);
            return (
              <line
                key={`${from}-${to}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                className={`agent-graph-edge entity ${isLive ? "live" : ""}`}
              />
            );
          })}

          {ENTITY_NODES.map((node) => {
            if (laneFilter !== "all" && laneFilter !== "entity") return null;
            const active =
              (node.id === "decision" && liveFlow.decision) ||
              (node.id === "intent" && liveFlow.intent) ||
              (node.id === "order" && liveFlow.order) ||
              (node.id === "position" && liveFlow.position) ||
              (node.id === "blog_post" && liveFlow.blog);
            return (
              <g key={node.id} className={`agent-graph-entity ${active ? "active" : ""}`}>
                <rect x={node.x - 4} y={node.y - 2.7} rx={1.6} ry={1.6} width={8} height={4.8} />
                <text x={node.x} y={node.y + 5.2} textAnchor="middle" className="agent-graph-entity-label">
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        <aside className="agent-graph-sidepanel">
          <h4>{selectedRole ? `${selectedRole.replace(/_/g, " ")} Tasks` : "Role Inspector"}</h4>
          {hoveredRole && (
            <div className="agent-graph-hovercard" role="status" aria-live="polite">
              <strong>{hoveredRole.replace(/_/g, " ")}</strong>
              <span>Status: {roleStatus(hoveredWorker)}</span>
              <span>Running: {hoveredWorker?.running ? "yes" : "no"}</span>
              {hoveredWorker?.last_error ? <span>Last error: {String(hoveredWorker.last_error).slice(0, 80)}</span> : null}
            </div>
          )}
          <div className="agent-graph-nav-row">
            <button className="agent-graph-nav-btn" onClick={selectPrevRole} aria-label="Select previous role">Prev Role</button>
            <button className="agent-graph-nav-btn" onClick={selectNextRole} aria-label="Select next role">Next Role</button>
          </div>
          {!selectedRole ? (
            <p>Select a node to inspect active tasks and health for that role.</p>
          ) : selectedTasks.length === 0 ? (
            <p>No active tasks for this role right now.</p>
          ) : (
            <div className="agent-graph-task-list">
              {selectedTasks.map((task) => (
                <div key={task.task_id} className="agent-graph-task-item">
                  <strong>{task.task_type || task.kind || "task"}</strong>
                  <span>Status: {task.status || "unknown"}</span>
                  <span>Priority: {task.priority ?? "n/a"}</span>
                </div>
              ))}
            </div>
          )}
          {selectedRole && (
            <div className="agent-graph-deeplinks">
              <a className="agent-graph-link" href="/admin#audit">Open Audit Tab</a>
              <a className="agent-graph-link" href="/admin#decisions">Open Decisions Tab</a>
              {selectedTaskPreview?.run_id ? (
                <a className="agent-graph-link" href={`/audit/${encodeURIComponent(selectedTaskPreview.run_id)}`}>
                  Open Run Timeline
                </a>
              ) : null}
            </div>
          )}
          {timelineCurrent ? (
            <div className="agent-graph-timeline-event">
              <h5>Timeline Cursor</h5>
              <span>{timelineCurrent.timestamp ? new Date(timelineCurrent.timestamp).toLocaleString() : "no timestamp"}</span>
              <span>{timelineCurrent.event_type || timelineCurrent.type || "event"}</span>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
