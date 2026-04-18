import { getAllBlogPosts } from "./blog-loader";

interface BlogPageSource {
  url: string;
  data: {
    title: string;
    description: string;
    date: string;
    tags?: string[];
    featured?: boolean;
    readTime?: string;
    author?: string;
    authorImage?: string;
    thumbnail?: string;
    body?: React.ReactNode;  // Placeholder for MDX body
    content: string; // Raw markdown/MDX content
  };
}

// Create a source-like object that works with the fumadocs loader
export async function createBlogSource() {
  const posts = await getAllBlogPosts();
  
  // Create a map of slug to post for quick lookup
  const postsBySlug = new Map<string, (typeof posts)[0]>();
  posts.forEach(post => {
    postsBySlug.set(post.slug, post);
  });
  
  return {
    getPage: (slugParts: string[]) => {
      const slug = Array.isArray(slugParts) ? slugParts[0] : slugParts;
      const post = postsBySlug.get(slug);
      
      if (!post) {
        return null;
      }
      
      return {
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
          body: post.content, // Raw content for now
          content: post.content,
        },
      };
    },
    getPages: () => {
      return posts.map(post => ({
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
          body: post.content,
          content: post.content,
        },
      }));
    },
  };
}
