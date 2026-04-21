import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Search,
  Filter,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  BookOpen,
} from 'lucide-react';
import '../styles/research.css';
import { researchAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ConnectionIndicator from '../components/common/ConnectionIndicator';
import ToastContainer from '../components/common/Toast';
import ResearchGrid from '../components/research/ResearchGrid';
import ResearchDetail from '../components/research/ResearchDetail';

const TICKER_LABELS = {
  AAPL: 'Apple Inc.',
  AMD: 'Advanced Micro Devices',
  AMZN: 'Amazon.com',
  META: 'Meta Platforms',
  MSFT: 'Microsoft Corporation',
  NVDA: 'NVIDIA Corporation',
  SLV: 'iShares Silver Trust',
  SPY: 'SPDR S&P 500 ETF',
};

const classifyPaper = (report) => {
  const title = String(report?.title || '').toLowerCase();
  const summary = String(report?.summary || '').toLowerCase();
  const findings = Array.isArray(report?.findings) ? report.findings.length : 0;
  if (title.includes('proposal') || summary.includes('proposal')) return 'Proposal Paper';
  if (title.includes('discovery') || summary.includes('discovery')) return 'Discovery Note';
  if (report?.agent_role === 'researcher' || findings >= 4) return 'Case Study';
  return 'Signal Brief';
};

const transition = (fn) => {
  if (document.startViewTransition) {
    document.startViewTransition(fn);
    return;
  }
  fn();
};

const Research = () => {
  const requestedReportId = useRef(new URLSearchParams(window.location.search).get('report'));
  const [view, setView] = useState('grid');
  const [selectedReport, setSelectedReport] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [qualityFilter, setQualityFilter] = useState('institutional');
  const [sortBy, setSortBy] = useState('recent');
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;

    const fetchReports = async () => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;

      try {
        if (!reports.length) setConnectionStatus('connecting');
        const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Request timeout')), 15000));
        const data = await Promise.race([researchAPI.getReports({ status: 'published', limit: 80 }), timeoutPromise]);
        if (!isMounted.current) return;
        setReports(data.reports || []);
        setConnectionStatus('connected');
        setLastUpdate(new Date());

        if (requestedReportId.current && !selectedReport) {
          try {
            const detail = await researchAPI.getReportDetail(requestedReportId.current);
            if (isMounted.current && detail) {
              setSelectedReport(detail);
              setView('detail');
            }
          } catch (detailErr) {
            console.warn('Failed to hydrate requested report:', detailErr);
          }
        }
        setLoading(false);
      } catch (err) {
        if (!isMounted.current) return;
        console.error('Failed to fetch research reports:', err);
        setConnectionStatus('error');
        setLoading(false);
        showError(`Failed to load reports: ${err.message}`);
      } finally {
        fetchInProgress.current = false;
      }
    };

    fetchReports();
    const interval = setInterval(fetchReports, 30000);
    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, []);

  const enrichedReports = useMemo(
    () =>
      reports.map((report) => {
        const leadAsset = String(report.asset_universe?.[0] || 'MULTI').toUpperCase();
        return {
          ...report,
          paperType: classifyPaper(report),
          leadAsset,
          leadAssetName: TICKER_LABELS[leadAsset] || leadAsset,
          institutionalScore: report.agent_role === 'researcher' ? 2 : Number(report.confidence || 0) >= 0.6 ? 1 : 0,
        };
      }),
    [reports]
  );

  const filteredReports = useMemo(() => {
    let next = [...enrichedReports];
    if (qualityFilter === 'institutional') next = next.filter((r) => r.institutionalScore > 0);
    if (qualityFilter === 'case-study') next = next.filter((r) => r.paperType === 'Case Study');
    if (qualityFilter === 'proposal') next = next.filter((r) => r.paperType === 'Proposal Paper');
    if (searchTerm.trim()) {
      const query = searchTerm.trim().toLowerCase();
      next = next.filter((r) =>
        [r.title, r.summary, r.leadAsset, r.leadAssetName, r.paperType].some((field) => String(field || '').toLowerCase().includes(query))
      );
    }
    if (sortBy === 'recent') next.sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
    if (sortBy === 'confidence') next.sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0));
    if (sortBy === 'paper') next.sort((a, b) => a.paperType.localeCompare(b.paperType));
    return next;
  }, [enrichedReports, qualityFilter, searchTerm, sortBy]);

  const handleRefresh = () => {
    setConnectionStatus('connecting');
    setLoading(true);
    setTimeout(() => {
      setConnectionStatus('connected');
      setLoading(false);
      success('Research data refreshed');
    }, 600);
  };

  const handleReportClick = async (report) => {
    try {
      const detail = await researchAPI.getReportDetail(report.report_id);
      transition(() => {
        setSelectedReport(detail || report);
        setView('detail');
        const url = new URL(window.location.href);
        url.searchParams.set('report', report.report_id);
        window.history.replaceState({}, '', url.toString());
      });
    } catch (err) {
      console.warn('Failed to fetch report detail:', err);
      transition(() => {
        setSelectedReport(report);
        setView('detail');
      });
    }
  };

  const handleBackToGrid = () => {
    transition(() => {
      setSelectedReport(null);
      setView('grid');
      const url = new URL(window.location.href);
      url.searchParams.delete('report');
      window.history.replaceState({}, '', url.toString());
    });
  };

  return (
    <>
      <ToastContainer />
      <div className="research-container">
        <header className="research-header" role="banner">
          <div className="header-left">
            {view === 'detail' && (
              <button className="btn-back" onClick={handleBackToGrid} aria-label="Back to research grid">
                <ArrowLeft size={18} />
                Back
              </button>
            )}
            <h1 className="page-title">Research Hub</h1>
          </div>
          <div className="header-right">
            <ConnectionIndicator status={connectionStatus} lastUpdate={lastUpdate} />
            <button className="btn-refresh" onClick={handleRefresh} disabled={loading} aria-label="Refresh research">
              <RefreshCw size={18} className={loading ? 'spinning' : ''} />
            </button>
          </div>
        </header>

        {loading && view === 'grid' ? (
          <div className="research-loading"><div className="loading-state"><div className="spinner" /><p>Loading research reports...</p></div></div>
        ) : connectionStatus === 'error' && !reports.length ? (
          <div className="error-state"><AlertCircle size={48} /><h3>Connection Failed</h3><p>Unable to load research reports</p><button className="btn-primary" onClick={handleRefresh}>Retry</button></div>
        ) : view === 'grid' ? (
          <>
            <section className="research-hero" role="region" aria-label="Research introduction">
              <div className="hero-content">
                <h2 className="hero-title">Case Studies, Discovery Notes, and Proposal Papers</h2>
                <p className="hero-subtitle">Readable institutional research from Vektor's live research stack. Default view prioritizes composite and high-confidence work.</p>
              </div>
            </section>

            <section className="research-controls" role="search">
              <div className="search-bar">
                <Search size={18} className="search-icon" aria-hidden="true" />
                <input type="text" placeholder="Search asset, topic, or paper type..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="search-input" aria-label="Search research" />
              </div>
              <div className="controls-right">
                <div className="filter-group">
                  <Filter size={16} aria-hidden="true" />
                  <select value={qualityFilter} onChange={(e) => setQualityFilter(e.target.value)} className="filter-select" aria-label="Filter research quality">
                    <option value="institutional">Institutional set</option>
                    <option value="case-study">Case studies</option>
                    <option value="proposal">Proposal papers</option>
                    <option value="all">All reports</option>
                  </select>
                </div>
                <div className="sort-group">
                  <label htmlFor="sort-select">Sort by:</label>
                  <select id="sort-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="sort-select" aria-label="Sort research reports">
                    <option value="recent">Most Recent</option>
                    <option value="confidence">Highest Confidence</option>
                    <option value="paper">Paper Type</option>
                  </select>
                </div>
              </div>
            </section>

            <section className="research-results-info" role="status" aria-live="polite">
              <div className="results-count">Showing <strong>{filteredReports.length}</strong> of <strong>{reports.length}</strong> reports</div>
            </section>

            {filteredReports.length > 0 ? <ResearchGrid reports={filteredReports} onReportClick={handleReportClick} /> : (
              <div className="empty-research"><BookOpen size={48} /><h3>No research found</h3><p>Adjust the search or filters.</p></div>
            )}
          </>
        ) : (
          selectedReport && <ResearchDetail report={{ ...selectedReport, paperType: classifyPaper(selectedReport) }} onBack={handleBackToGrid} />
        )}
      </div>
    </>
  );
};

export default Research;
