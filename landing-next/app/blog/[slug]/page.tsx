"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ThemeSwitcher from "../../ThemeSwitcher";
import { blogPostsData } from "../data";
import ReactMarkdown from "react-markdown";

const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default function BlogPost({ params }: PageProps) {
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [slug, setSlug] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { slug: paramSlug } = await params;
        setSlug(paramSlug);
        
        const foundPost = blogPostsData[paramSlug];
        setPost(foundPost || null);
      } catch (error) {
        console.error('Error loading post:', error);
      }
      setLoading(false);
    })();

    // Scroll to top
    window.scrollTo(0, 0);

    // Animation observer
    const nodes = Array.from(document.querySelectorAll(".cinematic-fade"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [params]);

  if (loading) {
    return (
      <>
        <header className="topbar">
          <div className="container topbar-inner">
            <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: 32 }} />
            <span>Vektor <em>Blog</em></span>
          </a>
            <nav className="hero-actions" style={{ alignItems: 'center' }}>
              <Link className="btn ghost" href="/blog">Back to Blog</Link>
              <div style={{ width: '1px', height: '24px', background: 'var(--line)', margin: '0 8px' }} />
              <ThemeSwitcher />
            </nav>
          </div>
        </header>
        <main className="container" style={{ padding: '120px 24px', textAlign: 'center', color: 'var(--muted)' }}>
          Loading article...
        </main>
      </>
    );
  }

  if (!post) {
    return (
      <>
        <header className="topbar">
          <div className="container topbar-inner">
            <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: 32 }} />
            <span>Vektor <em>Blog</em></span>
          </a>
            <nav className="hero-actions" style={{ alignItems: 'center' }}>
              <Link className="btn ghost" href="/blog">Back to Blog</Link>
              <div style={{ width: '1px', height: '24px', background: 'var(--line)', margin: '0 8px' }} />
              <ThemeSwitcher />
            </nav>
          </div>
        </header>
        <main className="container" style={{ padding: '120px 24px', textAlign: 'center' }}>
          <h1>Article Not Found</h1>
          <p style={{ color: 'var(--muted)', marginBottom: '24px' }}>Sorry, we couldn't find that article.</p>
          <Link className="btn primary" href="/blog">Back to Blog</Link>
        </main>
      </>
    );
  }

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <a href="/" className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img src="/VektorLogo.png" alt="Vektor Logo" style={{ height: 32 }} />
            <span>Vektor <em>Blog</em></span>
          </a>
          <nav className="hero-actions" style={{ alignItems: 'center' }}>
            <Link className="btn ghost" href="/blog">Back to Blog</Link>
            <a className="btn primary" href={`${productUrl}/admin`}>Admin Console</a>
            <div style={{ width: '1px', height: '24px', background: 'var(--line)', margin: '0 8px' }} />
            <ThemeSwitcher />
          </nav>
        </div>
      </header>

      <main className="container" style={{ padding: '80px 24px' }}>
        <article className="cinematic-fade" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div style={{ marginBottom: '40px' }}>
            <span style={{ fontSize: '12px', color: 'var(--accent)', textTransform: 'uppercase', fontWeight: '600', letterSpacing: '0.1em' }}>
              {post.tags?.[0] || 'Blog'}
            </span>
            <h1 style={{ fontSize: 'clamp(32px, 5vw, 48px)', marginTop: '12px', marginBottom: '16px', letterSpacing: '-0.03em' }}>
              {post.title}
            </h1>
            <p style={{ color: 'var(--muted)', fontSize: '16px', marginBottom: '24px' }}>
              {post.description}
            </p>
            <div style={{ display: 'flex', gap: '24px', color: 'var(--muted)', fontSize: '14px', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', padding: '16px 0' }}>
              <span>By {post.author}</span>
              <span>{post.readTime} min read</span>
              <span>{new Date(post.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            </div>
          </div>

          <div style={{ fontSize: '16px', lineHeight: '1.8', color: 'var(--text)', marginBottom: '60px' }} className="blog-content">
            <ReactMarkdown
              components={{
                h1: ({node, ...props}) => <h1 style={{ fontSize: '28px', fontWeight: '600', marginTop: '40px', marginBottom: '20px' }} {...props} />,
                h2: ({node, ...props}) => <h2 style={{ fontSize: '24px', fontWeight: '600', marginTop: '32px', marginBottom: '16px' }} {...props} />,
                h3: ({node, ...props}) => <h3 style={{ fontSize: '20px', fontWeight: '600', marginTop: '24px', marginBottom: '12px' }} {...props} />,
                p: ({node, ...props}) => <p style={{ marginBottom: '16px', lineHeight: '1.8' }} {...props} />,
                ul: ({node, ...props}) => <ul style={{ marginLeft: '24px', marginBottom: '16px', listStyle: 'disc' }} {...props} />,
                ol: ({node, ...props}) => <ol style={{ marginLeft: '24px', marginBottom: '16px', listStyle: 'decimal' }} {...props} />,
                li: ({node, ...props}) => <li style={{ marginBottom: '8px' }} {...props} />,
                code: ({node, inline, ...props}) => inline 
                  ? <code style={{ background: 'var(--surface)', padding: '2px 6px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '14px' }} {...props} />
                  : <code style={{ background: 'var(--surface)', padding: '12px', borderRadius: '6px', display: 'block', overflow: 'auto', marginBottom: '16px', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.5' }} {...props} />,
                pre: ({node, ...props}) => <pre style={{ background: 'var(--surface)', padding: '16px', borderRadius: '6px', marginBottom: '16px', overflow: 'auto' }} {...props} />,
                blockquote: ({node, ...props}) => <blockquote style={{ borderLeft: '4px solid var(--accent)', paddingLeft: '16px', marginLeft: '0', marginBottom: '16px', color: 'var(--muted)', fontStyle: 'italic' }} {...props} />,
                a: ({node, ...props}) => <a style={{ color: 'var(--accent)', textDecoration: 'underline' }} {...props} />,
              }}
            >
              {post.content}
            </ReactMarkdown>
          </div>

          <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', paddingTop: '40px', borderTop: '1px solid var(--line)' }}>
            <Link className="btn ghost" href="/blog">← Back to Blog</Link>
            <a className="btn primary" href={`${productUrl}/admin`}>Open Admin Console →</a>
          </div>
        </article>
      </main>

      <footer className="footer">
        <div className="container">
           <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Vektor Fund OS • Research & Insights</span>
              <div style={{display: 'flex', gap: '24px'}}>
                 <Link href="/">Home</Link>
                 <Link href="/blog">Blog</Link>
                 <a href={productUrl}>PnL</a>
              </div>
           </div>
        </div>
      </footer>
    </>
  );
}
