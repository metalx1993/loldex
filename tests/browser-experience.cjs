const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');fs.mkdirSync('work',{recursive:true});
const base=process.env.LOLDEX_TEST_URL||'http://127.0.0.1:8765';
(async()=>{
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base+'/');
await page.waitForSelector('#stats .stat');
await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').textContent(),'Skip to content');
const catalog=await (await page.request.get(base+'/catalog.json')).json();
assert.equal(await page.locator('.stat strong').first().textContent(),catalog.count.toLocaleString('en-US'));
await page.screenshot({path:'work/home-desktop.png',fullPage:true});
await page.goto(base+'/search.html?q=T1105');
await page.waitForSelector('.entry-row');
assert((await page.locator('#result-count').textContent()).includes('results'));
assert.equal(await page.locator('.entry-row').count(),30);
await page.selectOption('#f-platform','linux');
assert((await page.locator('#result-count').textContent()).startsWith('0 results'));
await page.click('#reset');
await page.waitForSelector('.entry-row');
await page.click('#more');assert.equal(await page.locator('.entry-row').count(),60);
await page.fill('#q','certutil');
assert(await page.locator('.entry-row').count()>0);
const inspectedId=new URL(await page.locator('.rowhead h2 a').first().getAttribute('href'),page.url()).searchParams.get('id');
await page.locator('.rowhead h2 a').first().click();
await page.waitForSelector('.claims');
await page.getByText('Inspect original source data',{exact:true}).click();
await page.waitForSelector('details pre');
await page.waitForSelector('.graph svg');
await page.screenshot({path:'work/entry-desktop.png',fullPage:true});
await page.goto(base+'/technique.html?id=T1105');
await page.waitForSelector('.graph svg');
assert.equal(await page.locator('h1').textContent(),'Ingress Tool Transfer');
await page.goto(base+'/techniques.html');
await page.waitForSelector('.tech-card');
await page.fill('#tech-q','ZZZ');assert.equal(await page.locator('.tech-card').count(),0);
await page.fill('#tech-q','T1105');assert.equal(await page.locator('.tech-card').count(),1);
for(const path of ['index.html','search.html','techniques.html','entry.html?id='+encodeURIComponent(inspectedId),'technique.html?id=T1105']){
  await page.setViewportSize({width:320,height:780});
  await page.goto(base+'/'+path);
  await page.waitForSelector(path.startsWith('index')?'#stats .stat':path.startsWith('search')?'.entry-row':path.startsWith('techniques')?'.tech-card':path.startsWith('entry')?'.claims':'.graph svg');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),path+' overflows');
}
await page.screenshot({path:'work/technique-mobile.png',fullPage:true});
await page.goto(base+'/technique.html?id=T1562');await page.waitForSelector('.graph svg');assert(await page.getByText('This identifier is revoked in the registry.',{exact:true}).isVisible());
await page.goto(base+'/search.html?q=Ingress%20Tool%20Transfer');await page.waitForSelector('.entry-row');assert(await page.locator('.entry-row').count()>0);
// Payloads in source data must stay literal; unsafe protocols must never become links.
await page.route('**/catalog.json',async route=>{const response=await route.fetch();const json=await response.json();json.entries[0].name='<img src=x onerror=alert(1)>';json.entries[0].references=['javascript:alert(1)'];await route.fulfill({json});});
await page.goto(base+'/search.html');await page.waitForSelector('.entry-row');
assert.equal(await page.locator('img').count(),0);
assert.equal(await page.locator('a[href^="javascript:"]').count(),0);
// Exercise the entry renderer which actually creates source-reference anchors.
await page.unroute('**/catalog.json');
await page.route('**/catalog.json',async route=>{
 const response=await route.fetch(),json=await response.json();
 json.entries[0].references=['javascript:alert(1)','data:text/html,<script>alert(1)</script>','https://example.com/safe-reference'];
 await route.fulfill({json});
});
await page.goto(base+'/entry.html?id='+encodeURIComponent(catalog.entries[0].id));
await page.waitForSelector('.claims');
assert.equal(await page.locator('a[href^="javascript:"],a[href^="data:"]').count(),0);
const safeReference=page.locator('a[href="https://example.com/safe-reference"]');
assert.equal(await safeReference.count(),1);
assert.equal(await safeReference.getAttribute('rel'),'noopener noreferrer');
assert.equal(await safeReference.getAttribute('target'),'_blank');
await page.goto(base+'/contact.html');
assert.equal(await page.locator('#send').isEnabled(),true);
assert.equal(await page.locator('script:not([src])').count(),0);
let contactRequests=0;
await page.route('**/contact.php',async route=>{
 contactRequests++;
 await route.fulfill({status:429,contentType:'application/json',headers:{'Retry-After':'60'},body:JSON.stringify({success:false,message:'Please retry later.'})});
});
await page.fill('#name','Browser test');await page.fill('#email','tester@example.invalid');
await page.fill('#message','漢'.repeat(3000));await page.click('#send');
assert.equal(contactRequests,0);assert(await page.locator('.field-err[data-for="message"]').isVisible());
await page.fill('#message','A simulated message; no mail is sent.');await page.click('#send');
await page.waitForFunction(()=>document.querySelector('#result').textContent==='Please retry later.');
assert.equal(contactRequests,1);assert.equal(await page.locator('#send').isEnabled(),true);
await page.evaluate(()=>{
 window.__cspBlocked=false;
 document.addEventListener('securitypolicyviolation',event=>{if(event.violatedDirective==='script-src-elem')window.__cspBlocked=true;});
 const injected=document.createElement('script');injected.textContent='window.__unsafeInlineExecuted=true';document.body.append(injected);
});
await page.waitForFunction(()=>window.__cspBlocked===true);
assert.equal(await page.evaluate(()=>window.__unsafeInlineExecuted),undefined);

assert.deepEqual(errors,[]);
console.log('Browser checks passed: search, filters, pagination, entry evidence, techniques, 320px layouts, injection rendering.');
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
