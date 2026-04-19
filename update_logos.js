const fs = require('fs');

const updates = [
  {
    file: 'landing-next/app/page.jsx',
    find: 'style={{ height: 32 }}',
    replace: 'style={{ height: "48px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'landing-next/app/how-it-works/page.jsx',
    find: 'style={{ height: 32 }}',
    replace: 'style={{ height: "48px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'landing-next/app/blog/page.tsx',
    find: 'style={{ height: 32 }}',
    replace: 'style={{ height: "48px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'landing-next/app/blog/[slug]/page.tsx',
    find: 'style={{ height: 32 }}',
    replace: 'style={{ height: "48px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'landing-next/components/site-nav.tsx',
    find: 'className="w-10 h-10 object-cover"',
    replace: 'className="h-10 w-auto object-contain"'
  },
  {
    file: 'blog-next/components/site-nav.tsx',
    find: 'className="w-10 h-10 object-cover"',
    replace: 'className="h-10 w-auto object-contain"'
  },
  {
    file: 'landing-next/components/promo-content.tsx',
    find: 'className="w-8 h-8 rounded object-cover flex-shrink-0"',
    replace: 'className="h-10 w-auto rounded object-contain flex-shrink-0"'
  },
  {
    file: 'blog-next/components/promo-content.tsx',
    find: 'className="w-8 h-8 rounded object-cover flex-shrink-0"',
    replace: 'className="h-10 w-auto rounded object-contain flex-shrink-0"'
  },
  {
    file: 'frontend/src/pages/PublicPnlPage.jsx',
    find: 'style={{ height: \'32px\' }}',
    replace: 'style={{ height: "48px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'frontend/src/pages/Admin.jsx',
    find: 'style={{ height: \'24px\' }}',
    replace: 'style={{ height: "36px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'frontend/src/pages/Blog.jsx',
    find: 'style={{ height: \'24px\' }}',
    replace: 'style={{ height: "36px", width: "auto", objectFit: "contain" }}'
  },
  {
    file: 'frontend/src/pages/AlfredDashboard.jsx',
    find: 'style={{ height: \'18px\' }}',
    replace: 'style={{ height: "28px", width: "auto", objectFit: "contain" }}'
  }
];

updates.forEach(u => {
  if (fs.existsSync(u.file)) {
    let content = fs.readFileSync(u.file, 'utf8');
    // For [slug]/page.tsx which might have multiple instances
    content = content.split(u.find).join(u.replace);
    fs.writeFileSync(u.file, content, 'utf8');
    console.log('Updated', u.file);
  }
});
