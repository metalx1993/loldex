/* Real PHP interpreter (WASM), isolated VFS; never connects to the public host. */
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
const canonical=o=>JSON.stringify(Object.fromEntries(Object.entries(o).sort(([a],[b])=>a.localeCompare(b))));
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 for(const p of ['/www','/www/public_html','/www/public_html/releases','/www/loldex-control'])php.mkdir(p);
 php.writeFile('/www/public_html/loldex-router.php',fs.readFileSync('deployment/siteground/loldex-router.php'));
 const id='r-'+'a'.repeat(64), second='r-'+'b'.repeat(64), commit='c'.repeat(40);
 const token={version:1,generation:1,release_id:id,previous_release_id:null,commit};
 const file='/www/loldex-control/active.json';
 for(const rid of [id,second]){php.mkdir('/www/public_html/releases/'+rid);php.writeFile('/www/public_html/releases/'+rid+'/release.json',canonical({release_id:rid,commit}));}
 const run=async(uri,method='GET')=>php.run({scriptPath:'/www/public_html/loldex-router.php',relativeUri:uri,method,$_SERVER:{REQUEST_URI:uri,REQUEST_METHOD:method},usePrimaryPhp:true});
 const location=r=>(r.headers.location||r.headers.Location||[])[0];
 let r=await run('/');assert.equal(r.httpStatusCode,503); // uninitialized never guesses
 php.writeFile(file,canonical(token));r=await run('/');assert.equal(r.errors,'');assert.equal(r.httpStatusCode,307);assert.equal(location(r),'/releases/'+id+'/index.html');
 assert((r.headers['cache-control']||[]).join().includes('no-store'));
 r=await run('/api.php?action=search&q=a%20b');assert.equal(r.httpStatusCode,307);assert.equal(location(r),'/releases/'+id+'/api.php?action=search&q=a%20b');
 r=await run('/contact.php','POST');assert.equal(r.httpStatusCode,307); // no following or sending mail
 const oldURL=location(await run('/catalog.json'));
 php.writeFile(file,canonical({...token,generation:2,release_id:second,previous_release_id:id}));
 assert.equal(location(await run('/catalog.json')),'/releases/'+second+'/catalog.json');assert(oldURL.includes(id));
 for(const uri of ['/../secret','/%2e%2e/secret','/%2Fsecret','/%5Csecret','/%00secret','/.git/config']){
  const response=await run(uri);assert.equal(response.httpStatusCode,400,uri);assert.equal(response.errors,'');
 }
 for(const invalid of [canonical({...token,generation:true}),canonical({...token,generation:0}),canonical({...token,commit:'wrong'}),canonical({...token,previous_release_id:'../../x'}),canonical(token)+'\n','{"generation":1,'+canonical(token).slice(1)]){
  php.writeFile(file,invalid);assert.equal((await run('/')).httpStatusCode,503,invalid);
 }
 php.writeFile(file,canonical(token));php.writeFile('/www/public_html/releases/'+id+'/release.json',canonical({release_id:id,commit:'d'.repeat(40)}));assert.equal((await run('/')).httpStatusCode,503);
 php.exit();console.log('A2 PHP router checks passed: redirects/query/POST preservation, no-store, release binding, malformed state and unsafe paths.');
})().catch(e=>{console.error(e);process.exit(1)});
