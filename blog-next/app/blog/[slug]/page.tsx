import { getBlogPostBySlug } from "@/lib/blog-loader";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import React from "react";

import { FlickeringGrid } from "@/components/magicui/flickering-grid";
import { HashScrollHandler } from "@/components/hash-scroll-handler";
import { siteConfig } from "@/lib/site";

interface PageProps {
  params: Promise<{ slug: string }>;
}

const formatDate = (date: Date): string => {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

export default async function BlogPost({ params }: PageProps) {
  const { slug } = await params;

  if (!slug || slug.length === 0) {
    notFound();
  }

  const post = await getBlogPostBySlug(slug);

  if (!post) {
    notFound();
  }

  const date = new Date(post.date);
  const formattedDate = formatDate(date);
  const tags = Array.isArray(post.tags)
    ? post.tags
    : post.tags
      ? [post.tags]
      : [];

  return (
    <div className="relative min-h-screen bg-background">
      <HashScrollHandler />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[320px] [mask-image:linear-gradient(to_top,transparent_18%,black_88%)]">
        <FlickeringGrid
          className="absolute inset-0 size-full"
          squareSize={4}
          gridGap={6}
          color="#6B7280"
          maxOpacity={0.18}
          flickerChance={0.12}
        />
      </div>

      <section className="relative z-10 border-b border-border/70">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-10 lg:py-14">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Button variant="outline" asChild className="rounded-full bg-card/60">
              <Link href="/">
                <ArrowLeft data-icon="inline-start" />
                Back to archive
              </Link>
            </Button>
            {tags.map((tag: string) => (
              <span
                key={tag}
                className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary"
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(260px,0.45fr)] lg:items-end">
            <div className="flex flex-col gap-5">
              <h1 className="max-w-5xl text-4xl font-semibold tracking-[-0.08em] text-balance sm:text-5xl lg:text-7xl">
                {post.title}
              </h1>
              {post.description ? (
                <p className="max-w-3xl text-base leading-7 text-muted-foreground md:text-lg">
                  {post.description}
                </p>
              ) : null}
            </div>

            <aside className="rounded-[28px] border border-border bg-card/60 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.15)] backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">Article facts</p>
              <dl className="mt-5 grid gap-4 text-sm">
                <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
                  <dt className="text-muted-foreground">Published</dt>
                  <dd className="font-medium text-foreground">{formattedDate}</dd>
                </div>
                {post.author ? (
                  <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
                    <dt className="text-muted-foreground">Author</dt>
                    <dd className="font-medium text-foreground">{post.author}</dd>
                  </div>
                ) : null}
                {post.readTime ? (
                  <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-3">
                    <dt className="text-muted-foreground">Read time</dt>
                    <dd className="font-medium text-foreground">{post.readTime} min</dd>
                  </div>
                ) : null}
                <div className="flex flex-col gap-3 pt-1">
                  <a
                    href={`${siteConfig.links.product}/admin`}
                    className="inline-flex min-h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5"
                  >
                    Open admin console
                  </a>
                  <a
                    href={siteConfig.links.product}
                    className="inline-flex min-h-11 items-center justify-center rounded-full border border-border bg-background/70 px-5 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
                  >
                    View live PnL
                  </a>
                </div>
              </dl>
            </aside>
          </div>
        </div>
      </section>

      <section className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-8 lg:py-10">
        {post.thumbnail ? (
          <div className="relative h-[260px] overflow-hidden rounded-[32px] border border-border bg-card/60 sm:h-[360px] lg:h-[520px]">
            <Image
              src={post.thumbnail}
              alt={post.title}
              fill
              priority
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-background/65 via-transparent to-transparent" />
          </div>
        ) : null}

        <article className="overflow-hidden rounded-[32px] border border-border bg-card/55 shadow-[0_24px_70px_rgba(0,0,0,0.16)] backdrop-blur-sm">
          <div className="px-6 py-8 lg:px-10 lg:py-10">
            <div className="vektor-prose max-w-none prose prose-lg dark:prose-invert prose-headings:font-semibold prose-headings:text-balance prose-headings:tracking-tight prose-p:text-muted-foreground prose-p:leading-8 prose-a:text-primary prose-a:no-underline hover:prose-a:text-primary/80 prose-strong:text-foreground prose-code:text-foreground prose-pre:border prose-pre:border-border prose-pre:bg-background/80">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => <h1 className="text-4xl font-semibold tracking-[-0.06em]">{children}</h1>,
                  h2: ({ children }) => <h2 className="mt-14 text-3xl font-semibold tracking-[-0.05em]">{children}</h2>,
                  h3: ({ children }) => <h3 className="mt-10 text-2xl font-semibold tracking-[-0.04em]">{children}</h3>,
                  p: ({ children }) => {
                    const items = React.Children.toArray(children);
                    const hasMediaChild = items.some((item) => {
                      if (!React.isValidElement(item)) {
                        return false;
                      }
                      if (item.type === "figure" || item.type === "img") {
                        return true;
                      }
                      const props = item.props as { src?: string; node?: { tagName?: string } };
                      return Boolean(props?.src) || props?.node?.tagName === "img";
                    });

                    if (hasMediaChild) {
                      return <div className="mb-8 max-w-4xl">{children}</div>;
                    }

                    return <p className="max-w-3xl text-[1.03rem] leading-8 text-muted-foreground">{children}</p>;
                  },
                  ul: ({ children }) => <ul className="my-6 flex list-disc flex-col gap-2 pl-5">{children}</ul>,
                  ol: ({ children }) => <ol className="my-6 flex list-decimal flex-col gap-2 pl-5">{children}</ol>,
                  li: ({ children }) => <li className="text-muted-foreground">{children}</li>,
                  a: ({ href, children }) => (
                    <a href={href} className="font-medium text-primary underline decoration-primary/40 underline-offset-4 transition-colors hover:text-primary/80">
                      {children}
                    </a>
                  ),
                  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                  em: ({ children }) => <em className="italic text-foreground/90">{children}</em>,
                  code: ({ children }) => (
                    <code className="rounded-md bg-background/90 px-2 py-1 text-[0.9em] font-medium text-foreground">
                      {children}
                    </code>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="my-8 rounded-r-2xl border-l-4 border-primary bg-primary/5 px-5 py-4 italic text-muted-foreground">
                      {children}
                    </blockquote>
                  ),
                  img: ({ src, alt }) => (
                    <figure className="my-10 overflow-hidden rounded-[28px] border border-border bg-card/60">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={String(src || "")}
                        alt={String(alt || "Blog figure")}
                        className="w-full object-cover"
                      />
                      {alt ? (
                        <figcaption className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
                          {String(alt)}
                        </figcaption>
                      ) : null}
                    </figure>
                  ),
                }}
              >
                {post.content}
              </ReactMarkdown>
            </div>
          </div>
        </article>
      </section>
    </div>
  );
}
