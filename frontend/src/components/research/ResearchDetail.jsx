import React, { useState } from 'react';
import {
  ChevronLeft,
  Share2,
  BookmarkPlus,
  Download,
  Zap,
  Calendar,
  User,
  Layers,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import ProvenanceVisualization from './ProvenanceVisualization';

const ResearchDetail = ({ report, onBack }) => {
  const [showProvenance, setShowProvenance] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleShare = async () => {
    try {
      const reportUrl = `${window.location.origin}/research?id=${report.id}`;
      if (navigator.share) {
        await navigator.share({
          title: report.title,
          text: report.summary,
          url: reportUrl,
        });
      } else {
        await navigator.clipboard.writeText(reportUrl);
        alert('Report link copied to clipboard!');
      }
    } catch (err) {
      console.error('Share error:', err);
    }
  };

  const handleDownload = () => {
    try {
      // Create a simple text document for download
      const reportText = `
${report.title}
${new Date(report.published_at).toLocaleDateString()}

SUMMARY
${report.summary}

KEY FINDINGS
${report.findings?.map((f, i) => `${i + 1}. ${f}`).join('\n')}

ASSETS ANALYZED
${report.asset_universe?.join(', ')}
      `.trim();

      const element = document.createElement('a');
      element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(reportText));
      element.setAttribute('download', `${report.title.replace(/\s+/g, '_')}_report.txt`);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    } catch (err) {
      console.error('Download error:', err);
    }
  };

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
    <div className="research-detail-container">
      {/* Detail Header with Back Button */}
      <div className="detail-header">
        <button className="back-button" onClick={onBack}>
          <ChevronLeft size={20} />
          Back to Research
        </button>

        <div className="header-actions">
          <button className="action-btn" onClick={handleShare} title="Share">
            <Share2 size={18} />
          </button>
          <button
            className={`action-btn ${saved ? 'saved' : ''}`}
            onClick={() => setSaved(!saved)}
            title="Save for later"
          >
            <BookmarkPlus size={18} />
          </button>
          <button className="action-btn" onClick={handleDownload} title="Download PDF">
            <Download size={18} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <article className="detail-content">
        {/* Hero Section */}
        <section className="detail-hero">
          <div className="hero-badges">
            <span className={`confidence-badge ${getConfidenceColor(report.confidence)}`}>
              <Zap size={14} />
              {(report.confidence * 100).toFixed(0)}% Confidence
            </span>

            {report.status === 'draft' && <span className="status-badge draft">Draft</span>}
            {report.status === 'published' && (
              <span className="status-badge published">Published</span>
            )}
          </div>

          <h1 className="detail-title">{report.title}</h1>
          <p className="detail-subtitle">{report.summary}</p>

          {/* Author & Metadata */}
          <div className="author-section">
            <div className="author-card">
              <div className="author-avatar-large">
                {getAgentRole(report.agent_role).charAt(0)}
              </div>
              <div className="author-details">
                <div className="author-name-large">{getAgentRole(report.agent_role)}</div>
                <div className="author-meta">
                  <span className="meta-item">
                    <Calendar size={14} />
                    {new Date(report.published_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </span>
                  {report.views !== undefined && (
                    <span className="meta-item">
                      <Layers size={14} />
                      {report.views} views
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Key Metrics */}
            <div className="key-metrics">
              <div className="metric">
                <span className="metric-label">Assets Covered</span>
                <span className="metric-value">
                  {report.asset_universe?.length || 0}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Data Sources</span>
                <span className="metric-value">
                  {report.provenance?.data_sources?.length || 0}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Decision Links</span>
                <span className="metric-value">
                  {report.provenance?.decision_ids?.length || 0}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Asset Universe */}
        {report.asset_universe && report.asset_universe.length > 0 && (
          <section className="detail-section">
            <h2 className="section-title">Assets Under Analysis</h2>
            <div className="asset-list">
              {report.asset_universe.map((asset) => (
                <span key={asset} className="asset-item">
                  {asset}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Executive Summary */}
        <section className="detail-section">
          <h2 className="section-title">Executive Summary</h2>
          <div className="summary-box">
            <p>{report.summary}</p>
          </div>
        </section>

        {/* Key Findings */}
        {report.findings && report.findings.length > 0 && (
          <section className="detail-section">
            <h2 className="section-title">Key Findings</h2>
            <ol className="findings-list">
              {report.findings.map((finding, idx) => (
                <li key={idx} className="finding-item">
                  <span className="finding-number">{idx + 1}</span>
                  <div className="finding-content">
                    <p>{finding}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Provenance Trail */}
        <section className="detail-section">
          <div className="provenance-header">
            <h2 className="section-title">
              <Layers size={18} />
              Research Provenance & Lineage
            </h2>
            <button
              className="toggle-provenance"
              onClick={() => setShowProvenance(!showProvenance)}
            >
              {showProvenance ? 'Hide' : 'Show'} Provenance Tree
            </button>
          </div>

          {showProvenance && report.provenance && (
            <ProvenanceVisualization provenance={report.provenance} />
          )}

          {report.provenance && (
            <div className="provenance-summary">
              {/* Data Sources */}
              {report.provenance.data_sources && report.provenance.data_sources.length > 0 && (
                <div className="provenance-item">
                  <h4>Data Sources</h4>
                  <ul className="source-list">
                    {report.provenance.data_sources.map((source, idx) => (
                      <li key={idx} className="source-item">
                        <span className="source-icon">📊</span>
                        {source}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Thesis Link */}
              {report.provenance.thesis_id && (
                <div className="provenance-item">
                  <h4>Trading Thesis</h4>
                  <a href={`/thesis/${report.provenance.thesis_id}`} className="thesis-link">
                    <TrendingUp size={14} />
                    View Related Thesis →
                  </a>
                </div>
              )}

              {/* Decision Links */}
              {report.provenance.decision_ids && report.provenance.decision_ids.length > 0 && (
                <div className="provenance-item">
                  <h4>Linked Decisions ({report.provenance.decision_ids.length})</h4>
                  <div className="decision-links">
                    {report.provenance.decision_ids.slice(0, 3).map((decisionId, idx) => (
                      <a
                        key={idx}
                        href={`/audit/${decisionId}`}
                        className="decision-link"
                        title="View audit trail"
                      >
                        {decisionId.slice(0, 12)}...
                      </a>
                    ))}
                    {report.provenance.decision_ids.length > 3 && (
                      <span className="more-links">
                        +{report.provenance.decision_ids.length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Policy Gates Applied */}
              {report.provenance.policy_gates_applied &&
                report.provenance.policy_gates_applied.length > 0 && (
                  <div className="provenance-item">
                    <h4>Compliance Gates Applied</h4>
                    <div className="gates-list">
                      {report.provenance.policy_gates_applied.map((gate, idx) => (
                        <span key={idx} className="gate-badge">
                          ✓ {gate}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          )}
        </section>

        {/* Related Reports */}
        {report.related_reports && report.related_reports.length > 0 && (
          <section className="detail-section">
            <h2 className="section-title">Related Research</h2>
            <div className="related-reports-grid">
              {report.related_reports.map((relatedReport, idx) => (
                <a
                  key={idx}
                  href={`?id=${relatedReport.id}`}
                  className="related-report-card"
                  title={relatedReport.title}
                >
                  <h4>{relatedReport.title}</h4>
                  <p>{relatedReport.summary?.substring(0, 100)}...</p>
                </a>
              ))}
            </div>
          </section>
        )}
      </article>
    </div>
  );
};

export default ResearchDetail;
