import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Filter,
  Calendar,
  User,
  TrendingUp,
  ChevronRight,
  Zap,
  BookOpen,
  Eye,
  MessageCircle,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import '../styles/research.css';
import { researchAPI } from '../api/adminAPI';
import { useToast } from '../components/common/Toast';
import ConnectionIndicator from '../components/common/ConnectionIndicator';
import ToastContainer from '../components/common/Toast';

// Import sub-components
import ResearchGrid from '../components/research/ResearchGrid';
import ResearchDetail from '../components/research/ResearchDetail';
import ProvenanceVisualization from '../components/research/ProvenanceVisualization';

const Research = () => {
  const [view, setView] = useState('grid'); // 'grid' or 'detail'
  const [selectedReport, setSelectedReport] = useState(null);
  const [reports, setReports] = useState([]);
  const [filteredReports, setFilteredReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recent');
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  // Fetch research reports - simple, clean logic
  useEffect(() => {
    isMounted.current = true;
    
    const fetchReports = async () => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;
      
      try {
        if (!reports.length) {
          setConnectionStatus('connecting');
        }
        
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout')), 15000)
        );
        
        const data = await Promise.race([
          researchAPI.getReports({ status: 'published', limit: 50 }),
          timeoutPromise
        ]);
        
        if (!isMounted.current) return;
        
        setReports(data.reports || []);
        setConnectionStatus('connected');
        setLastUpdate(new Date());
        setLoading(false);
      } catch (err) {
        if (!isMounted.current) return;
        
        console.error('Failed to fetch research reports:', err);
        if (connectionStatus === 'connecting') {
          setConnectionStatus('error');
        }
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

  // Filter and sort reports
  useEffect(() => {
    let filtered = reports;

    // Filter by status
    if (selectedFilter !== 'all') {
      filtered = filtered.filter((r) => r.status === selectedFilter);
    }

    // Search by title, summary, or assets
    if (searchTerm) {
      const query = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (r) =>
          r.title.toLowerCase().includes(query) ||
          r.summary.toLowerCase().includes(query) ||
          r.asset_universe?.some((asset) => asset.toLowerCase().includes(query))
      );
    }

    // Sort
    if (sortBy === 'recent') {
      filtered.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
    } else if (sortBy === 'confidence') {
      filtered.sort((a, b) => b.confidence - a.confidence);
    } else if (sortBy === 'trending') {
      filtered.sort((a, b) => (b.views || 0) - (a.views || 0));
    }

    setFilteredReports(filtered);
  }, [reports, searchTerm, selectedFilter, sortBy]);

  const handleRefresh = () => {
    setConnectionStatus('connecting');
    setLoading(true);
    setTimeout(() => {
      setConnectionStatus('connected');
      setLoading(false);
      success('Research data refreshed');
    }, 800);
  };

  const handleReportClick = (report) => {
    setSelectedReport(report);
    setView('detail');
  };

  const handleBackToGrid = () => {
    setSelectedReport(null);
    setView('grid');
  };

  return (
    <>
      <ToastContainer />
      <div className="research-container">
        {/* Header Bar */}
        <header className="research-header" role="banner">
          <div className="header-left">
            {view === 'detail' && (
              <button 
                className="btn-back"
                onClick={handleBackToGrid}
                aria-label="Back to research grid"
              >
                <ArrowLeft size={18} />
                Back
              </button>
            )}
            <h1 className="page-title">Research Hub</h1>
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
              aria-label="Refresh research"
            >
              <RefreshCw size={18} className={loading ? 'spinning' : ''} />
            </button>
          </div>
        </header>

        {loading && view === 'grid' ? (
          <div className="research-loading">
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading research reports...</p>
            </div>
          </div>
        ) : connectionStatus === 'error' && !reports.length ? (
          <div className="error-state">
            <AlertCircle size={48} />
            <h3>Connection Failed</h3>
            <p>Unable to load research reports</p>
            <button className="btn-primary" onClick={handleRefresh}>
              Retry
            </button>
          </div>
        ) : view === 'grid' ? (
          <>
            {/* Hero Section */}
            <section className="research-hero" role="region" aria-label="Research introduction">
              <div className="hero-content">
                <h2 className="hero-title">Deep Market Insights</h2>
                <p className="hero-subtitle">
                  Multi-agent research analysis and sentiment tracking
                </p>
              </div>
            </section>

            {/* Search & Filter Bar */}
            <section className="research-controls" role="search">
              <div className="search-bar">
                <Search size={18} className="search-icon" aria-hidden="true" />
                <input
                  type="text"
                  placeholder="Search research, assets, topics..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="search-input"
                  aria-label="Search research"
                />
              </div>

              <div className="controls-right">
                <div className="filter-group">
                  <Filter size={16} aria-hidden="true" />
                  <select
                    value={selectedFilter}
                    onChange={(e) => setSelectedFilter(e.target.value)}
                    className="filter-select"
                    aria-label="Filter research by status"
                  >
                    <option value="all">All Reports</option>
                    <option value="published">Published</option>
                    <option value="draft">Draft</option>
                  </select>
                </div>

                <div className="sort-group">
                  <label htmlFor="sort-select">Sort by:</label>
                  <select
                    id="sort-select"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="sort-select"
                    aria-label="Sort research reports"
                  >
                    <option value="recent">Most Recent</option>
                    <option value="confidence">Highest Confidence</option>
                    <option value="trending">Most Viewed</option>
                  </select>
                </div>
              </div>
            </section>

            {/* Results Info */}
            <section className="research-results-info" role="status" aria-live="polite">
              <div className="results-count">
                Showing <strong>{filteredReports.length}</strong> of{' '}
                <strong>{reports.length}</strong> reports
              </div>
            </section>

            {/* Research Grid */}
            {filteredReports.length > 0 ? (
              <ResearchGrid reports={filteredReports} onReportClick={handleReportClick} />
            ) : (
              <div className="empty-research">
                <BookOpen size={48} />
                <h3>No research found</h3>
                <p>Try adjusting your filters or search terms</p>
              </div>
            )}
          </>
        ) : (
          selectedReport && (
            <ResearchDetail report={selectedReport} onBack={handleBackToGrid} />
          )
        )}
      </div>
    </>
  );
};

export default Research;
