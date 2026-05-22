"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { blogPostsData } from "../data";
import { SiteFooter, SiteHeader } from "../../../components/site-chrome";

interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string;
  tags?: string[];
  readTime?: number;
  author?: string;
  content: string;
}

interface PageProps {
  params: Promise<{ slug: string }>;
}

const allPosts = Object.values(blogPostsData) as BlogPost[];
const productUrl = process.env.NEXT_PUBLIC_PRODUCT_APP_URL || "http://localhost:9000";

const formatDate = (date: string) =>
  new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

export default function BlogPostPage({ params }: PageProps) {
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const { slug: resolvedSlug } = await params;
        if (cancelled) return;
        setPost((blogPostsData as Record<string, BlogPost>)[resolvedSlug] || null);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    window.scrollTo(0, 0);

    const nodes = Array.from(document.querySelectorAll(".cinematic-fade"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    nodes.forEach((node) => observer.observe(node));

    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, [params]);

  useEffect(() => {
    if (post) {
      document.title = `${post.title} | Vektor Research`;
    }
  }, [post]);

  const relatedPosts = useMemo(() => {
    if (!post) return [];

    return allPosts
      .filter((candidate) => candidate.slug !== post.slug)
      .map((candidate) => {
        const overlap = (candidate.tags || []).filter((tag) => post.tags?.includes(tag)).length;
        return { candidate, overlap };
      })
      .sort((a, b) => {
        if (a.overlap !== b.overlap) {
          return b.overlap - a.overlap;
        }
        return new Date(b.candidate.date).getTime() - new Date(a.candidate.date).getTime();
      })
      .slice(0, 3)
      .map(({ candidate }) => candidate);
  }, [post]);

  if (loading) {
    return (
      <>
        <SiteHeader active="blog" />
        <main className="page-shell">
          <section className="container article-shell" style={{ textAlign: "center" }}>
            <h1 style={{ marginTop: 0 }}>Loading article...</h1>
          </section>
        </main>
      </>
    );
  }

  if (!post) {
    return (
      <>
        <SiteHeader active="blog" />
        <main className="page-shell">
          <section className="container article-shell" style={{ textAlign: "center" }}>
            <p className="page-kicker">Research archive</p>
            <h1 style={{ marginTop: 0 }}>Article not found.</h1>
            <p className="section-copy" style={{ marginInline: "auto" }}>
              The requested article does not exist or may have moved.
            </p>
            <div className="hero-actions" style={{ justifyContent: "center" }}>
              <Link className="btn primary" href="/blog">
                Back to research
              </Link>
            </div>
          </section>
        </main>
        <SiteFooter eyebrow="Vektor research" />
      </>
    );
  }

  const content = post.content.replace(/^#\s.+?\n+/, "");

  return (
    <>
      <SiteHeader active="blog" />

      <main className="page-shell overflow-hidden">
        <section className="container page-masthead cinematic-fade">
          <div className="post-tags">
            {(post.tags || []).map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
          <h1 className="article-title" style={{ marginTop: "18px" }}>
            {post.title}
          </h1>
          <p className="article-dek">{post.description}</p>
          <div className="meta-strip" style={{ marginTop: "18px" }}>
            <span>{post.author || "Vektor Team"}</span>
            <span>{post.readTime || 5} min read</span>
            <span>{formatDate(post.date)}</span>
          </div>
        </section>

        <section className="container cinematic-fade">
          <article className="article-shell">
            <div className="article-header">
              <div className="article-nav">
                <Link className="btn ghost" href="/blog">
                  Back to research
                </Link>
                <a className="btn primary" href={`${productUrl}/admin`}>
                  Open admin console
                </a>
              </div>
            </div>

            <div className="article-content">
              <ReactMarkdown
                components={{
                  h1: ({ node, ...props }) => <h1 {...props} />,
                  h2: ({ node, ...props }) => <h2 {...props} />,
                  h3: ({ node, ...props }) => <h3 {...props} />,
                  p: ({ node, ...props }) => <p {...props} />,
                  ul: ({ node, ...props }) => <ul {...props} />,
                  ol: ({ node, ...props }) => <ol {...props} />,
                  li: ({ node, ...props }) => <li {...props} />,
                  code: ({ node, ...props }) => <code {...props} />,
                  pre: ({ node, ...props }) => <pre {...props} />,
                  blockquote: ({ node, ...props }) => <blockquote {...props} />,
                  a: ({ node, ...props }) => <a {...props} />,
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          </article>
        </section>

        {relatedPosts.length > 0 ? (
          <section className="section cinematic-fade" style={{ paddingTop: "42px" }}>
            <div className="container">
              <div className="section-head">
                <p className="section-kicker">Keep reading</p>
                <h2 className="section-title">More from the research archive</h2>
              </div>
              <div className="blog-grid">
                {relatedPosts.map((related) => (
                  <article key={related.slug} className="post-card" style={{ gridColumn: "span 4" }}>
                    <div className="post-tags">
                      {(related.tags || []).slice(0, 2).map((tag) => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div>
                      <h3>{related.title}</h3>
                      <p className="post-description" style={{ marginTop: "14px" }}>
                        {related.description}
                      </p>
                    </div>
                    <div className="meta-strip">
                      <span>{formatDate(related.date)}</span>
                      <span>{related.readTime || 5} min</span>
                    </div>
                    <Link href={`/blog/${related.slug}`} className="btn ghost">
                      Read article
                    </Link>
                  </article>
                ))}
              </div>
            </div>
          </section>
        ) : null}
      </main>

      <SiteFooter
        eyebrow="Vektor research"
        description={`Article: ${post.title}. Explore the rest of the archive for more operating notes and market context.`}
      />
    </>
  );
}
