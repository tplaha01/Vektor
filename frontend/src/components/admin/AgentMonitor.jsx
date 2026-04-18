import React, { useState, useEffect, useMemo } from 'react';
import { Cpu, Activity, AlertTriangle, CheckCircle, Clock, Bot, Shield, FileText, Users } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const ANALYST_ROLES = [
  'technical_analyst',
  'fundamental_analyst',
  'sentiment_analyst',
  'ml_timeseries_analyst',
  'insight_researcher',
  'hedge_fund_researcher',
];

const EXECUTION_ROLES = ['fund_manager', 'trader', 'risk_auditor', 'blog_writer'];

const FLOW_NODES = [
  { id: 'ceo', label: 'CEO', task: 'Defines mandate and constraints', level: 0 },
  { id: 'openclaw', label: 'OpenClaw Orchestrator', task: 'Routes commands and task packs', level: 1 },
  { id: 'research', label: 'Research Director', task: 'Coordinates specialist analysts', level: 2 },
  { id: 'analysts', label: 'Analyst Swarm', task: 'Generates source-backed reports', level: 3 },
  { id: 'fund', label: 'Fund Manager', task: 'Builds sleeve-aware decision', level: 4 },
  { id: 'risk', label: 'Risk Auditor', task: 'Enforces policy and guardrails', level: 5 },
  { id: 'trader', label: 'Trader', task: 'Converts approved intent to order', level: 6 },
  { id: 'blog', label: 'Blog Writer', task: 'Publishes explainable narratives', level: 6 },
];

const roleLabel = (role) =>
  String(role || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const statusPriority = {
  error: 4,
  running: 3,
  idle: 2,
  queued: 1,
  stopped: 0,
  unknown: 0,
};

const AgentMonitor = ({ expanded = false }) => {
  const [agents, setAgents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [recentEvents, setRecentEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const [workersPayload, activeTasksPayload, historyPayload] = await Promise.all([
          adminAPI.getFundWorkersStatus(),
          adminAPI.getFundActiveTasks(),
          adminAPI.getFundTaskHistory(24),
        ]);

        const workers = Array.isArray(workersPayload?.workers) ? workersPayload.workers : [];
        const mappedWorkers = workers.map((worker, idx) => {
          const completed = worker.completed_count || 0;
          const failed = worker.failed_count || 0;
          const blocked = worker.blocked_count || 0;
          const total = completed + failed + blocked;
          return {
            agent_id: worker.agent_id || `${worker.role || 'agent'}-${idx}`,
            role: worker.role || 'unknown',
            status: worker.running ? 'running' : worker.started ? 'idle' : 'stopped',
            task_count: total,
            success_rate: total > 0 ? completed / total : 1,
            last_heartbeat: worker.last_heartbeat_at || null,
            last_task_status: worker.last_task_status || null,
            last_task_id: worker.last_task_id || null,
            last_error: worker.last_error || null,
          };
        });

        const activeTasks = adminAPI.normalizeArray(activeTasksPayload, 'tasks');
        const history = adminAPI.normalizeArray(historyPayload, 'history');
        const normalizedHistory = history
          .map((entry, idx) => ({
            task_id: entry.task_id || `hist-${idx}`,
            role: entry.role || entry.agent_id || 'unknown',
            agent_id: entry.agent_id || 'unknown',
            status: entry.status || entry.event || 'unknown',
            ts: entry.ts || entry.created_at || new Date().toISOString(),
            run_id: entry.run_id || null,
            event: entry.event || null,
          }))
          .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

        setAgents(mappedWorkers);
        setTasks(activeTasks);
        setRecentEvents(normalizedHistory.slice(0, 8));
      } catch (err) {
        console.error('Failed to fetch agent data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
    const interval = setInterval(fetchAgents, 5000);
    return () => clearInterval(interval);
  }, []);

  const hierarchy = useMemo(() => {
    const byRole = new Map(agents.map((agent) => [agent.role, agent]));

    const summarize = (roles) => {
      const members = roles
        .map((role) => byRole.get(role))
        .filter(Boolean);

      if (members.length === 0) {
        return {
          status: 'idle',
          task_count: 0,
          success_rate: 1,
          members: 0,
        };
      }

      const status = members
        .map((member) => member.status || 'unknown')
        .sort((a, b) => (statusPriority[b] || 0) - (statusPriority[a] || 0))[0];

      const taskCount = members.reduce((sum, member) => sum + (member.task_count || 0), 0);
      const avgSuccess = members.reduce((sum, member) => sum + (member.success_rate || 0), 0) / members.length;

      return {
        status,
        task_count: taskCount,
        success_rate: avgSuccess,
        members: members.length,
      };
    };

    const allRoles = Array.from(byRole.keys());
    const allSummary = summarize(allRoles);
    const analystSummary = summarize(ANALYST_ROLES);

    const ceo = {
      agent_id: 'ceo-virtual',
      role: 'ceo',
      status: allSummary.status,
      task_count: allSummary.task_count,
      success_rate: allSummary.success_rate,
      members: allSummary.members,
      virtual: true,
    };

    const orchestrator = {
      agent_id: 'openclaw-virtual',
      role: 'openclaw_orchestrator',
      status: allSummary.status,
      task_count: allSummary.task_count,
      success_rate: allSummary.success_rate,
      members: allSummary.members,
      virtual: true,
    };

    const researchDirector = {
      agent_id: 'research-director-virtual',
      role: 'research_director',
      status: analystSummary.status,
      task_count: analystSummary.task_count,
      success_rate: analystSummary.success_rate,
      members: analystSummary.members,
      virtual: true,
    };

    const analysts = ANALYST_ROLES.map((role) => byRole.get(role)).filter(Boolean);
    const execution = EXECUTION_ROLES.map((role) => byRole.get(role)).filter(Boolean);

    return {
      ceo,
      orchestrator,
      researchDirector,
      analysts,
      execution,
    };
  }, [agents]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Activity size={16} className="status-icon running" />;
      case 'idle':
        return <CheckCircle size={16} className="status-icon idle" />;
      case 'error':
        return <AlertTriangle size={16} className="status-icon error" />;
      case 'queued':
        return <Clock size={16} className="status-icon queued" />;
      case 'stopped':
        return <AlertTriangle size={16} className="status-icon error" />;
      default:
        return null;
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'ceo':
      case 'openclaw_orchestrator':
      case 'fund_manager':
        return <Cpu size={16} />;
      case 'trader':
      case 'technical_analyst':
      case 'fundamental_analyst':
      case 'sentiment_analyst':
      case 'ml_timeseries_analyst':
      case 'insight_researcher':
      case 'hedge_fund_researcher':
      case 'research_director':
        return <Bot size={16} />;
      case 'risk_auditor':
        return <Shield size={16} />;
      case 'blog_writer':
        return <FileText size={16} />;
      default:
        return <Users size={16} />;
    }
  };

  const HierarchyCard = ({ node, level = 1 }) => (
    <div key={node.agent_id} className={`agent-box agent-box-level-${level}`}>
      <div className="agent-box-header">
        <div className="agent-box-icon">{getRoleIcon(node.role)}</div>
        <div className="agent-box-title-section">
          <h4 className="agent-box-title">{roleLabel(node.role)}</h4>
          <div className="agent-box-status">
            {getStatusIcon(node.status)}
            <span className="agent-box-status-text">{node.status}</span>
            {node.virtual && <span className="agent-monitor-chip">virtual</span>}
          </div>
        </div>
      </div>
      <div className="agent-box-stats">
        <div className="stat-item">
          <span className="stat-label">Tasks:</span>
          <span className="stat-value">{node.task_count || 0}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Success:</span>
          <span className="stat-value">{((node.success_rate || 0) * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return <div className="panel-loading">Loading agents...</div>;
  }

  return (
    <div className={`agent-monitor ${expanded ? 'expanded' : 'compact'}`}>
      {expanded ? (
        <>
          <div className="monitor-section">
            <h4 className="monitor-title">Agent Overview (Hierarchy)</h4>
            <div className="agent-flow-strip">
              {FLOW_NODES.map((node, idx) => (
                <React.Fragment key={node.id}>
                  <div className={`agent-flow-node level-${node.level}`}>
                    <div className="agent-flow-node-title">{node.label}</div>
                    <div className="agent-flow-node-task">{node.task}</div>
                  </div>
                  {idx < FLOW_NODES.length - 1 && <div className="agent-flow-arrow">→</div>}
                </React.Fragment>
              ))}
            </div>
            <div className="agent-monitor-hierarchy">
              <div className="hierarchy-level level-0">
                <div className="level-label">Control</div>
                <div className="agent-container">
                  <HierarchyCard node={hierarchy.ceo} level={0} />
                </div>
              </div>

              <div className="hierarchy-level level-1">
                <div className="agent-container">
                  <HierarchyCard node={hierarchy.orchestrator} level={1} />
                </div>
              </div>

              <div className="hierarchy-level level-1">
                <div className="level-label">Research Flow</div>
                <div className="executive-group">
                  <HierarchyCard node={hierarchy.researchDirector} level={1} />
                  <div className="analysts-subgrid">
                    <div className="sublevel-label">Analysts</div>
                    <div className="analysts-grid">
                      {hierarchy.analysts.map((agent) => (
                        <HierarchyCard key={agent.agent_id} node={agent} level={2} />
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="hierarchy-level level-1">
                <div className="level-label">Execution & Risk</div>
                <div className="analysts-grid">
                  {hierarchy.execution.map((agent) => (
                    <HierarchyCard key={agent.agent_id} node={agent} level={2} />
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="monitor-section">
            <h4 className="monitor-title">Worker Pool ({agents.length})</h4>
            <div className="agent-list">
              {agents.map((agent) => (
                <div key={agent.agent_id} className="agent-row">
                  <div className="agent-info">
                    <div className="agent-header">
                      <span className="agent-name">{agent.role}</span>
                      {getStatusIcon(agent.status)}
                      <span className="agent-status">{agent.status}</span>
                    </div>
                    <div className="agent-details">
                      <span className="agent-id">ID: {agent.agent_id.slice(0, 8)}</span>
                      <span className="agent-rate">Success: {(agent.success_rate * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                    <div className="agent-metrics">
                      <div className="metric">
                        <span className="metric-label">Tasks</span>
                        <span className="metric-value">{agent.task_count}</span>
                      </div>
                      <div className="metric">
                        <span className="metric-label">Uptime</span>
                        <span className="metric-value">
                          {agent.last_heartbeat
                            ? `${Math.max(
                                0,
                                Math.floor((Date.now() - new Date(agent.last_heartbeat)) / 1000)
                              )}s`
                            : 'n/a'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="monitor-section">
            <h4 className="monitor-title">Active Tasks ({tasks.length})</h4>
            <div className="task-list">
              {tasks.length === 0 ? (
                <div className="empty-state">No active tasks right now</div>
              ) : (
                tasks.map((task, idx) => (
                  <div key={task.task_id || `task-${idx}`} className="task-row">
                    <div className="task-status">{getStatusIcon(task.status || 'running')}</div>
                    <div className="task-info">
                      <div className="task-title">
                        {(task.role || task.task_type || 'Task').toString()} - Priority{' '}
                        {task.priority ?? 'n/a'}
                      </div>
                      <div className="task-details">
                        <span>Agent: {(task.agent_id || task.role || 'n/a').toString().slice(0, 16)}</span>
                        <span>
                          Created:{' '}
                          {new Date(task.created_at || task.ts || Date.now()).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="monitor-section">
            <h4 className="monitor-title">Recent Task Events ({recentEvents.length})</h4>
            <div className="task-list">
              {recentEvents.length === 0 ? (
                <div className="empty-state">No recent events</div>
              ) : (
                recentEvents.map((event, idx) => (
                  <div key={`${event.task_id}-${idx}`} className="task-row">
                    <div className="task-status">{getStatusIcon(event.status)}</div>
                    <div className="task-info">
                      <div className="task-title">
                        {event.role} - {(event.status || 'unknown').toUpperCase()}
                      </div>
                      <div className="task-details">
                        <span>Run: {(event.run_id || 'n/a').toString().slice(0, 20)}</span>
                        <span>{new Date(event.ts).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="agent-monitor-compact">
          <div className="compact-stat">
            <Cpu size={16} />
            <span>{agents.length} agents</span>
          </div>
          <div className="compact-stat">
            <Activity size={16} />
            <span>{tasks.length} active tasks</span>
          </div>
          <div className="compact-stat running">
            <div className="dot-live" />
            {agents.filter((a) => a.status === 'running').length} running
          </div>
          <div className="compact-stat">
            {agents.length > 0 && (
              <>
                <span>Avg Success: </span>
                <strong>
                  {(
                    (agents.reduce((sum, a) => sum + a.success_rate, 0) / agents.length) * 100
                  ).toFixed(0)}
                  %
                </strong>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentMonitor;
