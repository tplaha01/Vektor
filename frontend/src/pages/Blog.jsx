import React, { useState, useEffect, useRef } from "react";
import { Menu, X, ArrowLeft, Share2, Bookmark, RefreshCw, AlertCircle } from "lucide-react";
import "../styles/blog.css";
import { blogAPI } from "../api/adminAPI";
import { useToast } from "../components/common/Toast";
import ConnectionIndicator from "../components/common/ConnectionIndicator";
import ToastContainer from "../components/common/Toast";

function renderMarkdownSimple(content) {
  const rows = String(content || "").split("\n");
  const rendered = [];
  let bulletBuffer = [];
  let codeBlockBuffer = [];
  let inCodeBlock = false;
  let key = 0;

  const flushBullets = () => {
    if (!bulletBuffer.length) return;
    rendered.push(
      <ul key={`ul-${key++}`} className="blog-article-list">
        {bulletBuffer.map((item, idx) => (
          <li key={`li-${idx}`}>{item}</li>
        ))}
      </ul>
    );
    bulletBuffer = [];
  };

  const flushCodeBlock = () => {
    if (!codeBlockBuffer.length) return;
    rendered.push(
      <pre key={`code-${key++}`} className="blog-code-block">
        <code>{codeBlockBuffer.join("\n")}</code>
      </pre>
    );
    codeBlockBuffer = [];
  };

  const parseInlineMarkdown = (text) => {
    // Parse bold **text**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Parse italic *text* or _text_
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.*?)_/g, '<em>$1</em>');
    // Parse links [text](url)
    text = text.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // Parse inline code `text`
    text = text.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>');
    return <span dangerouslySetInnerHTML={{ __html: text }} />;
  };

  for (const rawLine of rows) {
    const line = rawLine.trim();

    // Handle code blocks
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockBuffer.push(rawLine);
      continue;
    }

    if (!line) {
      flushBullets();
      continue;
    }

    // Headers
    if (line.startsWith("# ")) {
      flushBullets();
      rendered.push(<h1 key={`h1-${key++}`}>{parseInlineMarkdown(line.replace(/^#\s+/, ""))}</h1>);
      continue;
    }
    if (line.startsWith("## ")) {
      flushBullets();
      rendered.push(<h2 key={`h2-${key++}`}>{parseInlineMarkdown(line.replace(/^##\s+/, ""))}</h2>);
      continue;
    }
    if (line.startsWith("### ")) {
      flushBullets();
      rendered.push(<h3 key={`h3-${key++}`}>{parseInlineMarkdown(line.replace(/^###\s+/, ""))}</h3>);
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      flushBullets();
      rendered.push(
        <blockquote key={`bq-${key++}`} className="blog-blockquote">
          {parseInlineMarkdown(line.replace(/^>\s+/, ""))}
        </blockquote>
      );
      continue;
    }

    // Bullet list
    if (line.startsWith("- ")) {
      bulletBuffer.push(line.replace(/^-\s+/, ""));
      continue;
    }

    // Numbered list
    if (line.match(/^\d+\.\s/)) {
      bulletBuffer.push(line.replace(/^\d+\.\s+/, ""));
      continue;
    }

    flushBullets();
    rendered.push(<p key={`p-${key++}`}>{parseInlineMarkdown(line)}</p>);
  }

  flushBullets();
  flushCodeBlock();
  return rendered;
}

function BlogGrid({ blogs, onBlogClick, onAuthorFilter }) {
  return (
    <div className="blog-grid">
      {blogs.length === 0 ? (
        <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "40px 20px", color: "var(--txt2)" }}>
          <p>No blogs published yet. Check back soon!</p>
        </div>
      ) : (
        blogs.map((blog) => (
          <article key={blog.id} className="blog-card" onClick={() => onBlogClick(blog)}>
            {blog.heroImageUrl ? (
              <div className="blog-card-image-wrap">
                <img src={blog.heroImageUrl} alt={blog.title} className="blog-card-image" loading="lazy" />
              </div>
            ) : null}
            <div className="blog-card-header">
              <span className="blog-badge">{blog.category}</span>
              <span className="blog-date">{new Date(blog.publishedAt).toLocaleDateString()}</span>
            </div>
            <h3 className="blog-card-title">{blog.title}</h3>
            <p className="blog-card-excerpt">{blog.excerpt}</p>
            <div className="blog-card-footer">
              <div
                className="blog-author"
                onClick={(event) => {
                  event.stopPropagation();
                  onAuthorFilter(blog.author);
                }}
              >
                <div className="blog-avatar">{String(blog.author || "V").slice(0, 1)}</div>
                <span>{blog.author}</span>
              </div>
              <div className="blog-meta">
                <span className="blog-views">{blog.views} views</span>
              </div>
            </div>
          </article>
        ))
      )}
    </div>
  );
}

function BlogDetail({ blog, onBack, blogs, onBlogClick }) {
  const content = typeof blog.content === "string" ? blog.content : blog.excerpt || "No content available yet.";
  const tags = Array.isArray(blog.tags) ? blog.tags : [];
  const heroImage = blog.heroImageUrl || blog?.metadata?.hero_image_url || null;
  const { success, error: showError } = useToast();

  const handleShare = async () => {
    try {
      const blogUrl = `${window.location.origin}/blog?id=${blog.id}`;
      if (navigator.share) {
        // Native share for mobile
        await navigator.share({
          title: blog.title,
          text: blog.excerpt,
          url: blogUrl,
        });
      } else {
        // Fallback: copy to clipboard
        await navigator.clipboard.writeText(blogUrl);
        success('Blog link copied to clipboard!');
      }
    } catch (err) {
      console.error('Share error:', err);
      showError('Failed to share blog');
    }
  };

  const handleSave = async () => {
    try {
      // Save to localStorage for bookmarks
      const saved = JSON.parse(localStorage.getItem('savedBlogs') || '[]');
      const exists = saved.some(b => b.id === blog.id);
      
      if (exists) {
        // Remove if already saved
        const filtered = saved.filter(b => b.id !== blog.id);
        localStorage.setItem('savedBlogs', JSON.stringify(filtered));
        success('Blog removed from saved');
      } else {
        // Add to saved
        saved.push({ id: blog.id, title: blog.title, savedAt: new Date().toISOString() });
        localStorage.setItem('savedBlogs', JSON.stringify(saved));
        success('Blog saved for later!');
      }
    } catch (err) {
      console.error('Save error:', err);
      showError('Failed to save blog');
    }
  };

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
            <span>|</span>
            <span>By {blog.author}</span>
            <span>|</span>
            <span>{blog.readTime} min read</span>
          </p>
        </header>

        {heroImage ? (
          <div className="blog-hero-image-wrap">
            <img src={heroImage} alt={blog.title} className="blog-hero-image" loading="lazy" />
          </div>
        ) : null}

        <div className="blog-article-content">{renderMarkdownSimple(content)}</div>

        <footer className="blog-article-footer">
          <div className="blog-actions">
            <button className="btn-action" onClick={handleShare} title="Share this blog">
              <Share2 size={16} />
              Share
            </button>
            <button className="btn-action" onClick={handleSave} title="Save this blog for later">
              <Bookmark size={16} />
              Save
            </button>
          </div>
          <div className="blog-tags">
            {tags.map((tag) => (
              <span key={tag} className="blog-tag">
                #{tag}
              </span>
            ))}
          </div>
        </footer>
      </article>

      <section className="related-blogs">
        <h2>Related Blogs</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "16px", marginTop: "16px" }}>
          {blogs
            .filter(b => b.id !== blog.id && (b.category === blog.category || b.tags?.some(t => blog.tags?.includes(t))))
            .slice(0, 3)
            .map(relatedBlog => (
              <article 
                key={relatedBlog.id}
                className="blog-card" 
                onClick={() => onBlogClick(relatedBlog)}
                style={{ cursor: 'pointer' }}
              >
                {relatedBlog.heroImageUrl ? (
                  <div className="blog-card-image-wrap">
                    <img src={relatedBlog.heroImageUrl} alt={relatedBlog.title} className="blog-card-image" loading="lazy" />
                  </div>
                ) : null}
                <div className="blog-card-header">
                  <span className="blog-badge">{relatedBlog.category}</span>
                </div>
                <h3 className="blog-card-title">{relatedBlog.title}</h3>
                <p className="blog-card-excerpt">{relatedBlog.excerpt}</p>
              </article>
            ))}
          {blogs.filter(b => b.id !== blog.id && (b.category === blog.category || b.tags?.some(t => blog.tags?.includes(t)))).length === 0 && (
            <div style={{ padding: "16px", background: "var(--bg1)", borderRadius: "8px", color: "var(--txt3)", gridColumn: "1/-1" }}>
              No related blogs found
            </div>
          )}
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
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const { success, error: showError } = useToast();
  const fetchInProgress = useRef(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;

    const fetchBlogs = async () => {
      if (fetchInProgress.current) return;
      fetchInProgress.current = true;

      try {
        if (!blogs.length) {
          setConnectionStatus("connecting");
        }

        const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error("Request timeout")), 15000));
        const data = await Promise.race([blogAPI.getPosts({ limit: 50 }), timeoutPromise]);
        if (!isMounted.current) return;

        setBlogs(data.blogs || []);
        setConnectionStatus("connected");
        setLastUpdate(new Date());
        setLoading(false);
      } catch (err) {
        if (!isMounted.current) return;
        console.error("Failed to fetch blogs:", err);
        if (connectionStatus === "connecting") {
          setConnectionStatus("error");
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
      setConnectionStatus("connected");
      setLoading(false);
      success("Blog feed refreshed");
    }, 800);
  };

  const filteredBlogs = blogs
    .filter((item) => categoryFilter === "all" || item.category === categoryFilter)
    .filter(
      (item) =>
        item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.excerpt.toLowerCase().includes(searchTerm.toLowerCase())
    );
  const categories = ["all", ...new Set(blogs.map((item) => item.category))];

  if (selectedBlog) {
    return (
      <>
        <ToastContainer />
        <BlogDetail blog={selectedBlog} onBack={() => setSelectedBlog(null)} blogs={blogs} onBlogClick={handleBlogClick} />
      </>
    );
  }

  return (
    <>
      <ToastContainer />
      <div className="blog-page">
        <header className="blog-header" role="banner">
          <div className="blog-header-content">
            <div className="blog-logo">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h16M4 18h8" stroke="var(--purple)" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <span>Blog</span>
            </div>

            <div className="header-controls">
              <ConnectionIndicator status={connectionStatus} lastUpdate={lastUpdate} />
              <button className="btn-refresh-blog" onClick={handleRefresh} disabled={loading} aria-label="Refresh blog">
                <RefreshCw size={18} className={loading ? "spinning" : ""} />
              </button>
              <button className="menu-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
                {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
            </div>
          </div>

          <div className="blog-hero">
            <h1>Market Insights & Trading Research</h1>
            <p>Daily updates from our AI-native fund research agents</p>
          </div>

          <div className="blog-search-bar">
            <input
              type="text"
              placeholder="Search blogs..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="blog-search-input"
              aria-label="Search blogs"
            />
          </div>
        </header>

        <main className="blog-main">
          <aside className={`blog-sidebar ${sidebarOpen ? "open" : ""}`} role="complementary">
            <div className="filter-section">
              <h3>Categories</h3>
              <div className="filter-list">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    className={`filter-btn ${categoryFilter === cat ? "active" : ""}`}
                    onClick={() => {
                      setCategoryFilter(cat);
                      setSidebarOpen(false);
                    }}
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
                  <span className="stat-value">{blogs.filter((item) => isThisMonth(item.publishedAt)).length}</span>
                </div>
              </div>
            </div>
          </aside>

          <section className="blog-content" role="main">
            {loading ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Loading blogs...</p>
              </div>
            ) : connectionStatus === "error" && !blogs.length ? (
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
                <BlogGrid blogs={filteredBlogs} onBlogClick={handleBlogClick} onAuthorFilter={() => {}} />
              </>
            )}
          </section>
        </main>
      </div>
    </>
  );
}

function isThisMonth(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
}
