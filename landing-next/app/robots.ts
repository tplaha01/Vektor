import { MetadataRoute } from "next";
import { baseUrl } from "../lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api", "/.next"],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
