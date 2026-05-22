import { MetadataRoute } from "next";
import { baseUrl } from "../lib/site";
import { blogPostsData } from "./blog/data";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = [
    "",
    "/platform",
    "/operating-model",
    "/data",
    "/risk",
    "/performance",
    "/blog",
  ];

  const routeEntries = routes.map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: route === "" ? 1 : 0.82,
  }));

  const blogEntries = Object.values(blogPostsData).map((post) => ({
    url: `${baseUrl}/blog/${post.slug}`,
    lastModified: new Date(post.date),
    changeFrequency: "monthly" as const,
    priority: 0.64,
  }));

  return [...routeEntries, ...blogEntries];
}
