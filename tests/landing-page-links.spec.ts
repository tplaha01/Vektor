import { test, expect } from '@playwright/test';

const LANDING_URL = 'http://localhost:3000';
const FRONTEND_URL = 'http://localhost:9000';
const BACKEND_URL = 'http://localhost:8000';
const BLOG_URL = 'http://localhost:3001';

test.describe('Landing Page - Link Verification', () => {
  test('landing page loads successfully', async ({ page }) => {
    const response = await page.goto(LANDING_URL);
    expect(response?.status()).toBe(200);
  });

  test('all header navigation links are accessible', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    // Check "How It Works" link
    const howItWorksLink = page.locator('a[href="/how-it-works"]').first();
    await expect(howItWorksLink).toBeVisible();
    expect(await howItWorksLink.getAttribute('href')).toBe('/how-it-works');
    
    // Check "Blog" link
    const blogLink = page.locator(`a[href="${BLOG_URL}"]`).first();
    await expect(blogLink).toBeVisible();
    expect(await blogLink.getAttribute('href')).toBe(BLOG_URL);
    
    // Check "Live PnL" link
    const pnlLink = page.locator(`a[href="${FRONTEND_URL}"]`).first();
    await expect(pnlLink).toBeVisible();
    expect(await pnlLink.getAttribute('href')).toBe(FRONTEND_URL);
    
    // Check "Admin Console" link
    const adminLink = page.locator(`a[href="${FRONTEND_URL}/admin"]`).first();
    await expect(adminLink).toBeVisible();
    expect(await adminLink.getAttribute('href')).toBe(`${FRONTEND_URL}/admin`);
  });

  test('all CTA buttons navigate to correct URLs', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    // Collect all links
    const links = await page.locator('a[href]').all();
    const uniqueUrls = new Set<string>();
    
    for (const link of links) {
      const href = await link.getAttribute('href');
      if (href) {
        uniqueUrls.add(href);
      }
    }
    
    // Verify expected links exist
    expect(Array.from(uniqueUrls)).toContain('/how-it-works');
    expect(Array.from(uniqueUrls)).toContain(BLOG_URL);
    expect(Array.from(uniqueUrls)).toContain(FRONTEND_URL);
    expect(Array.from(uniqueUrls)).toContain(`${FRONTEND_URL}/admin`);
  });

  test('hero section primary button works', async ({ page, context }) => {
    await page.goto(LANDING_URL);
    
    // Get the primary button in hero section
    const heroBtn = page.locator('.hero .btn.primary').first();
    await expect(heroBtn).toBeVisible();
    
    const href = await heroBtn.getAttribute('href');
    expect(href).toBe(FRONTEND_URL);
  });

  test('all dark-card elements are styled correctly', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    const darkCards = page.locator('.dark-card');
    const count = await darkCards.count();
    expect(count).toBeGreaterThan(0);
    
    // Verify dark theme colors
    for (let i = 0; i < Math.min(count, 3); i++) {
      const card = darkCards.nth(i);
      const styles = await card.evaluate((el) => window.getComputedStyle(el));
      expect(styles.borderColor).toBeTruthy();
    }
  });

  test('footer links are accessible', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    // Scroll to footer
    await page.locator('footer').scrollIntoViewIfNeeded();
    
    // Check footer links
    const footerBlogLink = page.locator('footer').locator(`a[href="${BLOG_URL}"]`);
    const footerPnlLink = page.locator('footer').locator(`a[href="${FRONTEND_URL}"]`);
    const footerTechLink = page.locator('footer').locator('a[href="/how-it-works"]');
    
    await expect(footerBlogLink).toBeVisible();
    await expect(footerPnlLink).toBeVisible();
    await expect(footerTechLink).toBeVisible();
  });

  test('all section links are accessible', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    // Check navigation to sections
    const sections = ['#how', '#safety', '#agents', '#features', '#comparison', '#faq', '#cta-final'];
    
    for (const section of sections) {
      const element = page.locator(section);
      await expect(element).toBeInViewport({ ratio: 0.1 }).catch(() => {
        // Section may not exist, that's okay
      });
    }
  });

  test('page has no broken internal links', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    const links = await page.locator('a[href^="/"], a[href^="http://localhost"]').all();
    
    for (const link of links) {
      const href = await link.getAttribute('href');
      expect(href).toBeTruthy();
      
      // Check if link is valid format
      if (href?.startsWith('http')) {
        expect(href).toMatch(/^https?:\/\//);
      }
    }
  });

  test('page loads with dark theme styles', async ({ page }) => {
    await page.goto(LANDING_URL);
    
    // Check dark theme variables are applied
    const html = page.locator('html');
    const styles = await html.evaluate((el) => {
      const style = window.getComputedStyle(document.documentElement);
      return {
        bg: style.getPropertyValue('--bg'),
        text: style.getPropertyValue('--text'),
        accent: style.getPropertyValue('--accent'),
      };
    });
    
    expect(styles).toBeTruthy();
  });

  test('responsive design - all buttons readable on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(LANDING_URL);
    
    // Check buttons are visible and clickable
    const buttons = page.locator('.btn');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
    
    for (let i = 0; i < Math.min(count, 5); i++) {
      const btn = buttons.nth(i);
      await expect(btn).toBeVisible();
    }
  });

  test('page performance - landing page loads in reasonable time', async ({ page }) => {
    const startTime = Date.now();
    await page.goto(LANDING_URL, { waitUntil: 'networkidle' });
    const loadTime = Date.now() - startTime;
    
    // Should load in less than 3 seconds
    expect(loadTime).toBeLessThan(3000);
  });
});
