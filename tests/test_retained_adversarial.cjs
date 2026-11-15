/* Independent retained-release bridge probes: VFS only, no HTTP/mail. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
const digest=x=>'sha256:'+crypto.createHash('sha256').update(x).digest('hex');
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 for(const p of ['/host','/host/public_html','/host/public_html/releases','/host/loldex-control','/host/loldex-control/tools','/host/loldex-control/tools/security'])php.mkdir(p);
 for(const [to,from]of [['loldex-retained.php','deployment/siteground/loldex-retained.php'],['loldex-router.php','deployment/siteground/loldex-router.php']])php.writeFile('/host/public_html/'+to,fs.readFileSync(from));
 php.writeFile('/host/loldex-control/tools/security/request-guard.php',fs.readFileSync('site/request-guard.php'));
 const oldApi=`<?php header('Content-Type: application/json');$data=json_decode(file_get_contents(__DIR__.'/data.json'),true);echo json_encode(['pinned'=>basename(__DIR__),'count'=>count($data['entries']),'query'=>$_GET]);`;
 const oldContact=`<?php echo '{"old_handler_executed":true}';`;
 const create=(count,guarded=false)=>{
  const files={'api.php':Buffer.from(oldApi),'contact.php':Buffer.from(oldContact),'data.json':Buffer.from(JSON.stringify({entries:Array.from({length:count},(_,i)=>({id:'entry'+i}))}))};
  if(guarded)files['request-guard.php']=fs.readFileSync('site/request-guard.php');
  const payload={version:1,commit:'a'.repeat(40),files:Object.fromEntries(Object.entries(files).map(([k,v])=>[k,digest(v)]))};
  const id='r-'+crypto.createHash('sha256').update(canonical(payload)).digest('hex');const folder='/host/public_html/releases/'+id;php.mkdir(folder);
  for(const [name,bytes]of Object.entries(files))php.writeFile(folder+'/'+name,bytes);php.writeFile(folder+'/release.json',canonical({...payload,release_id:id}));return {id,folder};
 };
 const old=create(2),other=create(3),modern=create(4,true);
 const token=id=>canonical({version:1,generation:1,release_id:id,previous_release_id:null,commit:'a'.repeat(40)});
 php.writeFile('/host/loldex-control/active.json',token(modern.id));
 const run=async(uri,method='GET',ip='192.0.2.1')=>{
  const response=await php.run({scriptPath:'/host/public_html/loldex-retained.php',method,relativeUri:uri,$_SERVER:{REQUEST_URI:uri,QUERY_STRING:uri.split('?')[1]||'',REQUEST_METHOD:method,DOCUMENT_ROOT:'/host/public_html',REMOTE_ADDR:ip},usePrimaryPhp:true});
  assert.equal(response.errors,'');assert(!response.text.includes('/host/'),'no filesystem path disclosure');return response;
 };
 let r=await run('/releases/'+old.id+'/api.php?q=tar');assert.equal(r.httpStatusCode,200);let data=JSON.parse(r.text);assert.equal(data.pinned,old.id);assert.equal(data.count,2);assert.equal(data.query.q,'tar');
 for(const suffix of ['api.php/extra','api.php/../contact.php','api-v1.php/extra','api/v1/search/extra','../api.php','contact.php/extra']){r=await run('/releases/'+old.id+'/'+suffix);assert.equal(r.httpStatusCode,400,suffix);assert(!r.text.includes('old_handler_executed'));}
 for(const q of ['q=x&q=y','q=x&%71=y','q[]=x','q=%ff','q=%ZZ','q=%00','limit=1e2','offset=10000001']){r=await run('/releases/'+old.id+'/api.php?'+q);assert.equal(r.httpStatusCode,400,q);}
 r=await run('/releases/'+old.id+'/contact.php','POST');assert.equal(r.httpStatusCode,307);assert.equal((r.headers.location||[])[0],'/releases/'+modern.id+'/contact.php');assert(!r.text.includes('old_handler_executed'));
 php.writeFile('/host/loldex-control/active.json',token(old.id));r=await run('/releases/'+old.id+'/contact.php','POST');assert.equal(r.httpStatusCode,503,'rollback must not loop into unguarded handler');assert(!r.text.includes('old_handler_executed'));
 r=await run('/releases/'+old.id+'/api.php','HEAD');assert.equal(r.httpStatusCode,200);assert.equal(r.text,'');
 r=await run('/releases/'+old.id+'/api.php','OPTIONS');assert.equal(r.httpStatusCode,204);assert.equal(r.text,'');assert.equal((r.headers['access-control-allow-origin']||[])[0],'*');
 // Same quota across multiple retained datasets; initial successful GET + HEAD consume two.
 for(let i=0;i<118;i++){r=await run('/releases/'+(i%2?other.id:old.id)+'/api.php');assert.equal(r.httpStatusCode,200);data=JSON.parse(r.text);assert.equal(data.count,i%2?3:2);}
 r=await run('/releases/'+other.id+'/api.php');assert.equal(r.httpStatusCode,429);assert(Number((r.headers['retry-after']||[])[0])>0);
 // Tampering cannot turn a bound endpoint or guard marker into unchecked execution.
 php.writeFile(old.folder+'/api.php','<?php echo "TAMPERED";');r=await run('/releases/'+old.id+'/api.php','GET','192.0.2.2');assert.equal(r.httpStatusCode,503);assert(!r.text.includes('TAMPERED'));
 php.writeFile(modern.folder+'/request-guard.php','<?php echo "TAMPERED-GUARD";');r=await run('/releases/'+modern.id+'/api.php','GET','192.0.2.3');assert.equal(r.httpStatusCode,503);assert(!r.text.includes('TAMPERED'));
 php.exit();console.log('Independent retained bridge passed: pinned old data, malformed paths/queries, no old contact execution, safe rollback, HEAD/CORS, shared quota and hash-bound endpoint/marker. Apache rewrite/provider behavior is outside this VFS test.');
})().catch(error=>{console.error(error);process.exit(1)});
