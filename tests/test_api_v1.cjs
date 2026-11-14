/* Real PHP/WASM integration + JS/PHP advanced-search semantic conformance. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
const engine=require('../site/search-engine.js');
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 php.mkdir('/www');php.writeFile('/www/search-engine.php',fs.readFileSync('site/search-engine.php'));
 const fixture=JSON.parse(fs.readFileSync('tests/test_advanced_search_vectors.json','utf8'));
 php.writeFile('/www/vectors.json',JSON.stringify({entries:fixture.entries,cases:fixture.cases}));
 const code=`<?php require '/www/search-engine.php';$fixture=json_decode(file_get_contents('/www/vectors.json'));$out=array();foreach($fixture->cases as $case){$out[]=array('query'=>$case->query,'ast'=>loldex_search_parse($case->query),'result'=>loldex_search($case->entries??$fixture->entries,$case->query));}echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);`;
 php.writeFile('/www/check.php',code);
 let response=await php.run({scriptPath:'/www/check.php',usePrimaryPhp:true});assert.equal(response.errors,'');
 const results=JSON.parse(response.text);assert.equal(results.length,fixture.cases.length);
 for(let i=0;i<results.length;i++){
  const q=results[i].query, expected=engine.search(fixture.cases[i].entries||fixture.entries,q);
  assert.deepEqual(results[i].ast,engine.parse(q),'AST '+q);
  assert.deepEqual(results[i].result,expected,'search/reasons/facets '+q);
  assert.deepEqual(results[i].result.results.map(r=>r.entry.id),fixture.cases[i].ids,'known IDs '+q);
 }
 for(const q of fixture.errors){
  const encoded=Buffer.from(JSON.stringify(q)).toString('base64');
  php.writeFile('/www/error.php',`<?php require '/www/search-engine.php';try{$q=json_decode(base64_decode('${encoded}'));loldex_search_parse($q);echo 'ACCEPTED';}catch(Throwable $e){echo 'REJECTED';}`);
  response=await php.run({scriptPath:'/www/error.php',usePrimaryPhp:true});assert.equal(response.errors,'');assert.equal(response.text,'REJECTED',JSON.stringify(q));
 }

 const canonical=value=>{
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
  return JSON.stringify(value);
 };
 const sha=raw=>'sha256:'+crypto.createHash('sha256').update(raw).digest('hex');
 const files={};
 for(const name of ['api-v1.php','api-v1-core.php','search-engine.php'])files[name]=fs.readFileSync('site/'+name);
 files['catalog.json']=Buffer.from(canonical({version:1,count:fixture.entries.length,entries:fixture.entries})+'\n');
 files['graph.json']=Buffer.from(canonical({version:1,nodes:[],edges:[],diagnostics:[]})+'\n');
 files['techniques.json']=Buffer.from(canonical({version:1,count:0,registry:{},techniques:[]})+'\n');
 files['identities.json']=Buffer.from(canonical({version:1,entities:[],candidates:[],entry_index:{},aliases:[{id:'alias:single',old_entry_id:'old-single',new_entry_ids:['a'],status:'active',evidence:'pinned-proof'},{id:'alias:split',old_entry_id:'old-split',new_entry_ids:['a','b'],status:'split',evidence:'pinned-proof'}]})+'\n');
 for(const e of fixture.entries){const hash=crypto.createHash('sha256').update(e.id).digest('hex');files['evidence-records/'+hash+'.json']=Buffer.from('{"Fixture":{"raw":{"empty_map":{},"empty_list":[],"big":18446744073709551615}}}\n');}
 const manifest={version:1,entries:fixture.entries.length,registry_checksum:'sha256:'+'c'.repeat(64),files:{}};
 for(const name of Object.keys(files))if(name.endsWith('.json'))manifest.files[name]=sha(files[name]);
 files['build-manifest.json']=Buffer.from(canonical(manifest)+'\n');
 const release={version:1,commit:'a'.repeat(40),files:{}};
 for(const [name,raw]of Object.entries(files))release.files[name]=sha(raw);
 release.release_id='r-'+crypto.createHash('sha256').update(canonical(release)).digest('hex');
 const folder='/www/releases/'+release.release_id;php.mkdir('/www/releases');php.mkdir(folder);php.mkdir(folder+'/evidence-records');
 for(const [name,raw]of Object.entries(files))php.writeFile(folder+'/'+name,raw);
 php.writeFile(folder+'/release.json',canonical(release));
 const run=async(q='',method='GET',etag=null)=>php.run({scriptPath:folder+'/api-v1.php',relativeUri:'/releases/'+release.release_id+'/api-v1.php?'+q,method,$_SERVER:{REQUEST_METHOD:method,QUERY_STRING:q,REQUEST_URI:'/releases/'+release.release_id+'/api-v1.php?'+q,...(etag?{HTTP_IF_NONE_MATCH:etag}:{})},usePrimaryPhp:true});
 const header=(r,key)=>(r.headers[key.toLowerCase()]||r.headers[key]||[])[0];
 let api=await run();assert.equal(api.errors,'');assert.equal(api.httpStatusCode,200);let body=JSON.parse(api.text);assert.equal(body.api_version,'1');assert.equal(body.dataset.release_id,release.release_id);assert(body.data.resources.includes('search'));
 api=await run('resource=entries&limit=1&offset=0');assert.equal(api.httpStatusCode,200);body=JSON.parse(api.text);assert.equal(body.data.length,1);assert.equal(body.pagination.total,fixture.entries.length);assert.equal(body.data[0].id,'a');
 api=await run('resource=search&q='+encodeURIComponent('capability:A confidence:high'));assert.equal(api.errors,'');assert.equal(api.httpStatusCode,200);body=JSON.parse(api.text);assert.deepEqual(body.data.map(x=>x.entry.id),engine.search(fixture.entries,'capability:A confidence:high').results.map(x=>x.entry.id));
 api=await run('resource=evidence&id=a');assert.equal(api.httpStatusCode,200);body=JSON.parse(api.text);assert(!Array.isArray(body.data.Fixture.raw.empty_map));assert(Array.isArray(body.data.Fixture.raw.empty_list));assert(api.text.includes('"big":18446744073709551615'));
 api=await run('resource=entry&id=a&include=evidence');assert.equal(api.httpStatusCode,200);body=JSON.parse(api.text);assert.equal(body.data.entry.id,'a');assert(body.data.evidence.Fixture);assert(api.text.includes('"big":18446744073709551615'));
 let ordinary=await run('resource=entries&limit=1');const etag=header(ordinary,'etag');assert(etag);api=await run('limit=1&resource=entries','GET',etag);assert.equal(api.httpStatusCode,304);assert.equal(api.text,'');
 const head=await run('resource=entries&limit=1','HEAD');assert.equal(head.httpStatusCode,200);assert.equal(head.text,'');assert.equal(header(head,'etag'),etag);assert.equal(Number(header(head,'content-length')),Buffer.byteLength(ordinary.text));
 for(const q of ['resource=entries&limit=01','resource=entries&limit=1.0','resource=entries&offset=-1','resource=entries&limit=201','resource=entries&offset=10000001','resource=entries&limit[]=1','resource=entries&limit=1&limit=2','resource=entries&%6cimit=1&limit=2','resource=entry&id=%ff','resource=entry&id=%00','resource=search&q=%ZZ']){api=await run(q);assert.equal(api.errors,'');assert.equal(api.httpStatusCode,400,q);assert(JSON.parse(api.text).error.code);}
 for(const [id,kind]of [['a','entry'],['old-single','alias'],['old-split','alias']]){api=await run('resource=resolve&id='+id);assert.equal(api.httpStatusCode,200);const resolved=JSON.parse(api.text).data;assert.equal(resolved.kind,kind);if(id==='old-split'){assert.deepEqual(resolved.alias.new_entry_ids,['a','b']);assert.equal(resolved.alias.status,'split');}}
 api=await run('resource=entry&id=old-single');assert.equal(api.httpStatusCode,404);
 api=await run('resource=entry&id=../../secret');assert.equal(api.httpStatusCode,404);assert(!api.text.includes('/www'));
 api=await run('resource=entries','POST');assert.equal(api.httpStatusCode,405);const preflight=await run('','OPTIONS');assert.equal(preflight.httpStatusCode,204);assert.equal(header(preflight,'access-control-allow-origin'),'*');assert(header(preflight,'access-control-allow-headers').includes('If-None-Match'));assert.equal(header(ordinary,'access-control-allow-origin'),'*');
 php.exit();console.log('API real PHP passed: '+results.length+' valid / '+fixture.errors.length+' invalid search vectors, full JS parity; versioned routes, release/manifest binding, raw evidence fidelity, bounded requests, GET/HEAD/OPTIONS and verified ETags.');
})().catch(error=>{console.error(error);process.exit(1)});
