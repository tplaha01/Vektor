import { Metadata } from "next";
import { getAllBlogPosts } from "@/lib/blog-loader";
import { siteConfig } from "@/lib/site";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  try {
    const { slug } = await params;

    if (!slug || slug.length === 0) {
      return {
        title: "Blog Not Found",
        description: "The requested blog post could not be found.",
      };
    }

    const posts = await getAllBlogPosts();
    const post = posts.find(p => p.slug === slug);

    if (!post) {
      return {
        title: "Blog Not Found",
        description: "The requested blog post could not be found.",
      };
    }

    const ogUrl = `${siteConfig.url}/blog/${slug}`;
    const ogImage = `${ogUrl}/opengraph-image`;

    return {
      title: post.title,
      description: post.description,
      keywords: [
        post.title,
        ...(post.tags || []),
        "Blog",
        "Article",
        "Trading",
        "AI",
        "Finance",
        "Multi-Agent Systems",
      ],
      authors: [
        {
          name: post.author || "Vektor Trading",
          url: siteConfig.url,
        },
      ],
      creator: post.author || "Vektor Trading",
      publisher: "Vektor Trading",
      robots: {
        index: true,
        follow: true,
        googleBot: {
          index: true,
          follow: true,
          "max-video-preview": -1,
          "max-image-preview": "large",
          "max-snippet": -1,
        },
      },
      openGraph: {
        title: post.title,
        description: post.description,
        type: "article",
        url: ogUrl,
        publishedTime: post.date,
        authors: [post.author || "Vektor Trading"],
        tags: post.tags,
        images: [
          {
            url: post.thumbnail || ogImage,
            width: 1200,
            height: 630,
            alt: post.title,
          },
        ],
        siteName: siteConfig.name,
      },
      twitter: {
        card: "summary_large_image",
        title: post.title,
        description: post.description,
        images: [post.thumbnail || ogImage],
        creator: "@vektortrading",
        site: "@vektortrading",
      },
      alternates: {
        canonical: ogUrl,
      },
    };
  } catch (error) {
    console.error("Error generating metadata:", error);
    return {
      title: "Blog Not Found",
      description: "The requested blog post could not be found.",
    };
  }
}
