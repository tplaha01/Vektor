import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, Users, BarChart3, Calendar } from 'lucide-react';
import '../styles/thesis.css';
import { adminAPI } from '../api/adminAPI';
import WorkspaceNav from '../components/common/WorkspaceNav';

const ThesisDetail = () => {
  const { thesisId } = useParams();
  const navigate = useNavigate();
  const [thesisData, setThesisData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setError('');
        const payload = await adminAPI.getLineageRunDetail(thesisId, 300);
        const decision = payload?.decision || {};
        const runRows = Array.isArray(payload?.task_events) ? payload.task_events : [];
        const createdAt = runRows.length ? runRows[0].ts || runRows[0].created_at : new Date().toISOString();
        const symbol = decision.symbol || 'n/a';
        if (!mounted) return;
        setThesisData({
          id: thesisId,
          title: `Run Thesis Context: ${symbol}`,
          author: 'Vektor Research Runtime',
          createdAt,
          summary: decision.thesis || 'No explicit thesis text available for this run yet.',
          hypothesis: decision.thesis || 'This run has not generated a formal thesis body yet.',
          confidence: Number(decision.confidence || 0),
          timeframe: decision.sleeve || 'tactical',
          primaryAssets: symbol === 'n/a' ? [] : [symbol],
          keyDrivers: [
            `Decision status: ${decision.status || 'unknown'}`,
            `Intent ID: ${decision.intent_id || 'n/a'}`,
            `Decision ID: ${decision.decision_id || 'n/a'}`,
          ],
          risks: (decision.risk_flags || []).length ? decision.risk_flags : ['Risk details not provided in this record.'],
          relatedDecisions: decision.decision_id ? [decision.decision_id] : [],
          backtestResults: {
            startDate: createdAt,
            endDate: new Date().toISOString(),
            returns: 'n/a',
            sharpeRatio: 'n/a',
            maxDrawdown: 'n/a',
            winRate: 'n/a'
          }
        });
      } catch (e) {
        if (mounted) setError(String(e?.message || e));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [thesisId]);

  if (loading) {
    return (
      <div className="thesis-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Thesis"
          title="Run Thesis Context"
          summary="Investment logic, risks, and supporting context for a single runtime thesis."
        />
        <div className="thesis-loading">Loading thesis...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="thesis-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Thesis"
          title="Run Thesis Context"
          summary="Investment logic, risks, and supporting context for a single runtime thesis."
        />
        <div className="thesis-loading">Unable to load thesis context: {error}</div>
      </div>
    );
  }

  if (!thesisData) {
    return (
      <div className="thesis-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Thesis"
          title="Run Thesis Context"
          summary="Investment logic, risks, and supporting context for a single runtime thesis."
        />
        <div className="thesis-loading">No thesis context available for this run.</div>
      </div>
    );
  }

  return (
    <div className="thesis-container">
        <WorkspaceNav
          compact
          eyebrow="Vektor Thesis"
          title="Run Thesis Context"
          summary="Investment logic, risks, and supporting context for a single runtime thesis."
        />
      <button className="thesis-back-btn" onClick={() => navigate(-1)}>
        <ArrowLeft size={20} />
        Back
      </button>

      <article className="thesis-article">
        <header className="thesis-header">
          <h1>{thesisData.title}</h1>
          <p className="thesis-subtitle">{thesisData.summary}</p>

          <div className="thesis-meta">
            <div className="meta-item">
              <Users size={16} />
              <span>{thesisData.author}</span>
            </div>
            <div className="meta-item">
              <Calendar size={16} />
              <span>{new Date(thesisData.createdAt).toLocaleDateString()}</span>
            </div>
            <div className="meta-item confidence">
              <TrendingUp size={16} />
              <span>{(thesisData.confidence * 100).toFixed(0)}% Confidence</span>
            </div>
          </div>
        </header>

        <section className="thesis-section">
          <h2>Investment Hypothesis</h2>
          <p className="thesis-text">{thesisData.hypothesis}</p>
          <div className="timeframe-badge">Timeframe: {thesisData.timeframe}</div>
        </section>

        <section className="thesis-section">
          <h2>Key Drivers</h2>
          <ul className="drivers-list">
            {thesisData.keyDrivers.map((driver, idx) => (
              <li key={idx} className="driver-item">
                <span className="checkmark">✓</span>
                <span>{driver}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="thesis-section">
          <h2>Risk Factors</h2>
          <ul className="risks-list">
            {thesisData.risks.map((risk, idx) => (
              <li key={idx} className="risk-item">
                <span className="warning">⚠</span>
                <span>{risk}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="thesis-section">
          <h2>Primary Assets</h2>
          <div className="assets-grid">
            {thesisData.primaryAssets.map((asset, idx) => (
              <div key={idx} className="asset-card">
                <span className="asset-ticker">{asset}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="thesis-section">
          <h2>Backtest Results</h2>
          <div className="backtest-grid">
            <div className="backtest-item">
              <span className="label">Period</span>
              <span className="value">
                {new Date(thesisData.backtestResults.startDate).getFullYear()} - {' '}
                {new Date(thesisData.backtestResults.endDate).getFullYear()}
              </span>
            </div>
            <div className="backtest-item">
              <span className="label">Total Return</span>
              <span className="value success">{thesisData.backtestResults.returns}</span>
            </div>
            <div className="backtest-item">
              <span className="label">Sharpe Ratio</span>
              <span className="value">{thesisData.backtestResults.sharpeRatio}</span>
            </div>
            <div className="backtest-item">
              <span className="label">Win Rate</span>
              <span className="value">{thesisData.backtestResults.winRate}</span>
            </div>
            <div className="backtest-item">
              <span className="label">Max Drawdown</span>
              <span className="value warning">{thesisData.backtestResults.maxDrawdown}</span>
            </div>
          </div>
        </section>

        <section className="thesis-section">
          <h2>Related Decisions</h2>
          <div className="related-decisions">
            {thesisData.relatedDecisions.map((decisionId, idx) => (
              <a
                key={idx}
                href={`/audit/${decisionId}`}
                className="decision-link"
              >
                Decision {idx + 1} →
              </a>
            ))}
          </div>
        </section>
      </article>
    </div>
  );
};

export default ThesisDetail;
