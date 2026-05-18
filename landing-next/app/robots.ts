import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/api', '/.next'],
    },
    sitemap: 'https://vektor-landing.vercel.app/sitemap.xml',
  };
}