import React, { useState, useEffect } from 'react';
import { Cpu, Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

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

  if (loading) {
    return <div className="panel-loading">Loading agents...</div>;
  }

  return (
    <div className={`agent-monitor ${expanded ? 'expanded' : 'compact'}`}>
      {expanded ? (
        <>
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
