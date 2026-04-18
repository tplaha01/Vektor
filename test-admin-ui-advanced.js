import { chromium } from 'playwright';
import fs from 'fs';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // Set viewport
  await page.setViewportSize({ width: 1440, height: 900 });
  
  console.log('🔍 Testing Admin Dashboard UI/UX...\n');
  
  try {
    // Navigate to admin page
    console.log('→ Navigating to /admin...');
    const response = await page.goto('http://localhost:9000/admin', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    });
    
    if (!response) {
      throw new Error('Failed to load page - frontend may not be running');
    }
    
    // Wait for content to load
    await page.waitForTimeout(2000);
    
    // Take screenshot
    console.log('→ Taking screenshot...');
    await page.screenshot({ path: 'admin-dashboard.png', fullPage: false });
    console.log('✓ Screenshot saved: admin-dashboard.png\n');
    
    // Check dark theme colors
    console.log('🎨 Checking color scheme...');
    const htmlElement = await page.locator('html');
    const bodyElement = await page.locator('body');
    
    const bodyBg = await bodyElement.evaluate(el => window.getComputedStyle(el).backgroundColor);
    console.log(`  Body background: ${bodyBg}`);
    
    // Check for key elements
    console.log('\n🔍 Checking UI elements...');
    
    const sidebar = await page.locator('.admin-sidebar');
    const sidebarExists = await sidebar.count() > 0;
    console.log(`  ✓ Sidebar: ${sidebarExists ? '✓' : '✗'}`);
    
    const header = await page.locator('.admin-header');
    const headerExists = await header.count() > 0;
    console.log(`  ✓ Header: ${headerExists ? '✓' : '✗'}`);
    
    const connectionIndicator = await page.locator('.connection-indicator');
    const connIndExists = await connectionIndicator.count() > 0;
    console.log(`  ✓ Connection Indicator: ${connIndExists ? '✓' : '✗'}`);
    
    // Check connection status
    console.log('\n📡 Connection Status:');
    const statusText = await connectionIndicator.textContent();
    console.log(`  Status: ${statusText}`);
    
    // Check for error messages
    console.log('\n⚠️  Looking for errors...');
    const alerts = await page.locator('[role="alert"]');
    const alertCount = await alerts.count();
    
    if (alertCount > 0) {
      const alertTexts = await alerts.allTextContents();
      alertTexts.forEach(text => console.log(`  ⚠️  ${text}`));
    } else {
      console.log('  ✓ No alerts found');
    }
    
    // Check if dashboard content loaded
    console.log('\n📊 Dashboard Content:');
    const kpiGrid = await page.locator('.kpi-grid');
    const kpiExists = await kpiGrid.count() > 0;
    console.log(`  ✓ KPI Grid: ${kpiExists ? '✓' : '✗'}`);
    
    const mainContent = await page.locator('.admin-content');
    const contentText = await mainContent.textContent();
    
    if (contentText.includes('Loading')) {
      console.log('  ⏳ Dashboard is still loading...');
    } else if (contentText.includes('Connection Failed')) {
      console.log('  ✗ Connection failed - backend may be down');
    } else {
      console.log('  ✓ Dashboard content loaded');
    }
    
    // Validate dark theme
    console.log('\n🌙 Dark Theme Validation:');
    const bgColor = await page.locator('.admin-container').evaluate(el => 
      window.getComputedStyle(el).backgroundColor
    );
    console.log(`  Background: ${bgColor}`);
    
    // Check for proper text contrast
    const textColor = await page.locator('.admin-header').evaluate(el => 
      window.getComputedStyle(el).color
    );
    console.log(`  Text color: ${textColor}`);
    
    console.log('\n✅ UI/UX Tests Complete!\n');
    
  } catch (err) {
    console.error('❌ Test Error:', err.message);
    console.log('\nTroubleshooting:');
    console.log('  1. Make sure frontend is running on localhost:9000');
    console.log('  2. Backend can be down - app should show demo data');
    console.log('  3. Check browser console for errors');
  } finally {
    // Keep browser open for inspection
    console.log('Browser will close in 5 seconds...');
    await page.waitForTimeout(5000);
    await browser.close();
  }
})();
