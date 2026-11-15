/* Stable bridge against retained immutable old and current real PHP endpoints. No mail. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 const root='/host/public_html',control='/host/loldex-control';
 for(const p of ['/host',root,root+'/releases',control,control+'/tools',control+'/tools/security'])php.mkdir(p);
 for(const name of ['loldex-retained.php','loldex-router.php'])php.writeFile(root+'/'+name,fs.readFileSync('deployment/siteground/'+name));
 php.writeFile(control+'/tools/security/request-guard.php',fs.readFileSync('site/request-guard.php'));
 const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
 const sha=raw=>'sha256:'+crypto.createHash('sha256').update(raw).digest('hex');
 // Frozen real application sources; no runtime Git or history-depth dependency.
 const base={};
 base['catalog.json']=Buffer.from(canonical({version:1,count:0,entries:[]})+'\n');
 base['graph.json']=Buffer.from(canonical({version:1,nodes:[],edges:[],diagnostics:[]})+'\n');
 base['techniques.json']=Buffer.from(canonical({version:1,count:0,registry:{},techniques:[]})+'\n');
 base['identities.json']=Buffer.from(canonical({version:1,entities:[],candidates:[],entry_index:{},aliases:[]})+'\n');
 base['data.json']=Buffer.from(JSON.stringify({entries:[{id:'retained/tar',name:'tar',platform:'linux',privilege_required:'sudo',type:'binary',aliases:['archive'],capabilities:['read'],phases:['execution']}]}));
 const build=(guarded=false,override={})=>{
  const files={...base};
  for(const name of ['api.php','api-v1.php','api-v1-core.php','search-engine.php'])files[name]=guarded?fs.readFileSync('site/'+name):fs.readFileSync('tests/fixtures/retained-pre-hardening/'+name);
  files['contact.php']=guarded?fs.readFileSync('site/contact.php'):Buffer.from("<?php throw new RuntimeException('OLD MAIL HANDLER MUST NEVER EXECUTE');");
  if(guarded)files['request-guard.php']=fs.readFileSync('site/request-guard.php');
  Object.assign(files,override);
  const manifest={version:1,entries:0,registry_checksum:'sha256:'+'c'.repeat(64),files:{}};
  for(const name of Object.keys(files))if(name.endsWith('.json'))manifest.files[name]=sha(files[name]);
  files['build-manifest.json']=Buffer.from(canonical(manifest)+'\n');
  const release={version:1,commit:'a'.repeat(40),files:{}};for(const [name,raw]of Object.entries(files))release.files[name]=sha(raw);
  release.release_id='r-'+crypto.createHash('sha256').update(canonical(release)).digest('hex');
  const folder=root+'/releases/'+release.release_id;php.mkdir(folder);for(const [name,raw]of Object.entries(files))php.writeFile(folder+'/'+name,raw);php.writeFile(folder+'/release.json',canonical(release));return release;
 };
 const old=build(),current=build(true);
 const active=release=>php.writeFile(control+'/active.json',canonical({version:1,generation:1,release_id:release.release_id,previous_release_id:null,commit:release.commit}));active(current);
 const uri=(release,suffix)=>'/releases/'+release.release_id+'/'+suffix;
 const run=async(url,method='GET',body='')=>php.run({scriptPath:root+'/loldex-retained.php',relativeUri:url,method,body:Buffer.from(body),headers:{'Content-Type':'application/json'},$_SERVER:{REQUEST_URI:url,REQUEST_METHOD:method,CONTENT_TYPE:'application/json',CONTENT_LENGTH:String(Buffer.byteLength(body)),DOCUMENT_ROOT:root,REMOTE_ADDR:'192.0.2.5'},usePrimaryPhp:true});
 const header=(r,k)=>(r.headers[k.toLowerCase()]||r.headers[k]||[])[0];
 const check=(r,status)=>{assert.equal(r.errors,'');assert.equal(r.httpStatusCode,status,r.text);};
 let r=await run(uri(old,'api.php'));check(r,200);assert.equal(JSON.parse(r.text).count,1);
 r=await run(uri(old,'api/search?q=archive&os=linux'));check(r,200);assert.equal(JSON.parse(r.text).results[0].id,'retained/tar');
 r=await run(uri(old,'api-v1.php'));check(r,200);assert.equal(JSON.parse(r.text).dataset.release_id,old.release_id);
 r=await run(uri(old,'api/v1/search?q=tar%0A'));check(r,200);assert.equal(JSON.parse(r.text).dataset.release_id,old.release_id);
 for(const endpoint of ['api.php','api-v1.php']){r=await run(uri(old,endpoint),'HEAD');check(r,200);assert.equal(r.text,'');r=await run(uri(old,endpoint),'POST');check(r,405);}
 for(const suffix of ['api.php?q[]=x','api.php?q=x&%71=y','api.php?offset=10000001','api.php?q=%ff','api-v1.php?resource[]=entries','api/v1/search?resource=search','api/search?action=search'])check(await run(uri(old,suffix)),400);
 for(const suffix of ['api.php/extra','api-v1.php/extra','api.php%2fextra','api/v1/../search','api/v1/search%2Fextra','%61pi.php'])check(await run(uri(old,suffix)),400);
 const quota=()=>JSON.parse(php.readFileAsText(control+'/rate-limits/state.json')).global.api[1];let before=quota();
 r=await run(uri(old,'api/v1/search'),'OPTIONS');check(r,204);assert.equal(r.text,'');assert.equal(quota(),before);
 // A guarded release executes its own guard once; the bridge never preloads it.
 r=await run(uri(current,'api.php'));check(r,200);assert.equal(quota(),before+1);
 r=await run(uri(current,'api-v1.php'));check(r,200);assert.equal(JSON.parse(r.text).dataset.release_id,current.release_id);assert.equal(quota(),before+2);
 const honeypot=JSON.stringify({name:'No mail',email:'probe@example.invalid',message:'probe',botcheck:'bot'});
 r=await run(uri(old,'contact.php'),'POST',honeypot);check(r,307);assert.equal(header(r,'location'),uri(current,'contact.php'));
 r=await run(uri(current,'contact.php'),'POST',honeypot);check(r,200);assert.equal(JSON.parse(r.text).success,true);
 active(old);r=await run(uri(old,'contact.php'),'POST',honeypot);check(r,503);assert.equal(header(r,'location'),undefined);active(current);
 // Quotas cross old/new releases and cannot be bypassed by switching URLs.
 before=quota();for(let i=before;i<120;i++)check(await run(uri(old,'api.php')),200);
 r=await run(uri(old,'api.php'));check(r,429);assert(Number(header(r,'retry-after'))>0);
 // Rejected clients never trigger hashing/parsing of retained dataset payloads.
 php.writeFile(root+'/releases/'+old.release_id+'/data.json','tampered-after-quota');
 r=await run(uri(old,'api.php'));check(r,429);
 r=await run(uri(old,'api-v1.php'),'HEAD');check(r,429);assert.equal(r.text,'');
 r=await run(uri(current,'api.php'));check(r,429);
 // A declared-but-altered guarded marker fails closed before PHP execution.
 php.writeFile(root+'/releases/'+current.release_id+'/request-guard.php','<?php echo "TAMPER";');r=await run(uri(current,'api.php'));check(r,503);assert(!r.text.includes('TAMPER'));
 php.exit();console.log('Retained bridge PASS: frozen old/current real APIs, pinned IDs, pretty routes, strict queries/paths, shared quota, HEAD/OPTIONS, no double guard, old contact307 and rollback503, marker tamper.');
})().catch(error=>{console.error(error);process.exit(1)});
