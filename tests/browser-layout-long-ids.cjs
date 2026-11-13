/* Real-corpus regression: identifiers and source evidence must wrap at 320px. */
'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.LOLDEX_TEST_URL||'http://127.0.0.1:8767';
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:320,height:780}});
    const catalog=await (await page.request.get(base+'/catalog.json')).json();
    const longest=catalog.entries.filter(e=>e.id.startsWith('lolad/')).sort((a,b)=>b.id.length-a.id.length)[0];
    assert(longest,'The corpus needs a LOLAD entry for this regression');
    const inspected=catalog.entries.find(e=>e.name==='Check Domain Controller Certificates')||longest;
    const longReference='https://example.invalid/reference/'+('source-evidence-'.repeat(55));
    await page.route('**/catalog.json',async route=>{
      const response=await route.fetch();
      const payload=await response.json();
      const row=payload.entries.find(e=>e.id===longest.id);
      row.references=[longReference];
      const claim=Object.values(row.claims||{}).flat().find(c=>c&&c.provenance);
      if(claim)claim.provenance.adapter='lolad@'+('revision'.repeat(100));
      await route.fulfill({json:payload});
    });
    for(const width of [320,375,768,1440]) {
      await page.setViewportSize({width,height:900});
      for(const id of new Set([inspected.id,longest.id])) {
        await page.goto(base+'/entry.html?id='+encodeURIComponent(id));
        await page.waitForSelector('.claims');
        await page.waitForSelector('.graph svg');
        const layout=await page.evaluate(()=>({
          viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
          bodyWidth:document.body.scrollWidth,
          documentOverflow:getComputedStyle(document.documentElement).overflowX,
          bodyOverflow:getComputedStyle(document.body).overflowX,
          crumb:document.querySelector('#crumb-label').textContent,
        }));
        assert(layout.documentWidth<=width&&layout.bodyWidth<=width,`${id.length}-character ID overflows ${width}px: ${JSON.stringify(layout)}`);
        assert.equal(layout.crumb,id,'Wrapping must retain the full identifier');
        assert.notEqual(layout.documentOverflow,'hidden','Do not hide global overflow');
        assert.notEqual(layout.bodyOverflow,'hidden','Do not hide global overflow');
        if(id===longest.id)assert.equal(await page.getByRole('link',{name:longReference,exact:true}).textContent(),longReference);
      }
    }
    console.log(`Long-identifier browser regression passed: ${longest.id.length}-character ID, source URLs and claim provenance at 320/375/768/1440px.`);
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1);});
