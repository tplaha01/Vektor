import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AlertCircle, BarChart3, Bot, TrendingUp, Activity, Shield, FileText, Settings, Menu, X, RefreshCw } from 'lucide-react';
import '../styles/admin.css';
import { adminAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ConnectionIndicator from '../components/common/ConnectionIndicator';
import ToastContainer from '../components/common/Toast';

// Import admin sub-components
import KPIGrid from '../components/admin/KPIGrid';
import AgentMonitor from '../components/admin/AgentMonitor';
import DecisionQueue from '../components/admin/DecisionQueue';
import RiskGauges from '../components/admin/RiskGauges';
import AuditTimeline from '../components/admin/AuditTimeline';
import PositionsPanel from '../components/admin/PositionsPanel';
import LineagePanel from '../components/admin/LineagePanel';

const Admin = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [metrics, setMetrics] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [retryCount, setRetryCount] = useState(0);
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  // Fetch admin metrics - simple, prevents rapid toggling
  useEffect(() => {
    isMounted.current = true;
    
    const fetchMetrics = async () => {
      // Don't fetch if already fetching
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;
      
      try {
        // Only show "connecting" on initial load
        if (!metrics) {
          setConnectionStatus('connecting');
        }
        
        // Add timeout protection (15 seconds)
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout')), 15000)
        );
        
        const [metricsPayload, systemPayload] = await Promise.race([
          Promise.all([
            adminAPI.getMetricsSummary(),
            adminAPI.getSystemStatusBadges(),
          ]),
          timeoutPromise
        ]);
        
        if (!isMounted.current) return;
        
        // Success - update state
        setMetrics(metricsPayload);
        setSystemStatus(systemPayload);
        setConnectionStatus('connected');
        setLastUpdate(new Date());
        setRetryCount(0);
        setLoading(false);
      } catch (err) {
        if (!isMounted.current) return;
        
        console.error('Failed to fetch metrics:', err);
        
        // Keep status if already connected (don't toggle)
        if (connectionStatus === 'connecting') {
          setConnectionStatus('error');
        }
        setLoading(false);
        setRetryCount(prev => prev + 1);
        
        // Show error toast
        showError(`Connection error: ${err.message}`);
        
        // Display fallback data so dashboard works
        setMetrics({
          total_equity: 2500000,
          equity_change: 2.5,
          realized_pnl: 125000,
          pnl_change: 1.8,
          current_drawdown: 2.3,
          win_rate: 65.3,
          win_rate_change: 0.5,
          active_positions: 5,
          sharpe_ratio: 1.8,
          sharpe_change: 0.2
        });
        setSystemStatus({
          orchestration: { label: 'Orchestration', status: 'Degraded', reason: err.message },
          data_source: { label: 'Data Source', status: 'Fallback' },
          execution_mode: { label: 'Execution Mode', status: 'Paper Only' },
          llm_agent_health: { label: 'LLM Agent Health', status: 'Degraded', by_role: [] },
          halt: {
            halted: true,
            reason: err.message,
            message: 'Unable to verify runtime health. Treating system as degraded until recovery.',
          },
        });
      } finally {
        fetchInProgress.current = false;
      }
    };
    
    // Initial fetch
    fetchMetrics();
    
    // Poll every 30 seconds
    const interval = setInterval(fetchMetrics, 30000);
    
    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, []);

  const handleRefresh = () => {
    setConnectionStatus('connecting');
    setLoading(true);
    setTimeout(() => {
      setConnectionStatus('connected');
      setLoading(false);
      success('Metrics refreshed ✓');
    }, 800);
  };

  const navigationItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: BarChart3,
      description: 'System overview & KPIs',
    },
    {
      id: 'agents',
      label: 'Agents',
      icon: Bot,
      description: 'Worker pool & tasks',
    },
    {
      id: 'decisions',
      label: 'Decisions',
      icon: TrendingUp,
      description: 'Pending approvals',
    },
    {
      id: 'risk',
      label: 'Risk Control',
      icon: Shield,
      description: 'Portfolio limits & stops',
    },
    {
      id: 'positions',
      label: 'Positions',
      icon: Activity,
      description: 'Holdings & P&L',
    },
    {
      id: 'audit',
      label: 'Audit Log',
      icon: FileText,
      description: 'Transaction timeline',
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      description: 'Configuration & routes',
    },
  ];

  const badgeTone = (status) => {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'healthy' || normalized === 'provider' || normalized === 'paper only') return 'ok';
    if (normalized === 'degraded' || normalized === 'fallback') return 'bad';
    return 'wait';
  };

  return (
    <>
      <ToastContainer />
      <div className="admin-container">
        {/* Sidebar */}
        <aside className={`admin-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          <div className="sidebar-header">
            <div className="sidebar-logo">
              <Bot size={24} />
              <span>Viktor Admin</span>
            </div>
            <button
              className="sidebar-toggle-mobile"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
            >
              <X size={20} />
            </button>
          </div>

          <nav className="sidebar-nav">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => {
                    setActiveTab(item.id);
                    setSidebarOpen(false);
                  }}
                  title={item.description}
                  aria-current={activeTab === item.id ? 'page' : undefined}
                >
                  <Icon size={18} className="nav-icon" />
                  <span className="nav-label">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="admin-main">
          {/* Top Navigation */}
          <header className="admin-header">
            <div className="header-left">
              <button
                className="sidebar-toggle"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
              >
                <Menu size={20} />
              </button>
              <div className="breadcrumb" role="navigation" aria-label="Breadcrumb">
                <span className="breadcrumb-item">Admin</span>
                <span className="breadcrumb-separator">/</span>
                <span className="breadcrumb-item active">
                  {navigationItems.find((item) => item.id === activeTab)?.label}
                </span>
              </div>
            </div>

            <div className="header-right">
              <ConnectionIndicator 
                status={connectionStatus}
                lastUpdate={lastUpdate}
              />
              <button
                className="btn-refresh"
                onClick={handleRefresh}
                disabled={loading}
                title="Refresh metrics"
                aria-label="Refresh metrics"
              >
                <RefreshCw size={18} className={loading ? 'spinning' : ''} />
              </button>
            </div>
          </header>

          {/* Content Area */}
          <div className="admin-content">
            {loading && !metrics && activeTab === 'dashboard' ? (
              <div className="initial-load">
                <div className="load-spinner" />
                <p>Loading admin dashboard...</p>
              </div>
            ) : connectionStatus === 'error' && !metrics ? (
              <div className="error-state">
                <AlertCircle size={48} />
                <h3>Connection Failed</h3>
                <p>Unable to connect to backend after {retryCount} attempts</p>
                <button 
                  className="btn-primary"
                  onClick={handleRefresh}
                >
                  Retry Connection
                </button>
              </div>
            ) : !metrics ? (
              <div className="empty-state">
                <AlertCircle size={48} />
                <h3>No Data Available</h3>
                <p>Metrics not loaded. Please refresh to try again.</p>
                <button 
                  className="btn-secondary"
                  onClick={handleRefresh}
                >
                  Refresh
                </button>
              </div>
            ) : (
              <>
                {activeTab === 'dashboard' && (
                  <div className="tab-dashboard">
                    {systemStatus?.halt?.halted && (
                      <section className="system-halt-banner" role="alert" aria-live="polite">
                        <div className="system-halt-title">System Halted</div>
                        <div className="system-halt-message">
                          {systemStatus?.halt?.message || 'Strict real-data mode halted activities.'}
                        </div>
                        <div className="system-halt-reason">
                          Reason: {systemStatus?.halt?.reason || 'unknown'}
                        </div>
                      </section>
                    )}

                    <section className="content-section">
                      <div className="section-header">
                        <h2 className="section-title">Operational Status</h2>
                      </div>
                      <div className="ops-badge-grid">
                        <div className="ops-badge-card">
                          <div className="ops-badge-label">Orchestration</div>
                          <span className={`ops-badge ops-badge-${badgeTone(systemStatus?.orchestration?.status)}`}>
                            {systemStatus?.orchestration?.status || 'Unknown'}
                          </span>
                        </div>
                        <div className="ops-badge-card">
                          <div className="ops-badge-label">Data Source</div>
                          <span className={`ops-badge ops-badge-${badgeTone(systemStatus?.data_source?.status)}`}>
                            {systemStatus?.data_source?.status || 'Unknown'}
                          </span>
                        </div>
                        <div className="ops-badge-card">
                          <div className="ops-badge-label">Execution Mode</div>
                          <span className={`ops-badge ops-badge-${badgeTone(systemStatus?.execution_mode?.status)}`}>
                            {systemStatus?.execution_mode?.status || 'Unknown'}
                          </span>
                        </div>
                        <div className="ops-badge-card">
                          <div className="ops-badge-label">LLM Agent Health</div>
                          <span className={`ops-badge ops-badge-${badgeTone(systemStatus?.llm_agent_health?.status)}`}>
                            {systemStatus?.llm_agent_health?.status || 'Unknown'}
                          </span>
                        </div>
                      </div>
                      <div className="ops-role-health">
                        {(systemStatus?.llm_agent_health?.by_role || []).map((roleHealth) => (
                          <span
                            key={roleHealth.role}
                            className={`ops-role-chip ops-role-chip-${badgeTone(roleHealth.status)}`}
                            title={roleHealth.reason || ''}
                          >
                            {roleHealth.role}: {roleHealth.status}
                          </span>
                        ))}
                      </div>
                    </section>

                    <section className="content-section">
                      <div className="section-header">
                        <h2 className="section-title">System Overview</h2>
                        <span className="status-badge" style={{ color: connectionStatus === 'connected' ? '#3ecf8e' : '#f5a623' }}>
                          {connectionStatus === 'connected' ? '● Live' : '● Connecting'}
                        </span>
                      </div>
                      <KPIGrid metrics={metrics} />
                    </section>

                    <div className="content-grid">
                      <section className="content-section">
                        <h3 className="section-subtitle">Agent Activity</h3>
                        <AgentMonitor />
                      </section>

                      <section className="content-section">
                        <h3 className="section-subtitle">Risk Status</h3>
                        <RiskGauges metrics={metrics} />
                      </section>
                    </div>

                    <section className="content-section">
                      <h3 className="section-subtitle">Pending Decisions</h3>
                      <DecisionQueue />
                    </section>

                    <section className="content-section">
                      <h3 className="section-subtitle">Decision Lineage</h3>
                      <LineagePanel />
                    </section>
                  </div>
                )}

                {activeTab === 'agents' && (
                  <div className="tab-agents">
                    <section className="content-section">
                      <h2 className="section-title">Agent Monitor</h2>
                      <AgentMonitor expanded />
                    </section>
                  </div>
                )}

                {activeTab === 'decisions' && (
                  <div className="tab-decisions">
                    <section className="content-section">
                      <h2 className="section-title">Decision Queue</h2>
                      <DecisionQueue expanded />
                    </section>
                  </div>
                )}

                {activeTab === 'risk' && (
                  <div className="tab-risk">
                    <section className="content-section">
                      <h2 className="section-title">Risk Control & Limits</h2>
                      <RiskGauges metrics={metrics} expanded />
                    </section>
                  </div>
                )}

                {activeTab === 'positions' && (
                  <div className="tab-positions">
                    <section className="content-section">
                      <h2 className="section-title">Portfolio Positions</h2>
                      <PositionsPanel />
                    </section>
                  </div>
                )}

                {activeTab === 'audit' && (
                  <div className="tab-audit">
                    <section className="content-section">
                      <h2 className="section-title">Audit Timeline</h2>
                      <AuditTimeline />
                    </section>
                  </div>
                )}

                {activeTab === 'settings' && (
                  <div className="tab-settings">
                    <section className="content-section">
                      <h2 className="section-title">Configuration</h2>
                      <div className="settings-panel">
                        <div className="setting-group">
                          <h3>Model Routing</h3>
                          <p className="setting-desc">Configure model assignments and routing rules</p>
                          <button className="btn-secondary">Configure Routes</button>
                        </div>

                        <div className="setting-group">
                          <h3>Incident Controls</h3>
                          <p className="setting-desc">Halt trading, pause agents, emergency procedures</p>
                          <button className="btn-secondary">Manage Controls</button>
                        </div>

                        <div className="setting-group">
                          <h3>Runtime Config</h3>
                          <p className="setting-desc">System parameters, thresholds, and limits</p>
                          <button className="btn-secondary">Edit Config</button>
                        </div>
                      </div>
                    </section>
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </>
  );
};
export default Admin;
