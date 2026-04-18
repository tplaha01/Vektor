import { getAllBlogPosts } from "@/lib/blog-loader";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import Image from "next/image";
import ReactMarkdown from "react-markdown";

import { FlickeringGrid } from "@/components/magicui/flickering-grid";
import { HashScrollHandler } from "@/components/hash-scroll-handler";

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

  const posts = await getAllBlogPosts();
  const post = posts.find(p => p.slug === slug);

  if (!post) {
    notFound();
  }

  const date = new Date(post.date);
  const formattedDate = formatDate(date);

  return (
    <div className="min-h-screen bg-background relative">
      <HashScrollHandler />
      <div className="absolute top-0 left-0 z-0 w-full h-[200px] [mask-image:linear-gradient(to_top,transparent_25%,black_95%)]">
        <FlickeringGrid
          className="absolute top-0 left-0 size-full"
          squareSize={4}
          gridGap={6}
          color="#6B7280"
          maxOpacity={0.2}
          flickerChance={0.05}
        />
      </div>

      <div className="space-y-4 border-b border-border relative z-10">
        <div className="max-w-7xl mx-auto flex flex-col gap-6 p-6">
          <div className="flex flex-wrap items-center gap-3 gap-y-5 text-sm text-muted-foreground">
            <Button variant="outline" asChild className="h-6 w-6">
              <Link href="/">
                <ArrowLeft className="w-4 h-4" />
                <span className="sr-only">Back to all articles</span>
              </Link>
            </Button>
            {post.tags && post.tags.length > 0 && (
              <div className="flex flex-wrap gap-3 text-muted-foreground">
                {post.tags.map((tag: string) => (
                  <span
                    key={tag}
                    className="h-6 w-fit px-3 text-sm font-medium bg-muted text-muted-foreground rounded-md border flex items-center justify-center"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
            <time className="font-medium text-muted-foreground">
              {formattedDate}
            </time>
          </div>

          <h1 className="text-4xl md:text-5xl lg:text-6xl font-medium tracking-tighter text-balance">
            {post.title}
          </h1>

          {post.description && (
            <p className="text-muted-foreground max-w-4xl md:text-lg md:text-balance">
              {post.description}
            </p>
          )}
        </div>
      </div>
      <div className="flex divide-x divide-border relative max-w-7xl mx-auto px-4 md:px-0 z-10">
        <div className="absolute max-w-7xl mx-auto left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] lg:w-full h-full border-x border-border p-0 pointer-events-none" />
        <main className="w-full p-0 overflow-hidden">
          {post.thumbnail && (
            <div className="relative w-full h-[500px] overflow-hidden object-cover border border-transparent">
              <Image
                src={post.thumbnail}
                alt={post.title}
                fill
                className="object-cover"
                priority
              />
            </div>
          )}
          <div className="p-6 lg:p-10">
            <div className="prose dark:prose-invert max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-a:no-underline prose-headings:tracking-tight prose-headings:text-balance prose-p:tracking-tight prose-p:text-balance prose-lg">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => <h1 className="text-4xl font-bold mt-8 mb-4">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-3xl font-semibold mt-6 mb-3">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-2xl font-semibold mt-4 mb-2">{children}</h3>,
                  p: ({ children }) => <p className="text-muted-foreground leading-7 mb-4">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside space-y-2 mb-4">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-2 mb-4">{children}</ol>,
                  li: ({ children }) => <li className="text-muted-foreground">{children}</li>,
                  a: ({ href, children }) => <a href={href} className="text-primary hover:underline">{children}</a>,
                  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                  em: ({ children }) => <em className="italic">{children}</em>,
                  code: ({ children }) => <code className="bg-muted px-2 py-1 rounded text-sm font-mono">{children}</code>,
                  blockquote: ({ children }) => <blockquote className="border-l-4 border-primary pl-4 italic text-muted-foreground my-4">{children}</blockquote>,
                }}
              >
                {post.content}
              </ReactMarkdown>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
