const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const routes = [
  { name: 'login', url: 'http://localhost:8080/__boot-login.html', width: 1280, height: 800 },
  { name: 'register', url: 'http://localhost:8080/__boot-register.html', width: 1280, height: 800 },
  { name: 'employee', url: 'http://localhost:8080/__boot-employee.html', width: 1440, height: 900 },
  { name: 'employee-phone', url: 'http://localhost:8080/__boot-employee.html', width: 390, height: 844 },
  { name: 'client-admin', url: 'http://localhost:8080/__boot-client-admin.html', width: 1440, height: 900 },
  { name: 'client-admin-phone', url: 'http://localhost:8080/__boot-client-admin.html', width: 390, height: 844 },
  { name: 'super-admin', url: 'http://localhost:8080/__boot-super-admin.html', width: 1440, height: 900 },
  { name: 'super-admin-phone', url: 'http://localhost:8080/__boot-super-admin.html', width: 390, height: 844 },
];

async function capture() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const outDir = 'C:\\Users\\test user 2\\ChatBot_VaultIQ\\frontend\\screenshots-fe2';
  const fs = require('fs');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  for (const route of routes) {
    const page = await browser.newPage();
    await page.setViewport({ width: route.width, height: route.height, deviceScaleFactor: 1 });
    
    try {
      await page.goto(route.url, { waitUntil: 'networkidle0', timeout: 30000 });
      // Wait for redirect and page render
      await page.waitForFunction(() => document.readyState === 'complete', { timeout: 15000 });
      await new Promise(r => setTimeout(r, 1000)); // Extra wait for render
      
      await page.screenshot({ path: `${outDir}\\${route.name}.png`, fullPage: true });
      console.log(`${route.name}.png captured`);
    } catch (e) {
      console.error(`Failed ${route.name}:`, e.message);
    } finally {
      await page.close();
    }
  }

  await browser.close();
  console.log('All screenshots captured');
}

capture().catch(console.error);