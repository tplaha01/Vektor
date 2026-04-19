# Dark Theme Setup - Vektor Trading Bot Blog

This Next.js blog uses a custom dark theme that matches the Admin and Research pages of the trading bot.

## Theme Configuration

The dark theme colors have been applied to `app/globals.css` and use Tailwind CSS custom properties.

### Color Palette

- **Background**: `#060608` (Inky black)
- **Text Primary**: `#dde1ea` (Light gray-blue)
- **Text Secondary**: `#8b919e` (Medium gray)
- **Text Tertiary**: `#4e5462` (Dark gray)
- **Borders**: `rgba(255, 255, 255, 0.03)` (Barely visible)
- **Accents**:
  - Purple: `#9b7fe8` (Primary accent)
  - Green: `#3ecf8e` (Success/positive)
  - Red: `#e05252` (Destructive)
  - Blue: `#4a9eff` (Info)
  - Amber: `#f5a623` (Warning)

### CSS Custom Properties

All colors use CSS variables defined in `:root` and `.dark` classes:

```css
--background: #060608;
--foreground: #dde1ea;
--primary: #9b7fe8;
--accent: #9b7fe8;
--destructive: #e05252;
--border: rgba(255, 255, 255, 0.03);
```

## Running the Blog

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Adding Blog Posts

Blog posts are stored in `blog/content/` as MDX files.

### Creating a Post

1. Create a new file: `blog/content/your-post-title.mdx`
2. Add frontmatter:

```yaml
---
title: "Your Blog Post Title"
description: "A brief description"
date: "2026-04-17"
tags: ["Trading", "AI", "Research"]
featured: false
readTime: "5 min read"
author: "Your Name"
---
```

3. Write your content using Markdown + React components

## Customization

### Modifying Colors

Edit the color values in `app/globals.css`:

```css
:root {
  --primary: #9b7fe8;  /* Change primary accent */
  --destructive: #e05252;  /* Change error/destructive color */
  /* ... other colors */
}
```

### Typography

- Font: Geist Sans (defined in `app/layout.tsx`)
- Border radius: 0.625rem

### Components

Reusable components are in `components/` directory. Customize styling using Tailwind classes.

## Theme Implementation

The blog uses:
- **Tailwind CSS** for styling
- **Fumadocs UI** for blog functionality
- **MDX** for rich blog content
- **Next.js 15** with App Router
- **Dark mode** enabled by default (no theme toggle needed - matches admin aesthetic)

## Deployment

The blog can be deployed to:
- Vercel (recommended for Next.js)
- Docker
- Any Node.js hosting

See [Next.js Deployment](https://nextjs.org/docs/deployment) for options.
