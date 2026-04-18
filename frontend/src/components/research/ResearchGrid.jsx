import React from 'react';
import {
  TrendingUp,
  Calendar,
  Eye,
  MessageCircle,
  ChevronRight,
  Zap,
} from 'lucide-react';

const ResearchGrid = ({ reports, onReportClick }) => {
  const getConfidenceColor = (confidence) => {
    if (confidence > 0.7) return 'high';
    if (confidence > 0.4) return 'medium';
    return 'low';
  };

  const getAgentRole = (agentRole) => {
    const roleMap = {
      research_director: 'Research Director',
      risk_auditor: 'Risk Auditor',
      trading_director: 'Trading Director',
      fund_manager: 'Fund Manager',
      sentiment_analyst: 'Sentiment Analyst',
    };
    return roleMap[agentRole] || agentRole;
  };

  return (
    <div className="research-grid-container">
      <div className="research-grid">
        {reports.map((report) => (
          <article
            key={report.report_id}
            className="research-card"
            onClick={() => onReportClick(report)}
          >
            {/* Card Header with Badge */}
            <div className="card-header">
              <div className="card-title-section">
                <h3 className="card-title">{report.title}</h3>
                <div className="card-badges">
                  <span
                    className={`confidence-badge ${getConfidenceColor(report.confidence)}`}
                  >
                    <Zap size={12} />
                    {(report.confidence * 100).toFixed(0)}%
                  </span>

                  {report.status === 'draft' && (
                    <span className="status-badge draft">Draft</span>
                  )}
                </div>
              </div>
            </div>

            {/* Card Body */}
            <div className="card-body">
              <p className="card-summary">{report.summary}</p>

              {/* Asset Universe Tags */}
              {report.asset_universe && report.asset_universe.length > 0 && (
                <div className="asset-tags">
                  {report.asset_universe.slice(0, 4).map((asset) => (
                    <span key={asset} className="asset-tag">
                      {asset}
                    </span>
                  ))}
                  {report.asset_universe.length > 4 && (
                    <span className="asset-tag more">
                      +{report.asset_universe.length - 4}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Card Metadata */}
            <div className="card-meta">
              <div className="meta-author">
                <div className="author-avatar">
                  {getAgentRole(report.agent_role).charAt(0)}
                </div>
                <div className="author-info">
                  <div className="author-name">{getAgentRole(report.agent_role)}</div>
                  <div className="author-role">{report.agent_role}</div>
                </div>
              </div>

              <div className="meta-stats">
                <div className="meta-item">
                  <Calendar size={12} />
                  <span>{new Date(report.published_at).toLocaleDateString()}</span>
                </div>

                {report.views !== undefined && (
                  <div className="meta-item">
                    <Eye size={12} />
                    <span>{report.views}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Card Footer - CTA */}
            <div className="card-footer">
              <button className="read-more-btn">
                Read More
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
