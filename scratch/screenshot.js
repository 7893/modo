const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto('https://nexus.53.workers.dev/', { waitUntil: 'networkidle2' });
  await page.screenshot({ path: '/home/ubuntu/nexus/scratch/screenshot.png' });
  await browser.close();
  console.log('Screenshot taken!');
})();
