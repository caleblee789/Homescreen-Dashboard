const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/Users/test/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless:true, channel:'chrome'});
  const page = await browser.newPage();
  const errors=[];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto('file://' + path.join(__dirname, 'calendar.html'));
    await page.evaluate(() => { window.commands=[]; window.pycmd=x=>commands.push(JSON.parse(x.slice(4))); });
    await page.addScriptTag({path:path.resolve(__dirname, process.argv[3] || '../../web/dashboard.js')});
    const results = await page.evaluate(() => {
      const api=HDOHomeDashboard, root=document.getElementById('hdo-dashboard');
      const payload=JSON.parse(root.querySelector('.hdo-calendar-data').textContent);
      const insightRequests=()=>commands.filter(x=>x.command==='date_insight');
      root.querySelector('[data-date="2026-09-06"]').click();
      const first=insightRequests().at(-1).payload;
      api.receiveDayInsight({date:first.date, request_id:first.request_id, revision:1, insight:{most_missed_available:false}});
      api.receiveDashboardFacts({revision:2, facts:{...payload, revision:2}});
      const second=insightRequests().at(-1).payload;
      const reRequested=second.request_id!==first.request_id;
      // Only the current revision's reply can enable the selected-date action.
      api.receiveDayInsight({date:first.date, request_id:first.request_id, revision:1, insight:{most_missed_available:true}});
      const rejectedStaleInsight=root.querySelector('[data-hdo-most-missed]').hidden;
      api.receiveDayInsight({date:second.date, request_id:second.request_id, revision:2, insight:{most_missed_available:true}});
      const currentInsightWorks=!root.querySelector('[data-hdo-most-missed]').hidden;
      // Crossing the scheduler's year boundary while following Today moves the calendar.
      root.querySelector('[data-hdo-calendar="today"]').click();
      const nextFacts={...payload, revision:3, scheduling_date:'2027-01-01', calendar_date:'2027-01-01', selected_date:'2027-01-01', anchor:'2027-01-01', source_revision:'rollover', activity:[]};
      api.receiveDashboardFacts({revision:3, facts:nextFacts});
      const title=root.querySelector('[data-hdo-calendar-title]').textContent;
      const range=commands.filter(x=>x.command==='calendar_range').at(-1).payload;
      return {reRequested,rejectedStaleInsight,currentInsightWorks,rolloverTitle:title,rolloverPassed:title==='2027',rangeUsesCurrentRevision:range.revision===3,errors:[]};
    });
    results.errors=errors;
    console.log(JSON.stringify(results,null,2));
    fs.writeFileSync(path.join(__dirname,process.argv[2]),JSON.stringify(results,null,2)+'\n');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
