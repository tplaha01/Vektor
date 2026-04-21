import React from 'react';
import { Calendar, Eye, ChevronRight, Zap } from 'lucide-react';

const ResearchGrid = ({ reports, onReportClick }) => {
  const getConfidenceColor = (confidence) => {
    if (confidence > 0.7) return 'high';
    if (confidence > 0.4) return 'medium';
    return 'low';
  };

  const getAgentRole = (agentRole) => {
    const roleMap = {
      researcher: 'Signal Committee',
      research_director: 'Research Director',
      risk_auditor: 'Risk Auditor',
      trading_director: 'Trading Director',
      fund_manager: 'Fund Manager',
      sentiment_analyst: 'Sentiment Analyst',
    };
    return roleMap[agentRole] || String(agentRole || 'Agent').replace(/_/g, ' ');
  };

  return (
    <div className="research-grid-container">
      <div className="research-grid">
        {reports.map((report) => (
          <article
            key={report.report_id}
            className="research-card"
            style={{ viewTransitionName: `research-card-${report.report_id}` }}
            onClick={() => onReportClick(report)}
          >
            <div className="card-header">
              <div className="card-title-section">
                <div className="card-badges" style={{ marginBottom: 10 }}>
                  <span className={`confidence-badge ${getConfidenceColor(report.confidence)}`}>
                    <Zap size={12} />
                    {(report.confidence * 100).toFixed(0)}%
                  </span>
                  <span className="status-badge published">{report.paperType || 'Paper'}</span>
                </div>
                <h3 className="card-title">{report.title}</h3>
              </div>
            </div>

            <div className="card-body">
              <p className="card-summary">{report.summary}</p>
              <div className="asset-tags">
                <span className="asset-tag">{report.leadAsset}</span>
                <span className="asset-tag">{report.leadAssetName}</span>
                <span className="asset-tag">{getAgentRole(report.agent_role)}</span>
              </div>
            </div>

            <div className="card-meta">
              <div className="meta-author">
                <div className="author-avatar">{getAgentRole(report.agent_role).charAt(0)}</div>
                <div className="author-info">
                  <div className="author-name">{getAgentRole(report.agent_role)}</div>
                  <div className="author-role">{report.paperType}</div>
                </div>
              </div>
              <div className="meta-stats">
                <div className="meta-item"><Calendar size={12} /><span>{new Date(report.published_at).toLocaleDateString()}</span></div>
                <div className="meta-item"><Eye size={12} /><span>{report.views || 0}</span></div>
              </div>
            </div>

            <div className="card-footer">
              <button className="read-more-btn">
                Open Paper
                <ChevronRight size={14} />
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
};

export default ResearchGrid;
