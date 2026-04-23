import { getAllBlogPosts } from "@/lib/blog-loader";
import { Suspense } from "react";
import { BlogCard } from "@/components/blog-card";
import { TagFilter } from "@/components/tag-filter";
import { FlickeringGrid } from "@/components/magicui/flickering-grid";
import Link from "next/link";

interface BlogData {
  title: string;
  description: string;
  date: string;
  tags?: string[];
  featured?: boolean;
  readTime?: string;
  author?: string;
  authorImage?: string;
  thumbnail?: string;
  assetClass?: string;
  filterKey?: string;
  filterLabel?: string;
}

interface BlogPage {
  url: string;
  slug: string;
  data: BlogData;
}

const formatDate = (date: Date): string => {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const blogPosts = await getAllBlogPosts();

  const allPages: BlogPage[] = blogPosts.map((post) => ({
    slug: post.slug,
    url: `/blog/${post.slug}`,
    data: {
      title: post.title,
      description: post.description,
      date: post.date,
      tags: post.tags,
      featured: post.featured,
      readTime: post.readTime,
      author: post.author,
      authorImage: post.authorImage,
      thumbnail: post.thumbnail,
      assetClass: post.assetClass,
      filterKey: post.filterKey,
      filterLabel: post.filterLabel,
    },
  }));

  const sortedBlogs = allPages.sort((a, b) => {
    const dateA = new Date(a.data.date).getTime();
    const dateB = new Date(b.data.date).getTime();
    return dateB - dateA;
  });

  const allTags = [
    "All",
    ...Array.from(
      new Set(
        sortedBlogs
          .map((blog) => blog.data.filterLabel)
          .filter((label): label is string => Boolean(label))
      )
    ),
  ];

  const selectedTag = resolvedSearchParams.tag || "All";
  const filteredBlogs =
    selectedTag === "All"
      ? sortedBlogs
      : sortedBlogs.filter((blog) => blog.data.filterLabel === selectedTag);

  const tagCounts = allTags.reduce((acc, tag) => {
    acc[tag] =
      tag === "All"
        ? sortedBlogs.length
        : sortedBlogs.filter((blog) => blog.data.filterLabel === tag).length;
    return acc;
  }, {} as Record<string, number>);

  const [heroPost, ...remainingPosts] = filteredBlogs;
  const heroDate = heroPost ? formatDate(new Date(heroPost.data.date)) : "";

  return (
    <div className="relative min-h-screen bg-background">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[360px] [mask-image:linear-gradient(to_top,transparent_15%,black_85%)]">
        <FlickeringGrid
          className="absolute inset-0 size-full"
          squareSize={4}
          gridGap={6}
          color="#6B7280"
          maxOpacity={0.22}
          flickerChance={0.14}
        />
      </div>

      <section className="relative z-10 border-b border-border/70">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)] lg:items-end">
          <div className="flex flex-col gap-5">
            <div className="inline-flex w-fit items-center rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Vektor research
            </div>
            <div className="flex flex-col gap-4">
              <h1 className="max-w-4xl text-4xl font-semibold tracking-[-0.08em] text-balance sm:text-5xl lg:text-7xl">
                Research that reads like an operating log, not a content funnel.
              </h1>
              <p className="max-w-3xl text-base leading-7 text-muted-foreground md:text-lg">
                Market briefs, thesis work, and architecture notes from the stack that powers
                Vektor&apos;s paper-first trading workflow.
              </p>
            </div>
            {allTags.length > 0 ? (
              <div className="max-w-4xl">
                <TagFilter
                  tags={allTags}
                  selectedTag={selectedTag}
                  tagCounts={tagCounts}
                />
              </div>
            ) : null}
          </div>

          <aside className="rounded-[28px] border border-border bg-card/60 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] backdrop-blur-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Archive shape
            </p>
            <div className="mt-4 space-y-4 text-sm text-muted-foreground">
              <p>
                Notes are grouped the same way operators read them inside the product: market
                briefs first, deeper research second, controls always visible.
              </p>
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                <div className="rounded-2xl border border-border/80 bg-background/70 px-4 py-3">
                  <p className="text-2xl font-semibold tracking-tight text-foreground">{sortedBlogs.length}</p>
                  <p>Total posts</p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-background/70 px-4 py-3">
                  <p className="text-2xl font-semibold tracking-tight text-foreground">{allTags.length - 1}</p>
                  <p>Editorial lanes</p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-background/70 px-4 py-3">
                  <p className="text-2xl font-semibold tracking-tight text-foreground">Paper-first</p>
                  <p>Operating principle</p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <div className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-16 pt-8">
        {heroPost ? (
          <section className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(260px,0.75fr)]">
            <article className="overflow-hidden rounded-[32px] border border-border bg-card/70 p-6 shadow-[0_24px_70px_rgba(0,0,0,0.18)] backdrop-blur-sm md:p-8">
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                {heroPost.data.filterLabel ? (
                  <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-medium text-primary">
                    {heroPost.data.filterLabel}
                  </span>
                ) : null}
                {heroPost.data.assetClass ? <span>{heroPost.data.assetClass}</span> : null}
                <span>{heroDate}</span>
              </div>
              <div className="mt-5 flex flex-col gap-4">
                <h2 className="max-w-4xl text-3xl font-semibold tracking-[-0.06em] text-balance sm:text-4xl lg:text-5xl">
                  {heroPost.data.title}
                </h2>
                <p className="max-w-3xl text-base leading-7 text-muted-foreground md:text-lg">
                  {heroPost.data.description}
                </p>
              </div>
              <div className="mt-8 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <span>{heroPost.data.author || "Vektor"}</span>
                {heroPost.data.readTime ? <span>{heroPost.data.readTime} min read</span> : null}
              </div>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href={heroPost.url}
                  className="inline-flex min-h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5"
                >
                  Read featured note
                </Link>
                <Link
                  href="#latest"
                  className="inline-flex min-h-11 items-center justify-center rounded-full border border-border bg-background/70 px-5 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
                >
                  Browse archive
                </Link>
              </div>
            </article>

            <aside className="rounded-[32px] border border-border bg-card/60 p-6 backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                Read this archive for
              </p>
              <ul className="mt-5 flex list-none flex-col gap-4 p-0 text-sm leading-6 text-muted-foreground">
                <li className="rounded-2xl border border-border/80 bg-background/60 px-4 py-4">
                  Pre-market and post-market framing that can be scanned fast.
                </li>
                <li className="rounded-2xl border border-border/80 bg-background/60 px-4 py-4">
                  Deeper research notes with enough structure to revisit later.
                </li>
                <li className="rounded-2xl border border-border/80 bg-background/60 px-4 py-4">
                  A cleaner bridge between what the blog says and what the product does.
                </li>
              </ul>
            </aside>
          </section>
        ) : null}

        <Suspense fallback={<div className="rounded-3xl border border-border bg-card/60 p-8 text-muted-foreground">Loading articles...</div>}>
          {remainingPosts.length > 0 ? (
            <div id="latest" className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
              {remainingPosts.map((blog) => {
                const date = new Date(blog.data.date);
                const formattedDate = formatDate(date);

                return (
                  <BlogCard
                    key={blog.url}
                    url={blog.url}
                    title={blog.data.title}
                    description={blog.data.description}
                    date={formattedDate}
                    thumbnail={blog.data.thumbnail}
                    assetClass={blog.data.assetClass}
                    filterLabel={blog.data.filterLabel}
                    filterKey={blog.data.filterKey}
                    showRightBorder={false}
                  />
                );
              })}
            </div>
          ) : (
            <div className="rounded-[32px] border border-border bg-card/60 p-10 text-center shadow-[0_24px_70px_rgba(0,0,0,0.14)]">
              <h2 className="text-2xl font-semibold tracking-tight">No posts matched that filter.</h2>
              <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
                The category is empty right now. Switch back to the full archive to browse everything.
              </p>
              <div className="mt-6 flex justify-center">
                <Link
                  href="/"
                  className="inline-flex min-h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground"
                >
                  View all research
                </Link>
              </div>
            </div>
          )}
        </Suspense>
      </div>
    </div>
  );
}
