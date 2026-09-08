const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/Users/test/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless: true, channel: "chrome"});
  const results = {};
  try {
    for (const fixture of ['metrics', 'calendar']) {
      const page = await browser.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('file://' + path.join(__dirname, fixture + '.html'));
      await page.evaluate(() => { window.commands = []; window.pycmd = x => window.commands.push(JSON.parse(x.slice(4))); });
      await page.addScriptTag({path: path.resolve(__dirname, '../../web/dashboard.js')});
      await page.waitForTimeout(100);
      const before = await page.locator('[data-hdo-metric="today.answers"]').innerText();
      const updated = JSON.parse(fs.readFileSync(path.join(__dirname, 'updated-facts.json')));
      await page.evaluate(envelope => HDOHomeDashboard.receiveDashboardFacts(envelope), updated);
      const after = await page.locator('[data-hdo-metric="today.answers"]').innerText();
      results[fixture] = {before, after, refreshed: after === '123', errors};
      if (fixture === 'calendar') {
        // A pending lazy capability must be requested again after a refresh.
        results[fixture].insightRequests = await page.evaluate(() => commands.filter(x => x.command === 'date_insight').length);
      }
      await page.close();
    }
    console.log(JSON.stringify(results, null, 2));
    fs.writeFileSync(path.join(__dirname, process.argv[2] || 'browser-results.json'), JSON.stringify(results, null, 2) + '\n');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
