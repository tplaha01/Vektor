import fs from 'fs';
import path from 'path';

export interface BlogPost {
  id?: string;
  slug: string;
  title: string;
  description: string;
  date: string;
  tags?: string[];
  featured?: boolean;
  readTime?: string;
  author?: string;
  authorImage?: string;
  thumbnail?: string;
  content: string;
  category?: string;
  views?: number;
  imageQuery?: string;
  assetClass?: string;
  filterKey?: string;
  filterLabel?: string;
}

type FrontmatterValue = string | number | boolean | string[];
type FrontmatterMap = Record<string, FrontmatterValue>;

function asString(value: FrontmatterValue | undefined, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.join(", ");
  return fallback;
}

function asStringArray(value: FrontmatterValue | undefined): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (typeof value === "string") return value ? [value] : [];
  return [];
}

function asBoolean(value: FrontmatterValue | undefined, fallback = false): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return fallback;
}

function parseFrontmatter(content: string): { frontmatter: FrontmatterMap; body: string } {
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const frontmatterRegex = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/;
  const match = normalized.match(frontmatterRegex);

  if (!match) {
    console.warn('No frontmatter found in content');
    return { frontmatter: {}, body: normalized };
  }

  const [, frontmatterStr, body] = match;
  const frontmatter: FrontmatterMap = {};
  const lines = frontmatterStr.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const keyValueMatch = line.match(/^\s*(\w+)\s*:\s*(.*)$/);
    if (!keyValueMatch) continue;

    const [, key, valueStr] = keyValueMatch;
    const value = valueStr.trim();

    if (value === 'true') {
      frontmatter[key] = true;
    } else if (value === 'false') {
      frontmatter[key] = false;
    } else if (value.startsWith('[') && value.endsWith(']')) {
      const arrayContent = value.slice(1, -1);
      frontmatter[key] = arrayContent.split(',').map((item) => item.trim().replace(/^["']|["']$/g, ''));
    } else if (value.startsWith('"') && value.endsWith('"')) {
      frontmatter[key] = value.slice(1, -1);
    } else if (value.startsWith("'") && value.endsWith("'")) {
      frontmatter[key] = value.slice(1, -1);
    } else if (!isNaN(Number(value))) {
      frontmatter[key] = Number(value);
    } else {
      frontmatter[key] = value;
    }
  }

  return { frontmatter, body };
}

const BACKEND_BASE =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://127.0.0.1:8000";

function buildLocalBlogImageUrl(options: {
  title: string;
  subtitle?: string;
  variant?: string;
  symbols?: string[];
  eyebrow?: string;
  category?: string;
  assetClass?: string;
  primarySymbol?: string;
}): string {
  const params = new URLSearchParams();
  params.set("title", options.title || "Vektor Market Brief");
  if (options.subtitle) params.set("subtitle", options.subtitle);
  if (options.variant) params.set("variant", options.variant);
  if (options.eyebrow) params.set("eyebrow", options.eyebrow);
  if (options.category) params.set("category", options.category);
  if (options.assetClass) params.set("assetClass", options.assetClass);
  if (options.primarySymbol) params.set("primarySymbol", options.primarySymbol);
  if (options.symbols?.length) params.set("symbols", options.symbols.slice(0, 4).join(" / "));
  return `/api/blog-image?${params.toString()}`;
}

function parseImageHint(raw: unknown): string {
  const value = String(raw || "").trim();
  if (!value) return "";
  if (value.startsWith("vektor://blog-image/")) {
    return decodeURIComponent(value.replace("vektor://blog-image/", ""));
  }
  if (value.includes("source.unsplash.com")) {
    const queryIndex = value.indexOf("?");
    if (queryIndex >= 0) {
      return decodeURIComponent(value.slice(queryIndex + 1).replace(/\+/g, " "));
    }
  }
  return value;
}

function inferAssetClass(args: { category?: string; symbols?: string[]; tags?: string[]; title?: string }): string {
  const category = String(args.category || "").toLowerCase();
  const title = String(args.title || "").toLowerCase();
  const symbols = (args.symbols || []).map((item) => String(item).toUpperCase());
  const tags = (args.tags || []).map((item) => String(item).toLowerCase());
  const blob = `${category} ${title} ${tags.join(" ")}`;
  const commoditySet = new Set(["GLD", "SLV", "USO", "UNG"]);
  const forexSet = new Set(["EURUSD", "USDJPY", "GBPUSD", "DXY"]);
  const cryptoSet = new Set(["BTC", "ETH", "SOL", "XRP"]);

  if (blob.includes("market report")) return "Market Brief";
  if (blob.includes("quant")) return "Quant Research";
  if (blob.includes("technical")) return "Technical Research";
  if (blob.includes("fundamental")) return "Fundamental Research";
  if (blob.includes("sentiment")) return "Sentiment Research";
  if (symbols.some((item) => commoditySet.has(item))) return "Commodities";
  if (symbols.some((item) => forexSet.has(item))) return "FX";
  if (symbols.some((item) => cryptoSet.has(item))) return "Crypto";
  return "Equities";
}

function inferVisualVariant(args: {
  category?: string;
  assetClass?: string;
  title?: string;
  tags?: string[];
  scheduleKind?: string;
}): string {
  const scheduleKind = String(args.scheduleKind || "").toLowerCase();
  const category = String(args.category || "").toLowerCase();
  const assetClass = String(args.assetClass || "").toLowerCase();
  const title = String(args.title || "").toLowerCase();
  const tags = (args.tags || []).map((item) => String(item).toLowerCase());
  const blob = `${scheduleKind} ${category} ${assetClass} ${title} ${tags.join(" ")}`;

  if (scheduleKind === "premarket" || blob.includes("premarket")) return "premarket";
  if (scheduleKind === "postmarket" || blob.includes("postmarket")) return "postmarket";
  if (scheduleKind === "week_ahead" || blob.includes("week ahead") || blob.includes("macro")) return "macro";
  if (blob.includes("quant")) return "quant";
  if (blob.includes("technical")) return "technical";
  if (blob.includes("fundamental") || blob.includes("valuation")) return "fundamental";
  if (blob.includes("sentiment") || blob.includes("narrative")) return "sentiment";
  if (blob.includes("signal fusion") || blob.includes("multi-signal") || blob.includes("trade construction")) return "multi_signal";
  if (assetClass.includes("commod")) return "commodity";
  if (assetClass.includes("fx")) return "forex";
  if (assetClass.includes("crypto")) return "crypto";
  return "research";
}

function inferFilterGroup(args: {
  category?: string;
  assetClass?: string;
  title?: string;
  tags?: string[];
  scheduleKind?: string;
}): { key: string; label: string } {
  const scheduleKind = String(args.scheduleKind || "").toLowerCase();
  const category = String(args.category || "").toLowerCase();
  const assetClass = String(args.assetClass || "").toLowerCase();
  const title = String(args.title || "").toLowerCase();
  const tags = (args.tags || []).map((item) => String(item).toLowerCase());
  const blob = `${scheduleKind} ${category} ${assetClass} ${title} ${tags.join(" ")}`;

  if (scheduleKind) return { key: "market-briefs", label: "Market Briefs" };
  if (blob.includes("quant")) return { key: "quant", label: "Quant Research" };
  if (blob.includes("technical")) return { key: "technical", label: "Technical Research" };
  if (blob.includes("fundamental") || blob.includes("valuation")) return { key: "fundamental", label: "Fundamental Research" };
  if (blob.includes("sentiment") || blob.includes("narrative")) return { key: "sentiment", label: "Sentiment Research" };
  if (assetClass.includes("commod")) return { key: "commodities", label: "Commodities" };
  if (assetClass.includes("fx")) return { key: "fx", label: "FX" };
  if (assetClass.includes("crypto")) return { key: "crypto", label: "Crypto" };
  return { key: "research", label: "Research Notes" };
}

function rewriteMarkdownImages(markdown: string, post: Record<string, unknown>): string {
  const raw = String(markdown || "");
  const metadata = typeof post["metadata"] === "object" && post["metadata"] ? (post["metadata"] as Record<string, unknown>) : {};
  const symbols = Array.isArray(metadata["symbols"]) ? metadata["symbols"].map((item) => String(item)) : [];
  const category = String(post["category"] || "");
  const tags = Array.isArray(post["tags"]) ? post["tags"].map((item) => String(item)) : [];
  const eyebrow = String(post["category"] || "Vektor");
  const assetClass = inferAssetClass({ category, symbols, tags, title: String(post["title"] || "") });
  const primarySymbol = symbols[0] || String(post["title"] || "").split(":")[0].trim();
  const variant = inferVisualVariant({
    category,
    assetClass,
    title: String(post["title"] || ""),
    tags,
    scheduleKind: String(metadata["schedule_kind"] || ""),
  });

  return raw.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, src) => {
    const title = String(alt || post["title"] || "Vektor Figure").trim();
    const resolved = buildLocalBlogImageUrl({
      title,
      subtitle: parseImageHint(src),
      variant,
      symbols,
      eyebrow,
      category,
      assetClass,
      primarySymbol,
    });
    return `![${title}](${resolved})`;
  });
}

type BackendBlogListPayload = {
  blogs?: Array<Record<string, unknown>>;
};

type BackendBlogDetailPayload = Record<string, unknown> | null;

function mapBackendListItem(post: Record<string, unknown>): BlogPost {
  const metadata = typeof post["metadata"] === "object" && post["metadata"] ? (post["metadata"] as Record<string, unknown>) : {};
  const symbols = Array.isArray(metadata["symbols"]) ? metadata["symbols"].map((item) => String(item)) : [];
  const title = String(post["title"] || "Untitled");
  const description = String(post["excerpt"] || "");
  const category = String(post["category"] || "");
  const tags = Array.isArray(post["tags"]) ? post["tags"].map((item) => String(item)) : [];
  const assetClass = inferAssetClass({ category, symbols, tags, title });
  const primarySymbol = symbols[0] || title.split(":")[0].trim();
  const variant = inferVisualVariant({
    category,
    assetClass,
    title,
    tags,
    scheduleKind: String(metadata["schedule_kind"] || ""),
  });
  const filterGroup = inferFilterGroup({
    category,
    assetClass,
    title,
    tags,
    scheduleKind: String(metadata["schedule_kind"] || ""),
  });
  const imageHint = parseImageHint(post["heroImageUrl"] || metadata["hero_image_url"] || metadata["image_query"]);
  const thumbnail = buildLocalBlogImageUrl({
    title,
    subtitle: imageHint || description || "Vektor market intelligence",
    variant,
    symbols,
    eyebrow: category || "Vektor",
    category,
    assetClass,
    primarySymbol,
  });

  return {
    id: String(post["id"] || ""),
    slug: String(post["slug"] || ""),
    title,
    description,
    date: String(post["publishedAt"] || new Date().toISOString()),
    tags,
    featured: Boolean(post["featured"]),
    readTime: `${String(post["readTime"] || "3")} min read`,
    author: String(post["author"] || "Vektor Editorial"),
    authorImage: "",
    thumbnail,
    content: "",
    category,
    views: Number(post["views"] || 0),
    imageQuery: imageHint || String(metadata["image_query"] || ""),
    assetClass,
    filterKey: filterGroup.key,
    filterLabel: filterGroup.label,
  };
}

function mapBackendDetailItem(post: Record<string, unknown>): BlogPost {
  return {
    ...mapBackendListItem(post),
    content: rewriteMarkdownImages(String(post["content"] || ""), post),
  };
}

async function fetchBackendBlogPosts(): Promise<BlogPost[]> {
  const response = await fetch(`${BACKEND_BASE}/api/blog/posts?limit=100`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`backend_blog_list_failed:${response.status}`);
  }
  const payload = (await response.json()) as BackendBlogListPayload;
  const rows = Array.isArray(payload.blogs) ? payload.blogs : [];
  return rows.map((row) => mapBackendListItem(row)).filter((row) => row.slug && row.title);
}

async function fetchBackendBlogPostBySlug(slug: string): Promise<BlogPost | null> {
  const response = await fetch(`${BACKEND_BASE}/api/blog/posts/${encodeURIComponent(slug)}`, {
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`backend_blog_detail_failed:${response.status}`);
  }
  const payload = (await response.json()) as BackendBlogDetailPayload;
  if (!payload || typeof payload !== "object") {
    return null;
  }
  return mapBackendDetailItem(payload);
}

function loadStaticBlogPosts(): BlogPost[] {
  const contentDir = path.join(process.cwd(), 'blog', 'content');
  const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.mdx'));

  const posts: BlogPost[] = files.map(file => {
    const filePath = path.join(contentDir, file);
    const fileContent = fs.readFileSync(filePath, 'utf8');
    const { frontmatter, body } = parseFrontmatter(fileContent);

    return {
      slug: file.replace('.mdx', ''),
      title: asString(frontmatter.title, 'Untitled'),
      description: asString(frontmatter.description, ''),
      date: asString(frontmatter.date, new Date().toISOString()),
      tags: asStringArray(frontmatter.tags),
      featured: asBoolean(frontmatter.featured, false),
      readTime: asString(frontmatter.readTime, ''),
      author: asString(frontmatter.author, ''),
      authorImage: asString(frontmatter.authorImage, ''),
      thumbnail: asString(frontmatter.thumbnail, ''),
      content: body,
    };
  });

  console.log('Loaded', posts.length, 'static blog posts');
  return posts;
}

export async function getAllBlogPosts(): Promise<BlogPost[]> {
  try {
    const backendPosts = await fetchBackendBlogPosts();
    if (backendPosts.length > 0) {
      console.log('Loaded', backendPosts.length, 'backend blog posts');
      return backendPosts;
    }
  } catch (error) {
    console.error('Error loading backend blog posts, falling back to static content:', error);
  }
  try {
    return loadStaticBlogPosts();
  } catch (error) {
    console.error('Error loading static blog posts:', error);
    return [];
  }
}

export async function getBlogPostBySlug(slug: string): Promise<BlogPost | null> {
  try {
    const backendPost = await fetchBackendBlogPostBySlug(slug);
    if (backendPost) {
      return backendPost;
    }
  } catch (error) {
    console.error('Error loading backend blog detail, falling back to static content:', error);
  }

  const posts = await getAllBlogPosts();
  return posts.find((post) => post.slug === slug) || null;
}
