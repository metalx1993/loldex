/* Offline regression tests for historical Worker source; no deployment implied. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../api/worker.js'), 'utf8');
let serial = 0;
let checks = 0;
const fixture = { entries: [{id:'linux/tar/file-read', name:'tar', platform:'linux',
  privilege_required:'user', aliases:['gtar'], capabilities:['file-read'], phases:['collection'], type:'binary'}] };
async function fresh(fetcher) {
  global.fetch = fetcher;
  return (await import('data:text/javascript;base64,' + Buffer.from(source + '\n// test instance ' + serial++).toString('base64'))).default;
}
const request = (url) => new Request('https://worker.example' + url);
async function expect(worker, url, status) {
  const response = await worker.fetch(request(url));
  assert.equal(response.status, status, url);
  checks++;
  return response;
}
const reply = () => new Response(JSON.stringify(fixture));
(async () => {
  let calls = 0;
  let worker = await fresh(async () => {calls++; return reply();});
  for (const url of [
    '/api/search?q=one&q=two', '/api/search?q[]=x', '/api/search?limit=01',
    '/api/search?limit=-1', '/api/search?limit=201', '/api/search?limit=1x',
    '/api/search?offset=100001', '/api/search?offset=1e5', '/api/search?os=win&platform=linux',
    '/api/search?q=' + 'a'.repeat(257), '/api/search?cap=' + 'a'.repeat(65),
    '/api/search?q=%FF', '/api/search?q=%', '/api/search?q=%00',
    '/api/entry/%ZZ', '/api/entry/%ED%A0%80', '/api/entry/%00',
    '/api/entry/' + 'a'.repeat(513), '/api/search?unknown=x',
    '/api/search?q=' + 'a'.repeat(9000),
  ]) assert.deepEqual(await (await expect(worker,url,400)).json(), {error:'invalid request'});
  assert.equal(calls,0,'invalid input must not reach upstream');
  await expect(worker, '/private/debug',404);
  assert.equal(calls,0,'unrecognized paths must not reach upstream');
  const options = await worker.fetch(new Request('https://worker.example/api',{method:'OPTIONS'}));
  assert.equal(options.status,200);
  await worker.fetch(new Request('https://worker.example/api',{method:'POST'})).then(res=>assert.equal(res.status,405));
  assert.equal(calls,0);

  let response = await expect(worker, '/api/search?q=GTAR&platform=linux&limit=1&offset=0',200);
  assert.deepEqual(await response.json(),{count:1,limit:1,offset:0,results:fixture.entries});
  assert.equal(response.headers.get('x-content-type-options'),'nosniff');
  assert.equal(response.headers.get('access-control-allow-origin'),'*');
  assert.equal(response.headers.get('cache-control'),'no-store');
  await expect(worker, '/api/entry/linux%2Ftar%2Ffile-read',200);
  assert.equal(calls,1,'warm cache reused');
  assert.deepEqual(await (await expect(worker, '/api/search?limit=0',200)).json(),
    {count:1,limit:0,offset:0,results:[]});

  let release;
  calls = 0;
  worker = await fresh((url, init) => {calls++; assert.equal(url,'https://loldex.sh/data.json');
    assert.equal(init.redirect,'manual'); assert.ok(init.signal);
    return new Promise(resolve=>{release=()=>resolve(reply());});});
  const concurrent = Array.from({length:30},()=>worker.fetch(request('/api/stats')));
  await Promise.resolve();
  assert.equal(calls,1,'single in-flight upstream fetch');
  release();
  assert.ok((await Promise.all(concurrent)).every(res=>res.status===200));
  checks++;

  calls=0;
  worker = await fresh(async()=>{if(++calls===1) throw new Error('secret origin and path'); return reply();});
  assert.deepEqual(await (await expect(worker,'/api',502)).json(),{error:'index unavailable'});
  await expect(worker,'/api',200);
  assert.equal(calls,2,'failed in-flight promise is cleared');

  const releasePath='/releases/r-'+'a'.repeat(64)+'/data.json';
  calls=0;
  worker=await fresh(async(url)=>{
    calls++;
    if(calls===1) return new Response(null,{status:307,headers:{Location:releasePath}});
    assert.equal(url,'https://loldex.sh'+releasePath);
    return reply();
  });
  await expect(worker,'/api',200);
  assert.equal(calls,2,'A2 stable catalogue redirect supported');
  for(const location of ['https://attacker.example'+releasePath,'http://loldex.sh'+releasePath,
    'https://user@loldex.sh'+releasePath, '/data.json', releasePath+'?x=1',releasePath+'#fragment',
    '/releases/r-short/data.json','/contact.php']) {
    calls=0;
    worker=await fresh(async()=>{calls++;return new Response(null,{status:307,headers:{Location:location}});});
    await expect(worker,'/api',502);
    assert.equal(calls,1,'invalid redirect is rejected before following');
  }
  calls=0;
  worker=await fresh(async()=>{calls++;return new Response(null,{status:307,headers:{Location:releasePath}});});
  await expect(worker,'/api',502);
  assert.equal(calls,2,'redirect chain is bounded to one hop');

  for (const data of [null,{}, {entries:{}}, {entries:[null]},
    {entries:[{...fixture.entries[0],aliases:'bad'}]},
    {entries:[{...fixture.entries[0],capabilities:[{}]}]},
    {entries:[{...fixture.entries[0],privilege_required:1}]}]) {
    worker = await fresh(async()=>new Response(JSON.stringify(data)));
    assert.deepEqual(await (await expect(worker,'/api/stats',502)).json(),{error:'index unavailable'});
  }
  worker = await fresh(async()=>new Response('internal secret',{status:500}));
  assert.deepEqual(await (await expect(worker,'/api',502)).json(),{error:'index unavailable'});
  worker = await fresh(async()=>new Response('{invalid JSON private path}'));
  assert.deepEqual(await (await expect(worker,'/api',502)).json(),{error:'index unavailable'});
  worker = await fresh(async()=>new Response(new Uint8Array([0xff])));
  await expect(worker,'/api',502);

  let cancelled = false;
  worker = await fresh(async()=>new Response(new ReadableStream({
    cancel(){cancelled=true;}
  }),{headers:{'Content-Length':String(16*1024*1024+1)}}));
  await expect(worker,'/api',502);
  assert.ok(cancelled,'oversize declared body cancelled');
  cancelled=false;
  worker = await fresh(async()=>new Response(new ReadableStream({
    start(controller){controller.enqueue(new Uint8Array(9*1024*1024));controller.enqueue(new Uint8Array(9*1024*1024));},
    cancel(){cancelled=true;}
  })));
  await expect(worker,'/api',502);
  assert.ok(cancelled,'undeclared streamed oversize body cancelled');

  const realTimeout = global.setTimeout;
  global.setTimeout = (fn, ms, ...args)=>realTimeout(fn, ms===10000 ? 5 : ms, ...args);
  try {
    let signal;
    worker = await fresh(async (url,init)=>{signal=init.signal;return new Promise(()=>{});});
    await expect(worker,'/api',502);
    assert.ok(signal.aborted,'deadline aborts stalled fetch');
    cancelled=false;
    worker = await fresh(async()=>new Response(new ReadableStream({cancel(){cancelled=true;}})));
    await expect(worker,'/api',502);
    assert.ok(cancelled,'deadline cancels stalled body');
  } finally {global.setTimeout=realTimeout;}

  const protoEntry={...fixture.entries[0], platform:'__proto__', privilege_required:'constructor', capabilities:['__proto__']};
  worker=await fresh(async()=>new Response(JSON.stringify({entries:[protoEntry]})));
  const stats=await (await expect(worker,'/api/stats',200)).json();
  assert.equal(stats.byPlatform.__proto__,1);
  assert.equal(stats.byPriv.constructor,1);
  assert.equal(stats.byCapability.__proto__,1);

  const corpus=JSON.parse(fs.readFileSync(path.join(__dirname,'../site/data.json'),'utf8'));
  worker=await fresh(async()=>new Response(JSON.stringify(corpus)));
  assert.equal((await (await expect(worker,'/api/stats',200)).json()).count,corpus.entries.length);
  const found=await (await expect(worker,'/api/search?platform=windows&limit=200',200)).json();
  const expected=corpus.entries.filter(e=>e.platform==='windows');
  assert.deepEqual(found,{count:expected.length,limit:200,offset:0,results:expected.slice(0,200)});
  console.log(`Historical Worker security: ${checks} checks passed (offline, not deployed).`);
})().catch(err=>{console.error(err);process.exitCode=1;});
