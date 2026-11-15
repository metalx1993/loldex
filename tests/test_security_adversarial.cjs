/* Independent negative tests: isolated PHP VFS, no public host or mail() calls. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 for(const p of ['/host','/host/public_html','/host/public_html/releases','/host/loldex-control'])php.mkdir(p);
 const first='/host/public_html/releases/r-'+'a'.repeat(64),second='/host/public_html/releases/r-'+'b'.repeat(64);
 for(const p of [first,second]){php.mkdir(p);php.writeFile(p+'/request-guard.php',fs.readFileSync('site/request-guard.php'));}
 const run=async(code,folder=first)=>{
  php.writeFile(folder+'/probe.php',`<?php require __DIR__.'/request-guard.php';$_SERVER['DOCUMENT_ROOT']='/host/public_html';${code}`);
  const r=await php.run({scriptPath:folder+'/probe.php',usePrimaryPhp:true});assert.equal(r.errors,'',r.errors);return JSON.parse(r.text);
 };
 // WASM does not implement OS umask for fopen: seed private fixtures explicitly.
 await run(`mkdir('/host/loldex-control/rate-limits',0700);file_put_contents('/host/loldex-control/rate-limits/state.json','');chmod('/host/loldex-control/rate-limits/state.json',0600);file_put_contents('/host/loldex-control/rate-limits/key',str_repeat('x',32));chmod('/host/loldex-control/rate-limits/key',0600);echo 'null';`);
 let r=await run(`$_SERVER['REMOTE_ADDR']='2001:db8::1';$out=[];for($i=0;$i<3;$i++)$out[]=loldex_guard_rate('contact',true);$_SERVER['REMOTE_ADDR']='2001:0db8:0000:0000:0000:0000:0000:0001';$_SERVER['HTTP_X_FORWARDED_FOR']='198.51.100.2';$out[]=loldex_guard_rate('contact',true);echo json_encode($out);`);

 assert.deepEqual(r.map(x=>x.status),[200,200,200,429],'equivalent IPv6 and spoofed forwarding share client quota');assert(r[3].retry_after>0);
 r=await run(`$_SERVER['REMOTE_ADDR']='2001:db8::1';echo json_encode(loldex_guard_rate('contact',true));`,second);
 assert.equal(r.status,429,'retained releases share the same private limiter');
 r=await run(`$out=[];for($i=2;$i<=10;$i++){$_SERVER['REMOTE_ADDR']='192.0.2.'.$i;for($j=0;$j<3;$j++)$out[]=loldex_guard_rate('contact',true);}$_SERVER['REMOTE_ADDR']='192.0.2.11';$out[]=loldex_guard_rate('contact',true);echo json_encode($out);`);
 assert.equal(r.filter(x=>x.allowed).length,27);assert.equal(r.at(-1).status,429,'different IPs cannot evade global mail cap');
 r=await run(`$raw=file_get_contents('/host/loldex-control/rate-limits/state.json');echo json_encode(['state'=>$raw,'dir'=>fileperms('/host/loldex-control/rate-limits')&0777,'state_mode'=>fileperms('/host/loldex-control/rate-limits/state.json')&0777,'key_mode'=>fileperms('/host/loldex-control/rate-limits/key')&0777]);`);
 assert(!r.state.includes('192.0.2.')&&!r.state.includes('2001:'),'state stores keyed digests rather than addresses');assert.equal(r.dir,448);assert.equal(r.state_mode,384);assert.equal(r.key_mode,384);
 r=await run(`file_put_contents('/host/loldex-control/rate-limits/state.json','{broken');$_SERVER['REMOTE_ADDR']='192.0.2.12';echo json_encode(loldex_guard_rate('api',true));`);assert.equal(r.status,503,'corrupt private state fails closed');
 r=await run(`file_put_contents('/host/loldex-control/rate-limits/state.json',str_repeat('x',262145));$_SERVER['REMOTE_ADDR']='192.0.2.12';echo json_encode(loldex_guard_rate('api',true));`);assert.equal(r.status,503,'oversized state fails closed');
 // Only malformed bodies or honeypot submissions: this suite never invokes mail().
 php.writeFile(first+'/contact.php',fs.readFileSync('site/contact.php'));
 const body=JSON.stringify({name:'Independent probe',email:'probe@example.invalid',message:'test',botcheck:'robot'});
 for(const length of ['-1','1e2',' 5','5, 5','0','16385']){
  const response=await php.run({scriptPath:first+'/contact.php',method:'POST',body:Buffer.from(body),headers:{'Content-Type':'application/json'},$_SERVER:{REQUEST_METHOD:'POST',CONTENT_TYPE:'application/json',CONTENT_LENGTH:length,REMOTE_ADDR:'192.0.2.20',DOCUMENT_ROOT:'/host/public_html'},usePrimaryPhp:true});
  assert.equal(response.errors,'');assert.equal(response.httpStatusCode,length==='16385'?413:400,'malformed/mismatched body length '+length);assert(!response.text.includes('/host'));assert.doesNotThrow(()=>JSON.parse(response.text));
 }
 const head=await php.run({scriptPath:first+'/contact.php',method:'HEAD',$_SERVER:{REQUEST_METHOD:'HEAD'},usePrimaryPhp:true});assert.equal(head.httpStatusCode,405);assert.equal(head.text,'');assert.equal(head.errors,'');
 const invalidJson=['{"name":"a","\\u006eame":"b"}','{"name":"a","name":"b"}','{"name":{}}','["a"]','null','{"name":"a",}'];
 const invalidPairs=['name=x&%6eame=y','name%5b%5d=x','name=x&&email=y','name=%ff','name=%00','name=%ZZ'];
 r=await run(`$json=json_decode(base64_decode('${Buffer.from(JSON.stringify(invalidJson)).toString('base64')}'));$pairs=json_decode(base64_decode('${Buffer.from(JSON.stringify(invalidPairs)).toString('base64')}'));$out=[];foreach($json as $raw){try{loldex_guard_json_fields($raw);$out[]=false;}catch(Throwable $e){$out[]=true;}}foreach($pairs as $raw){try{loldex_guard_pairs($raw);$out[]=false;}catch(Throwable $e){$out[]=true;}}echo json_encode($out);`);
 assert(r.every(Boolean),'duplicate/ambiguous/invalid parameter syntax rejected');
 php.exit();console.log('Independent guard adversarial checks passed: canonical IPv6, forwarded-IP spoofing, shared retained-release/global quota, private hashes/modes, corrupt/oversized state and duplicate parser spellings. Native OS flock concurrency is not asserted by WASM.');
})().catch(error=>{console.error(error);process.exit(1)});
