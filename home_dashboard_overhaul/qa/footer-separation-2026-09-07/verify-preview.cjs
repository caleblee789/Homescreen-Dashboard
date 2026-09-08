// Focused checks against the existing local production-renderer preview.
const { chromium } = require('/Users/test/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const assert = require('assert/strict');
async function inspect(page) {
  return page.evaluate(() => {
    const q = s => document.querySelector(s);
    const rect = e => e && e.getClientRects().length ? Object.fromEntries(['x','y','width','height','right','bottom'].map(k => [k,e.getBoundingClientRect()[k]])) : null;
    const verse = q('.hdo-calendar-footer-content > .hdo-bible-card');
    const vs = verse && getComputedStyle(verse);
    return {
      date: rect(q('.hdo-selected-date-line')), actions: rect(q('.hdo-context-actions')),
      buttons: [...document.querySelectorAll('.hdo-context-action,.hdo-event-edit')].map(e => ({text:e.textContent,rect:rect(e)})).filter(e=>e.rect),
      chip: rect(q('.hdo-date-state-chip')), footer: rect(q('.hdo-calendar-footer-content')),
      context: rect(q('.hdo-calendar-context')), verse: rect(verse),
      divider: vs ? {vertical:parseFloat(vs.borderInlineStartWidth),horizontal:parseFloat(vs.borderBlockStartWidth),padding:parseFloat(vs.paddingInlineStart)} : null,
      title: rect(q('.hdo-event-heading')), edit: rect(q('.hdo-event-edit')), meta: rect(q('.hdo-event-meta')),
      wrapped: !!q('.hdo-event-row--wrapped'), empty: q('.hdo-event-empty')?.textContent,
      event: q('.hdo-event-title')?.textContent, verseCount:document.querySelectorAll('.hdo-bible-card').length,
      verseRail: !!q('.hdo-insight-rail > .hdo-bible-card'),
      overflow: document.documentElement.scrollWidth-innerWidth,
    };
  });
}
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:950},deviceScaleFactor:2});
  const report=[];
  for (const theme of ['Sapphire Glass','Graphite','Emerald','High Contrast']) for(const mode of ['dark','light']) for(const view of ['month','year']) {
    for(const state of ['event','empty']) {
      const params=new URLSearchParams({theme,mode,view}); if(state==='empty')params.set('events','none');
      await page.goto('http://127.0.0.1:8765/?'+params); await page.waitForTimeout(70);
      const r=await inspect(page); assert.equal(r.overflow,0); assert.equal(r.verseCount,1);
      assert(r.buttons.some(b=>b.text==='Most missed')); assert(r.buttons.every(b=>b.rect.height===28));
      assert.equal(r.chip.height,21);
      if(view==='year') {assert.equal(r.date.x,r.actions.x);assert(r.actions.y>r.date.bottom);assert.equal(r.divider.vertical,1);assert.equal(r.divider.horizontal,0);assert.equal(r.verse.y,r.date.y);assert.equal(r.verse.x-r.context.right,18);assert.equal(r.divider.padding,18);}
      else {assert.equal(r.divider,null);assert(r.verseRail);}
      if(state==='event'){assert(!r.wrapped);assert.equal(r.edit.y,r.title.y);assert(Math.abs(r.edit.x-r.title.right-8)<1);}
      else {assert.equal(r.edit,null);assert.equal(r.title,null);assert.equal(r.meta,null);assert.equal(r.empty,'No upcoming events');}
      report.push({theme,mode,view,state,...r});
    }
  }
  for (const [name,params,width] of [
    ['year-stacked','view=year',1080],['month-stacked','view=month',1080],
    ['year-small','view=year',430],['month-small','view=month',430],
    ['year-long','view=year&fixture=stress',1280],['month-long','view=month&fixture=stress',1280],
    ['year-no-verse','view=year&bible=disabled',1280],['month-no-verse','view=month&bible=disabled',1280],
    ['year-unavailable-verse','view=year&verse=none',1280],
    ['year-empty-no-verse','view=year&bible=disabled&events=none',1280],
    ['selected-fallback','view=year&selected=2026-08-16',1280],
    ['selected-empty','view=year&selected=2026-08-16&events=none',1280],
  ]) {
    await page.setViewportSize({width,height:950});await page.goto('http://127.0.0.1:8765/?'+params);await page.waitForTimeout(100);
    const r=await inspect(page);assert.equal(r.overflow,0);
    if(name==='year-stacked'||name==='year-small'){assert.equal(r.divider.vertical,0);assert.equal(r.divider.horizontal,1);assert(r.verse.y>r.context.bottom);}
    if(name.endsWith('-long')){assert(r.wrapped);assert(r.edit.y>=r.meta.bottom+3);assert.equal(r.edit.x,r.meta.x);}
    if(name.includes('no-verse')||name.includes('unavailable-verse')){assert.equal(r.verseCount,0);assert.equal(r.divider,null);}
    if(name==='selected-fallback')assert(r.event.startsWith('Next event:'));
    if(name==='selected-empty')assert.equal(r.empty,'No events on this date');
    report.push({name,...r});await page.screenshot({path:__dirname+'/preview-'+name+'.png'});
  }
  await page.setViewportSize({width:1280,height:950});await page.goto('http://127.0.0.1:8765/?view=month');
  await page.evaluate(()=>{window.qaVerse=document.querySelector('.hdo-bible-card');window.qaVerseText=qaVerse.textContent;window.qaDate=document.querySelector('[data-hdo-context-date]').textContent;});
  for(let i=0;i<6;i++)for(const view of ['year','month']){
    await page.locator('[data-hdo-calendar-view-button="'+view+'"]').count().then(async n=>{if(n)await page.locator('[data-hdo-calendar-view-button="'+view+'"]').click();else await page.locator('.hdo-view-switch button').filter({hasText:view==='year'?'Year':'Month'}).click();});
    await page.waitForTimeout(40);assert(await page.evaluate(()=>document.querySelectorAll('.hdo-bible-card').length===1 && qaVerse===document.querySelector('.hdo-bible-card') && qaVerseText===qaVerse.textContent && qaDate===document.querySelector('[data-hdo-context-date]').textContent));
  }
  fs.writeFileSync(__dirname+'/preview-verification.json',JSON.stringify({states:report,switch_cycles:6,status:'passed'},null,2));
  console.log('PASS: '+report.length+' layout states and 6 Month/Year cycles.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
