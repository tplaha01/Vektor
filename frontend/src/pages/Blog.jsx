import React, { useState, useEffect, useRef } from "react";
import { Menu, X, ArrowLeft, Share2, Bookmark, RefreshCw, AlertCircle } from "lucide-react";
import "../styles/blog.css";
import { blogAPI } from "../api/adminAPI";
import { useToast } from '../components/common/Toast';
import ConnectionIndicator from '../components/common/ConnectionIndicator';
import ToastContainer from '../components/common/Toast';

// Blog grid component
function BlogGrid({ blogs, onBlogClick, onAuthorFilter }) {
  return (
    <div className="blog-grid">
      {blogs.length === 0 ? (
        <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "40px 20px", color: "var(--txt2)" }}>
          <p>No blogs published yet. Check back soon!</p>
        </div>
      ) : (
        blogs.map(blog => (
          <article key={blog.id} className="blog-card" onClick={() => onBlogClick(blog)}>
            <div className="blog-card-header">
              <span className="blog-badge">{blog.category}</span>
              <span className="blog-date">{new Date(blog.publishedAt).toLocaleDateString()}</span>
            </div>
            <h3 className="blog-card-title">{blog.title}</h3>
            <p className="blog-card-excerpt">{blog.excerpt}</p>
            <div className="blog-card-footer">
              <div className="blog-author" onClick={(e) => { e.stopPropagation(); onAuthorFilter(blog.author); }}>
                <div className="blog-avatar">{blog.author[0]}</div>
                <span>{blog.author}</span>
              </div>
              <div className="blog-meta">
                <span className="blog-views">👁 {blog.views} views</span>
              </div>
            </div>
          </article>
        ))
      )}
    </div>
  );
}

// Blog detail component
function BlogDetail({ blog, onBack }) {
  const content = typeof blog.content === "string" ? blog.content : blog.excerpt || "No content available yet.";
  const tags = Array.isArray(blog.tags) ? blog.tags : [];
  return (
    <div className="blog-detail">
      <button className="btn-back" onClick={onBack}>
        <ArrowLeft size={16} />
        Back to blogs
      </button>

      <article className="blog-article">
        <header className="blog-article-header">
          <span className="blog-badge-lg">{blog.category}</span>
          <h1 className="blog-article-title">{blog.title}</h1>
          <p className="blog-article-meta">
            <span>{new Date(blog.publishedAt).toLocaleDateString()}</span>
            <span>•</span>
            <span>By {blog.author}</span>
            <span>•</span>
            <span>{blog.readTime} min read</span>
          </p>
        </header>

        <div className="blog-article-content">
          {content.split("\n\n").map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
        </div>

        <footer className="blog-article-footer">
          <div className="blog-actions">
            <button className="btn-action">
              <Share2 size={16} />
              Share
            </button>
            <button className="btn-action">
              <Bookmark size={16} />
              Save
            </button>
          </div>
          <div className="blog-tags">
            {tags.map(tag => (
              <span key={tag} className="blog-tag">#{tag}</span>
            ))}
          </div>
        </footer>
      </article>

      {/* Related blogs */}
      <section className="related-blogs">
        <h2>Related Blogs</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "16px", marginTop: "16px" }}>
          {/* Placeholder for related blogs - would fetch from API */}
          <div style={{ padding: "16px", background: "var(--bg1)", borderRadius: "8px", color: "var(--txt3)" }}>
            Loading related blogs...
          </div>
        </div>
      </section>
    </div>
  );
}

export default function Blog() {
  const [blogs, setBlogs] = useState([]);
  const [selectedBlog, setSelectedBlog] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  // Fetch blogs - simple, clean logic
  useEffect(() => {
    isMounted.current = true;
    
    const fetchBlogs = async () => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;
      
      try {
        if (!blogs.length) {
          setConnectionStatus('connecting');
        }
        
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout')), 15000)
        );
        
        const data = await Promise.race([
          blogAPI.getPosts({ limit: 50 }),
          timeoutPromise
        ]);
        
        if (!isMounted.current) return;
        
        setBlogs(data.blogs || []);
        setConnectionStatus('connected');
        setLastUpdate(new Date());
        setLoading(false);
      } catch (err) {
        if (!isMounted.current) return;
        
        console.error('Failed to fetch blogs:', err);
        if (connectionStatus === 'connecting') {
          setConnectionStatus('error');
        }
        setLoading(false);
        showError(`Failed to load blogs: ${err.message}`);
        setBlogs([]);
      } finally {
        fetchInProgress.current = false;
      }
    };
    
    fetchBlogs();
    const interval = setInterval(fetchBlogs, 30000);
    
    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, []);

  const handleBlogClick = async (blog) => {
    if (!blog?.id) {
      setSelectedBlog(blog);
      return;
    }
    try {
      const detail = await blogAPI.getPostDetail(blog.id);
      setSelectedBlog(detail || blog);
      success("Blog loaded successfully");
    } catch (error) {
      console.warn("Error fetching blog detail:", error);
      setSelectedBlog(blog);
      showError(`Failed to load blog: ${error.message}`);
    }
  };

  const handleRefresh = () => {
    setLoading(true);
    setTimeout(() => {
      setConnectionStatus('connected');
      setLoading(false);
      success('Blog feed refreshed');
    }, 800);
  };

  // Filter blogs
  const filteredBlogs = blogs
    .filter(b => categoryFilter === "all" || b.category === categoryFilter)
    .filter(b => b.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                 b.excerpt.toLowerCase().includes(searchTerm.toLowerCase()));

  const categories = ["all", ...new Set(blogs.map(b => b.category))];

  if (selectedBlog) {
    return (
      <>
        <ToastContainer />
        <BlogDetail blog={selectedBlog} onBack={() => setSelectedBlog(null)} />
      </>
    );
  }

  return (
    <>
      <ToastContainer />
      <div className="blog-page">
        {/* Header */}
        <header className="blog-header" role="banner">
          <div className="blog-header-content">
            <div className="blog-logo">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h16M4 18h8" stroke="var(--purple)" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <span>Blog</span>
            </div>

            <div className="header-controls">
              <ConnectionIndicator 
                status={connectionStatus}
                lastUpdate={lastUpdate}
              />
              <button 
                className="btn-refresh-blog"
                onClick={handleRefresh}
                disabled={loading}
                aria-label="Refresh blog"
              >
                <RefreshCw size={18} className={loading ? 'spinning' : ''} />
              </button>
              <button 
                className="menu-toggle" 
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
              >
                {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
            </div>
          </div>

          {/* Hero */}
          <div className="blog-hero">
            <h1>Market Insights & Trading Research</h1>
            <p>Daily updates from our AI-native fund's research agents</p>
          </div>

          {/* Search */}
          <div className="blog-search-bar">
            <input
              type="text"
              placeholder="Search blogs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="blog-search-input"
              aria-label="Search blogs"
            />
          </div>
        </header>

        {/* Main content */}
        <main className="blog-main">
          {/* Sidebar filters */}
          <aside className={`blog-sidebar ${sidebarOpen ? "open" : ""}`} role="complementary">
            <div className="filter-section">
              <h3>Categories</h3>
              <div className="filter-list">
                {categories.map(cat => (
                  <button
                    key={cat}
                    className={`filter-btn ${categoryFilter === cat ? "active" : ""}`}
                    onClick={() => { setCategoryFilter(cat); setSidebarOpen(false); }}
                    aria-current={categoryFilter === cat ? "page" : undefined}
                  >
                    {cat === "all" ? "All Posts" : cat}
                  </button>
                ))}
              </div>
            </div>

            <div className="divider" />

            <div className="filter-section">
              <h3>Stats</h3>
              <div className="stats-list">
                <div className="stat">
                  <span className="stat-label">Total Posts</span>
                  <span className="stat-value">{blogs.length}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">This Month</span>
                  <span className="stat-value">{blogs.filter(b => isThisMonth(b.publishedAt)).length}</span>
                </div>
              </div>
            </div>
          </aside>

          {/* Blog grid */}
          <section className="blog-content" role="main">
            {loading ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Loading blogs...</p>
              </div>
            ) : connectionStatus === 'error' && !blogs.length ? (
              <div className="error-state">
                <AlertCircle size={48} />
                <h3>Connection Failed</h3>
                <p>Unable to load blog posts</p>
                <button className="btn-primary" onClick={handleRefresh}>
                  Retry
                </button>
              </div>
            ) : (
              <>
                <div className="blog-header-info">
                  <h2>Latest Posts ({filteredBlogs.length})</h2>
                </div>
                <BlogGrid
                  blogs={filteredBlogs}
                  onBlogClick={handleBlogClick}
                  onAuthorFilter={() => {
                    // Could add author filter if needed
                  }}
                />
              </>
            )}
          </section>
        </main>
      </div>
    </>
  );
}

// Helper function
function isThisMonth(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
}
