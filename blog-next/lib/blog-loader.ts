import fs from 'fs';
import path from 'path';

export interface BlogPost {
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
}

// Simple YAML frontmatter parser - handles various line ending formats
function parseFrontmatter(content: string): { frontmatter: Record<string, any>; body: string } {
  // Normalize line endings to \n
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  
  // Try to match frontmatter block
  const frontmatterRegex = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/;
  const match = normalized.match(frontmatterRegex);
  
  if (!match) {
    console.warn('No frontmatter found in content');
    return { frontmatter: {}, body: normalized };
  }
  
  const [, frontmatterStr, body] = match;
  const frontmatter: Record<string, any> = {};
  
  // Parse YAML-like frontmatter line by line
  const lines = frontmatterStr.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Skip empty lines and comments
    if (!line.trim() || line.trim().startsWith('#')) continue;
    
    // Match key: value pattern
    const keyValueMatch = line.match(/^\s*(\w+)\s*:\s*(.*)$/);
    if (!keyValueMatch) continue;
    
    const [, key, valueStr] = keyValueMatch;
    const value = valueStr.trim();
    
    console.log(`Parsing key "${key}": "${value}"`);
    
    // Parse the value
    if (value === 'true') {
      frontmatter[key] = true;
    } else if (value === 'false') {
      frontmatter[key] = false;
    } else if (value.startsWith('[') && value.endsWith(']')) {
      // Parse array [item1, item2, ...]
      const arrayContent = value.slice(1, -1);
      frontmatter[key] = arrayContent
        .split(',')
        .map(item => {
          // Remove surrounding quotes if present
          return item.trim().replace(/^["']|["']$/g, '');
        });
    } else if (value.startsWith('"') && value.endsWith('"')) {
      // Remove surrounding double quotes
      frontmatter[key] = value.slice(1, -1);
    } else if (value.startsWith("'") && value.endsWith("'")) {
      // Remove surrounding single quotes
      frontmatter[key] = value.slice(1, -1);
    } else if (!isNaN(Number(value))) {
      // Parse as number
      frontmatter[key] = Number(value);
    } else {
      // Keep as string
      frontmatter[key] = value;
    }
  }
  
  return { frontmatter, body };
}

export async function getAllBlogPosts(): Promise<BlogPost[]> {
  const contentDir = path.join(process.cwd(), 'blog', 'content');
  
  try {
    const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.mdx'));
    
    const posts: BlogPost[] = files.map(file => {
      const filePath = path.join(contentDir, file);
      const fileContent = fs.readFileSync(filePath, 'utf8');
      const { frontmatter, body } = parseFrontmatter(fileContent);
      
      // Debug logging
      if (file.includes('21-best')) {
        console.log('DEBUG: Parsing', file);
        console.log('Frontmatter keys:', Object.keys(frontmatter));
        console.log('Title value:', frontmatter.title);
        console.log('Date value:', frontmatter.date);
      }
      
      return {
        slug: file.replace('.mdx', ''),
        title: frontmatter.title || 'Untitled',
        description: frontmatter.description || '',
        date: frontmatter.date || new Date().toISOString(),
        tags: frontmatter.tags || [],
        featured: frontmatter.featured || false,
        readTime: frontmatter.readTime || '',
        author: frontmatter.author || '',
        authorImage: frontmatter.authorImage || '',
        thumbnail: frontmatter.thumbnail || '',
        content: body,
      };
    });
    
    console.log('Loaded', posts.length, 'blog posts');
    return posts;
  } catch (error) {
    console.error('Error loading blog posts:', error);
    return [];
  }
}

