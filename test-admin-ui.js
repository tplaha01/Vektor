import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    // Go to admin page
    await page.goto('http://localhost:9000/admin', { waitUntil: 'networkidle' });
    
    // Wait and screenshot
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'admin-page.png', fullPage: true });
    
    // Check what's on the page
    const bodyText = await page.textContent('body');
    console.log('Page content:', bodyText.substring(0, 500));
    
    // Check for error messages
    const errorMsgs = await page.locator('[role="alert"]').allTextContents();
    console.log('Errors:', errorMsgs);
    
    // Check network errors
    page.on('response', response => {
      if (!response.ok()) {
        console.log(`Response error: ${response.url()} - ${response.status()}`);
      }
    });
    
    await page.waitForTimeout(2000);
    
  } catch (err) {
    console.error('Test failed:', err.message);
  } finally {
    await browser.close();
  }
})();
