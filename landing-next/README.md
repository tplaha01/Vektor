# Vektor Landing (Next.js SSR)

This app is the public marketing/landing site for Vektor and is optimized for SEO with Next.js server-side rendering.

## Local run

```bash
cd landing-next
npm install
cp .env.example .env
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

- `NEXT_PUBLIC_SITE_URL`: Canonical URL for metadata, sitemap, and robots.
- `NEXT_PUBLIC_PRODUCT_APP_URL`: URL for your internal product UI (React app).

## Relationship to other apps

- `landing-next`: public SSR landing.
- `frontend`: product/trader web app (React/Vite).
- `backend`: API + orchestration + paper execution engine (FastAPI).
