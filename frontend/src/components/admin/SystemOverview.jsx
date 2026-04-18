import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, AlertCircle, CheckCircle, Pause, Zap, 
  Users, Bot, BarChart3, Shield, Lock, FileText 
} from 'lucide-react';
import { adminAPI } from '../../api/adminAPI';

const SystemOverview = () => {
  const [hierarchy, setHierarchy] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  // Fetch initial hierarchy
  useEffect(() => {
    const fetchHierarchy = async () => {
      try {
        const data = await adminAPI.getAgentHierarchy?.() || {
          hierarchy: null,
          stats: null,
        };
        setHierarchy(data.hierarchy);
        setStats(data.stats);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch agent hierarchy:', err);
        setLoading(false);
      }
    };

    fetchHierarchy();
    const interval = setInterval(fetchHierarchy, 5000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const connectWebSocket = () => {
      // Determine protocol and host
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = 'localhost:8000'; // Connect directly to backend
      const wsUrl = `${protocol}//${host}/ws/agents`;
      
      console.log(`[SystemOverview] Attempting WebSocket connection to: ${wsUrl}`);

      try {
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[SystemOverview] ✓ WebSocket connected successfully');
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log('WS Message:', message.type, message);
            
            // Handle agent status snapshot (initial state)
            if (message.type === 'agent.status_snapshot' && message.agents) {
              console.log('Received status snapshot with', Object.keys(message.agents).length, 'agents');
              setStats(message.agents);
              // Fetch full hierarchy to rebuild with status data
              adminAPI.getAgentHierarchy?.().then(data => {
                if (data?.hierarchy) {
                  setHierarchy(data.hierarchy);
                }
              }).catch(err => console.error('Failed to fetch hierarchy:', err));
            }
            
            // Handle individual agent status changes
            if (message.type === 'agent.status_changed' && message.data) {
              const agentUpdate = message.data;
              console.log('Agent status changed:', agentUpdate.agent_id, agentUpdate.status);
              
              // Update stats with new agent status
              setStats(prev => {
                if (!prev) return prev;
                return {
                  ...prev,
                  [agentUpdate.agent_id]: {
                    ...prev[agentUpdate.agent_id],
                    ...agentUpdate,
                  }
                };
              });
              
              // Re-fetch hierarchy to get updated structure
              adminAPI.getAgentHierarchy?.().then(data => {
                if (data?.hierarchy) {
                  setHierarchy(data.hierarchy);
                }
              }).catch(err => console.error('Failed to fetch hierarchy:', err));
            }
            
            // Handle task events
            if (message.type === 'task.status_updated' && message.data) {
              console.log('Task update:', message.data);
              // Re-fetch hierarchy on task changes
              adminAPI.getAgentHierarchy?.().then(data => {
                if (data?.hierarchy) {
                  setHierarchy(data.hierarchy);
                }
              }).catch(err => console.error('Failed to fetch hierarchy:', err));
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        ws.onerror = (error) => {
          console.error('[SystemOverview] ✗ WebSocket error:', error);
          setWsConnected(false);
        };

        ws.onclose = (event) => {
          console.log(`[SystemOverview] ✗ WebSocket disconnected (code: ${event.code}, reason: ${event.reason})`);
          setWsConnected(false);
          // Reconnect after 3 seconds
          console.log('[SystemOverview] Reconnecting in 3 seconds...');
          setTimeout(connectWebSocket, 3000);
        };

        wsRef.current = ws;
      } catch (err) {
        console.error('[SystemOverview] ✗ Failed to create WebSocket:', err);
        setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  if (loading) {
    return (
      <div className="system-overview">
        <div className="overview-loading">
          <div className="spinner"></div>
          <p>Loading agent system...</p>
        </div>
      </div>
    );
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Activity size={16} className="status-icon running" />;
      case 'idle':
        return <CheckCircle size={16} className="status-icon idle" />;
      case 'error':
        return <AlertCircle size={16} className="status-icon error" />;
      case 'stopped':
        return <Pause size={16} className="status-icon stopped" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return 'rgb(62, 207, 142)';
      case 'idle':
        return 'rgb(74, 158, 255)';
      case 'error':
        return 'rgb(224, 82, 82)';
      case 'stopped':
        return 'rgb(139, 145, 158)';
      default:
        return 'rgb(139, 145, 158)';
    }
  };

  const getAgentIcon = (role) => {
    switch (role) {
      case 'fund_manager':
        return <Zap size={20} />;
      case 'research_director':
        return <BarChart3 size={20} />;
      case 'trading_director':
        return <Activity size={20} />;
      case 'risk_auditor':
        return <Shield size={20} />;
      case 'compliance_ops':
        return <Lock size={20} />;
      case 'technical_analyst':
      case 'fundamental_analyst':
      case 'sentiment_analyst':
      case 'ml_timeseries_analyst':
      case 'insight_researcher':
      case 'hedge_fund_researcher':
        return <Bot size={18} />;
      case 'blog_writer':
        return <FileText size={20} />;
      default:
        return <Users size={20} />;
    }
  };

  const AgentBox = ({ agent, level = 0 }) => {
    if (!agent) return null;

    return (
      <div className={`agent-box agent-box-level-${level}`} style={{ borderLeft: `3px solid ${getStatusColor(agent.status)}` }}>
        <div className="agent-box-header">
          <div className="agent-box-icon" style={{ color: getStatusColor(agent.status) }}>
            {getAgentIcon(agent.role)}
          </div>
          <div className="agent-box-title-section">
            <h4 className="agent-box-title">{agent.role.replace(/_/g, ' ').toUpperCase()}</h4>
            <div className="agent-box-status">
              {getStatusIcon(agent.status)}
              <span className="agent-box-status-text">{agent.status}</span>
            </div>
          </div>
        </div>

        <div className="agent-box-content">
          {agent.current_activity && (
            <div className="agent-box-activity">
              <span className="activity-label">Activity:</span>
              <span className="activity-value">{agent.current_activity}</span>
            </div>
          )}
          {agent.current_task && (
            <div className="agent-box-task">
              <span className="task-label">Task:</span>
              <span className="task-value">{agent.current_task}</span>
            </div>
          )}
          <div className="agent-box-stats">
            <div className="stat-item">
              <span className="stat-label">Completed:</span>
              <span className="stat-value">{agent.success_count || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Failed:</span>
              <span className="stat-value error-count">{agent.failed_count || 0}</span>
            </div>
          </div>
        </div>

        {agent.last_error && (
          <div className="agent-box-error">
            <AlertCircle size={14} />
            <span>{agent.last_error}</span>
          </div>
        )}
      </div>
    );
  };

  const fundManager = hierarchy?.fund_manager;
  const executives = hierarchy?.executives || [];

  return (
    <div className="system-overview">
      <div className="overview-header">
        <h2>System Orchestration Overview</h2>
        <div className="overview-connection">
          <div className={`connection-indicator ${wsConnected ? 'connected' : 'disconnected'}`}></div>
          <span className="connection-text">
            {wsConnected ? 'Live' : 'Polling'}
          </span>
        </div>
      </div>

      {stats && (
        <div className="overview-stats-bar">
          <div className="stat-badge">
            <span className="badge-label">Total Agents:</span>
            <span className="badge-value">{stats.total_agents}</span>
          </div>
          <div className="stat-badge">
            <span className="badge-label">Active:</span>
            <span className="badge-value active">{stats.active_count}</span>
          </div>
          <div className="stat-badge">
            <span className="badge-label">Idle:</span>
            <span className="badge-value idle">{stats.idle_count}</span>
          </div>
          <div className="stat-badge">
            <span className="badge-label">Errors:</span>
            <span className="badge-value error">{stats.error_count}</span>
          </div>
        </div>
      )}

      <div className="overview-hierarchy">
        {/* Fund Manager Level */}
        {fundManager && (
          <div className="hierarchy-level level-0">
            <div className="level-label">Executive</div>
            <div className="agent-container">
              <AgentBox agent={fundManager} level={0} />
            </div>
          </div>
        )}

        {/* Executives & Analysts */}
        {executives.length > 0 && (
          <div className="hierarchy-level level-1">
            <div className="level-label">Leadership & Operations</div>
            <div className="executives-grid">
              {executives.map((exec, idx) => {
                const role = Object.keys(exec)[0];
                const agent = exec[role];
                const analysts = exec.analysts;

                return (
                  <div key={idx} className="executive-group">
                    <AgentBox agent={agent} level={1} />
                    
                    {analysts && analysts.length > 0 && (
                      <div className="analysts-subgrid">
                        <div className="sublevel-label">Research Analysts</div>
                        <div className="analysts-grid">
                          {analysts.filter(a => a).map((analyst, aIdx) => (
                            <AgentBox key={aIdx} agent={analyst} level={2} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemOverview;
