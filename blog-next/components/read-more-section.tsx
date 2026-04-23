/* eslint-disable @next/next/no-img-element */
import { docs, meta } from "@/.source";
import { loader } from "fumadocs-core/source";
import { createMDXSource } from "fumadocs-mdx";
import Link from "next/link";

const blogSource = loader({
  baseUrl: "/blog",
  source: createMDXSource(docs, meta),
});

const formatDate = (date: Date): string => {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

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
  filterLabel?: string;
}

interface BlogPage {
  url: string;
  data: BlogData;
}

interface ReadMoreSectionProps {
  currentSlug: string[];
  currentTags?: string[];
}

export function ReadMoreSection({ currentSlug, currentTags = [] }: ReadMoreSectionProps) {
  const allPages = blogSource.getPages() as BlogPage[];
  const currentUrl = `/blog/${currentSlug.join("/")}`;

  const otherPosts = allPages
    .filter((page) => page.url !== currentUrl)
    .map((page) => {
      const tagOverlap = currentTags.filter((tag) => page.data.tags?.includes(tag)).length;

      return {
        ...page,
        relevanceScore: tagOverlap,
        date: new Date(page.data.date),
      };
    })
    .sort((a, b) => {
      if (a.relevanceScore !== b.relevanceScore) {
        return b.relevanceScore - a.relevanceScore;
      }
      return b.date.getTime() - a.date.getTime();
    })
    .slice(0, 3);

  if (otherPosts.length === 0) {
    return null;
  }

  return (
    <section className="border-t border-border/70 px-6 py-10 lg:px-10">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">Read more</p>
        <h2 className="text-2xl font-semibold tracking-[-0.05em]">Continue through the archive</h2>
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-3">
        {otherPosts.map((post) => {
          const formattedDate = formatDate(post.date);

          return (
            <Link
              key={post.url}
              href={post.url}
              className="group flex h-full flex-col overflow-hidden rounded-[26px] border border-border bg-card/55 transition-all duration-300 hover:-translate-y-1 hover:border-primary/35 hover:bg-card/80"
            >
              {post.data.thumbnail ? (
                <div className="relative h-44 overflow-hidden border-b border-border/80">
                  <img
                    src={post.data.thumbnail}
                    alt={post.data.title}
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                  />
                </div>
              ) : null}
              <div className="flex flex-1 flex-col gap-3 p-5">
                {post.data.filterLabel ? (
                  <span className="inline-flex w-fit rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                    {post.data.filterLabel}
                  </span>
                ) : null}
                <h3 className="text-xl font-semibold tracking-[-0.04em] text-balance transition-colors group-hover:text-primary">
                  {post.data.title}
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">{post.data.description}</p>
                <time className="mt-auto text-sm text-muted-foreground">{formattedDate}</time>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
