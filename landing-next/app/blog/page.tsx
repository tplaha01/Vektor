"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { blogPostsData } from "./data";
import { SiteFooter, SiteHeader } from "../../components/site-chrome";

interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string;
  tags?: string[];
  featured?: boolean;
  readTime?: number;
  author?: string;
}

const posts = Object.values(blogPostsData) as BlogPost[];

const formatDate = (date: string) =>
  new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

export default function BlogPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>("All");

  useEffect(() => {
    document.title = "Research | Vektor";

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
    return () => observer.disconnect();
  }, []);

  const sortedPosts = useMemo(
    () =>
      [...posts].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
      ),
    []
  );

  const tags = useMemo(
    () => [
      "All",
      ...Array.from(new Set(sortedPosts.flatMap((post) => post.tags || []))),
    ],
    [sortedPosts]
  );

  const filteredPosts = useMemo(() => {
    if (selectedCategory === "All") {
      return sortedPosts;
    }

    return sortedPosts.filter((post) => post.tags?.includes(selectedCategory));
  }, [selectedCategory, sortedPosts]);

  const [featuredPost, ...remainingPosts] = filteredPosts;

  return (
    <>
      <SiteHeader active="blog" />

      <main className="page-shell overflow-hidden">
        <section className="container page-masthead cinematic-fade">
          <p className="page-kicker">Research and operating notes</p>
          <h1>Briefs that explain what the system is seeing and why it matters.</h1>
          <p>
            The blog mirrors the product philosophy: readable analysis, explicit tradeoffs, and a
            tighter connection between research, risk, and operating discipline.
          </p>
        </section>

        <section className="container cinematic-fade" style={{ marginBottom: "28px" }}>
          <div className="filter-panel">
            <div className="filter-row">
              {tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className={`filter-chip${selectedCategory === tag ? " is-active" : ""}`}
                  onClick={() => setSelectedCategory(tag)}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="container cinematic-fade">
          {featuredPost ? (
            <div className="blog-featured">
              <article className="post-card" style={{ gridColumn: "span 7" }}>
                <div className="post-tags">
                  {(featuredPost.tags || []).slice(0, 2).map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
                <div>
                  <p className="post-eyebrow">Featured note</p>
                  <h2 className="section-title" style={{ marginTop: "0.35rem", fontSize: "clamp(2.1rem, 4vw, 3.6rem)" }}>
                    {featuredPost.title}
                  </h2>
                  <p className="post-description" style={{ marginTop: "16px", fontSize: "1.04rem" }}>
                    {featuredPost.description}
                  </p>
                </div>
                <div className="meta-strip">
                  <span>{featuredPost.author || "Vektor Team"}</span>
                  <span>{featuredPost.readTime || 5} min read</span>
                  <span>{formatDate(featuredPost.date)}</span>
                </div>
                <div className="article-nav">
                  <Link className="btn primary" href={`/blog/${featuredPost.slug}`}>
                    Read the feature
                  </Link>
                  <Link className="btn ghost" href="/how-it-works">
                    Review the operating model
                  </Link>
                </div>
              </article>

              <aside className="hero-panel" style={{ gridColumn: "span 5" }}>
                <p className="panel-label">Editorial lens</p>
                <h2 className="panel-title">What shows up here</h2>
                <ul className="detail-list">
                  <li>Research explains the market setup before it talks about action.</li>
                  <li>Notes stay short enough to scan, but precise enough to audit later.</li>
                  <li>Categories align with how Vektor groups market work inside the product.</li>
                </ul>
              </aside>
            </div>
          ) : null}
        </section>

        <section className="section cinematic-fade" style={{ paddingTop: "24px" }}>
          <div className="container">
            <div className="section-head">
              <p className="section-kicker">Archive</p>
              <h2 className="section-title">Latest writing</h2>
            </div>

            <div className="blog-grid">
              {remainingPosts.map((post) => (
                <article key={post.slug} className="post-card" style={{ gridColumn: "span 4" }}>
                  <div className="post-tags">
                    {(post.tags || []).slice(0, 2).map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div>
                    <h3>{post.title}</h3>
                    <p className="post-description" style={{ marginTop: "14px" }}>
                      {post.description}
                    </p>
                  </div>
                  <div className="meta-strip">
                    <span>{post.author || "Vektor Team"}</span>
                    <span>{post.readTime || 5} min</span>
                    <span>{formatDate(post.date)}</span>
                  </div>
                  <Link href={`/blog/${post.slug}`} className="btn ghost">
                    Open article
                  </Link>
                </article>
              ))}
            </div>

            {filteredPosts.length === 0 ? (
              <div className="article-shell" style={{ marginTop: "24px", textAlign: "center" }}>
                <h2 style={{ marginTop: 0 }}>No articles in this category yet.</h2>
                <p className="section-copy" style={{ marginInline: "auto" }}>
                  Try another filter or return to the full archive.
                </p>
                <div className="hero-actions" style={{ justifyContent: "center" }}>
                  <button type="button" className="btn primary" onClick={() => setSelectedCategory("All")}>
                    Show all research
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </main>

      <SiteFooter
        eyebrow="Vektor research"
        description="Briefs, architecture notes, and operating context from the same stack that runs the simulated and live workflows."
      />
    </>
  );
}
