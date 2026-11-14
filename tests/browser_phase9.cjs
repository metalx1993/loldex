'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const engine=require('../site/search-engine.js');
const base=process.env.LOLDEX_TEST_URL||'http://127.0.0.1:8779';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
 const catalog=await(await page.request.get(base+'/catalog.json')).json();
 const identities=await(await page.request.get(base+'/identities.json')).json();
 async function search(q){await page.goto(base+'/search.html?q='+encodeURIComponent(q));await page.waitForFunction(()=>!document.querySelector('#result-count').textContent.includes('Loading'));}
 for(const q of ['certutil OR source:LOLBAS capability:file-download','platform:windows confidence:high','source:LOLBAS confidence:low','capability:file-download confidence:high']){
  await search(q);const expected=engine.search(catalog.entries,q,{limit:30});
  assert((await page.locator('#result-count').textContent()).startsWith(expected.total.toLocaleString('en')+' results'),q);
  assert.equal(await page.locator('.entry-row').count(),Math.min(30,expected.total));
  if(expected.total){await page.locator('.match-explanation summary').first().click();assert(await page.locator('.match-explanation[open]').first().isVisible());}
 }
 await search('(');assert(await page.locator('[role=alert]').isVisible());assert.equal(await page.locator('.entry-row').count(),0);
 await page.click('#reset');await page.waitForSelector('.entry-row');assert.equal(await page.locator('.entry-row').count(),30);await page.click('#more');assert.equal(await page.locator('.entry-row').count(),60);
 await page.goto(base+'/identities.html');await page.waitForSelector('#identity-results .tech-card');assert.equal(await page.locator('#identity-results .tech-card').count(),3);
 await page.fill('#identity-q','certutil');assert.equal(await page.locator('#identity-results .tech-card').count(),1);
 const withCandidates=identities.entities.find(e=>identities.candidates.some(c=>c.entity_id===e.id));
 for(const entity of identities.entities){
  await page.goto(base+'/identity.html?id='+encodeURIComponent(entity.id));await page.waitForSelector('.identity-member');
  assert.equal(await page.locator('.identity-member').count(),entity.members.length);
  await page.getByText('Inspect identity witnesses',{exact:true}).first().click();assert(await page.locator('details[open] pre').first().isVisible());
 }
 await page.goto(base+'/identity.html?id='+encodeURIComponent(withCandidates.id));await page.waitForSelector('.identity-member');assert(await page.getByRole('heading',{name:'Unconfirmed candidates',exact:true}).isVisible());
 const alias=identities.aliases[0];assert(alias);await page.goto(base+'/entry.html?id='+encodeURIComponent(alias.old_entry_id));await page.waitForSelector('.detail-title');assert((await page.locator('#detail').textContent()).includes(alias.new_entry_ids[0]));
 const member=identities.entities[0].members.find(m=>m.status==='active');
 await page.goto(base+'/entry.html?id='+encodeURIComponent(member.entry_id));await page.waitForSelector('.claims');const shard=page.waitForResponse(r=>r.url().includes('/evidence-records/')&&r.ok());await page.getByText('Inspect original source data',{exact:true}).click();await shard;assert(requests.some(u=>u.includes('/evidence-records/')),'sharded evidence was not loaded');
 for(const path of ['search.html?q=platform%3Awindows%20confidence%3Ahigh','identities.html','identity.html?id='+encodeURIComponent(withCandidates.id),'entry.html?id='+encodeURIComponent(alias.old_entry_id),'entry.html?id='+encodeURIComponent(member.entry_id)]){
  await page.setViewportSize({width:320,height:780});await page.goto(base+'/'+path);
  await page.waitForFunction(()=>!document.querySelector('[aria-busy=true]')&&!document.body.textContent.includes('Loading index'));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),path+' overflows at320');
 }
 assert.deepEqual(errors,[]);console.log('Phase9 browser PASS: advanced valid/invalid/correlated queries, pagination, three identities, candidates, alias, sharded evidence, mobile320; no page errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
