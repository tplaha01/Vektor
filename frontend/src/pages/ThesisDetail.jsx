import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, Users, BarChart3, Calendar } from 'lucide-react';
import '../styles/thesis.css';

const ThesisDetail = () => {
  const { thesisId } = useParams();
  const navigate = useNavigate();
  const [thesisData, setThesisData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data - replace with actual API call
    setTimeout(() => {
      setThesisData({
        id: thesisId,
        title: 'Tech Sector Outperformance Thesis',
        author: 'Research Director',
        createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        summary: 'Technology sector expected to outperform broader market due to strong earnings growth and AI momentum.',
        hypothesis: 'Large-cap tech companies will deliver above-market returns in the next 2-3 quarters due to AI adoption tailwinds.',
        confidence: 0.78,
        timeframe: '2-3 quarters',
        primaryAssets: ['AAPL', 'MSFT', 'GOOGL', 'NVDA'],
        keyDrivers: [
          'AI adoption accelerating across enterprise',
          'Cloud computing growth continuing',
          'Strong earnings guidance from mega-cap tech',
          'Favorable valuation vs historical averages'
        ],
        risks: [
          'Regulatory headwinds on big tech',
          'Macroeconomic slowdown',
          'Interest rate spike',
          'AI hype cycle reversal'
        ],
        relatedDecisions: [thesisId + '-001', thesisId + '-002'],
        backtestResults: {
          startDate: '2022-01-01',
          endDate: '2024-01-01',
          returns: '24.3%',
          sharpeRatio: 1.45,
          maxDrawdown: '15.2%',
          winRate: '68%'
        }
      });
      setLoading(false);
    }, 800);
  }, [thesisId]);

  if (loading) {
    return (
      <div className="thesis-container">
        <div className="thesis-loading">Loading thesis...</div>
      </div>
    );
  }

  return (
    <div className="thesis-container">
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
              <span className="value warning">-{thesisData.backtestResults.maxDrawdown}</span>
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
