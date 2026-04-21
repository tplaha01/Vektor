import React, { useState } from 'react';
import {
  ChevronLeft,
  Share2,
  BookmarkPlus,
  Download,
  Zap,
  Calendar,
  Layers,
  TrendingUp,
} from 'lucide-react';
import ProvenanceVisualization from './ProvenanceVisualization';

const ResearchDetail = ({ report, onBack }) => {
  const [showProvenance, setShowProvenance] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleShare = async () => {
    try {
      const reportUrl = `${window.location.origin}/research?report=${report.report_id}`;
      if (navigator.share) {
        await navigator.share({ title: report.title, text: report.summary, url: reportUrl });
      } else {
        await navigator.clipboard.writeText(reportUrl);
      }
    } catch (err) {
      console.error('Share error:', err);
    }
  };

  const handleDownload = () => {
    try {
      const reportText = [
        report.title,
        new Date(report.published_at).toLocaleDateString(),
        '',
        'ABSTRACT',
        report.summary,
        '',
        'FINDINGS',
        ...(report.findings || []).map((item, index) => `${index + 1}. ${item}`),
        '',
        'ASSETS',
        (report.asset_universe || []).join(', '),
      ].join('\n');

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

  return (
    <div className="research-detail-container" style={{ viewTransitionName: `research-card-${report.report_id}` }}>
      <div className="detail-header">
        <button className="back-button" onClick={onBack}>
          <ChevronLeft size={20} />
          Back to Research
        </button>

        <div className="header-actions">
          <button className="action-btn" onClick={handleShare} title="Share"><Share2 size={18} /></button>
          <button className={`action-btn ${saved ? 'saved' : ''}`} onClick={() => setSaved(!saved)} title="Save for later"><BookmarkPlus size={18} /></button>
          <button className="action-btn" onClick={handleDownload} title="Download text"><Download size={18} /></button>
        </div>
      </div>

      <article className="detail-content">
        <section className="detail-hero">
          <div className="hero-badges">
            <span className={`confidence-badge ${getConfidenceColor(report.confidence)}`}><Zap size={14} />{(report.confidence * 100).toFixed(0)}% Confidence</span>
            <span className="status-badge published">{report.paperType || 'Research Paper'}</span>
          </div>

          <h1 className="detail-title">{report.title}</h1>
          <p className="detail-subtitle">{report.summary}</p>

          <div className="author-section">
            <div className="author-card">
              <div className="author-avatar-large">{String(report.agent_role || 'R').charAt(0).toUpperCase()}</div>
              <div className="author-details">
                <div className="author-name-large">{String(report.agent_role || 'researcher').replace(/_/g, ' ')}</div>
                <div className="author-meta">
                  <span className="meta-item"><Calendar size={14} />{new Date(report.published_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
                  <span className="meta-item"><Layers size={14} />{report.views || 0} views</span>
                </div>
              </div>
            </div>
            <div className="key-metrics">
              <div className="metric"><span className="metric-label">Assets Covered</span><span className="metric-value">{report.asset_universe?.length || 0}</span></div>
              <div className="metric"><span className="metric-label">Data Sources</span><span className="metric-value">{report.provenance?.data_sources?.length || 0}</span></div>
              <div className="metric"><span className="metric-label">Paper Type</span><span className="metric-value">{report.paperType || 'Paper'}</span></div>
            </div>
          </div>
        </section>

        <section className="detail-section">
          <h2 className="section-title">Abstract</h2>
          <div className="summary-box"><p>{report.summary}</p></div>
        </section>

        {report.asset_universe?.length ? (
          <section className="detail-section">
            <h2 className="section-title">Coverage Universe</h2>
            <div className="asset-list">{report.asset_universe.map((asset) => <span key={asset} className="asset-item">{asset}</span>)}</div>
          </section>
        ) : null}

        {report.findings?.length ? (
          <section className="detail-section">
            <h2 className="section-title">Evidence and Findings</h2>
            <ol className="findings-list">
              {report.findings.map((finding, idx) => (
                <li key={idx} className="finding-item">
                  <span className="finding-number">{idx + 1}</span>
                  <div className="finding-content"><p>{finding}</p></div>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        <section className="detail-section">
          <div className="provenance-header">
            <h2 className="section-title"><Layers size={18} /> Provenance and lineage</h2>
            <button className="toggle-provenance" onClick={() => setShowProvenance(!showProvenance)}>{showProvenance ? 'Hide' : 'Show'} provenance tree</button>
          </div>
          {showProvenance && report.provenance ? <ProvenanceVisualization provenance={report.provenance} /> : null}
          {report.provenance ? (
            <div className="provenance-summary">
              {report.provenance.data_sources?.length ? (
                <div className="provenance-item">
                  <h4>Data Sources</h4>
                  <ul className="source-list">{report.provenance.data_sources.map((source, idx) => <li key={idx} className="source-item">{source}</li>)}</ul>
                </div>
              ) : null}
              {report.provenance.decision_ids?.length ? (
                <div className="provenance-item">
                  <h4>Linked Decisions</h4>
                  <div className="decision-links">{report.provenance.decision_ids.map((decisionId) => <a key={decisionId} href={`/audit/${decisionId}`} className="decision-link">{decisionId.slice(0, 12)}...</a>)}</div>
                </div>
              ) : null}
              {report.provenance.thesis_id ? (
                <div className="provenance-item">
                  <h4>Trading Thesis</h4>
                  <a href={`/thesis/${report.provenance.thesis_id}`} className="thesis-link"><TrendingUp size={14} /> View thesis</a>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </article>
    </div>
  );
};

export default ResearchDetail;
