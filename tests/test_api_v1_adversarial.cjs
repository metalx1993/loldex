/* Independent real-PHP requests in an isolated in-memory filesystem. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
const hash=v=>crypto.createHash('sha256').update(v).digest('hex');
const canonical=v=>JSON.stringify((function sorted(x){if(Array.isArray(x))return x.map(sorted);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,sorted(x[k])]));return x;})(v));
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 php.mkdir('/site');php.mkdir('/site/evidence-records');
 for(const name of ['api-v1.php','api-v1-core.php','search-engine.php'])php.writeFile('/site/'+name,fs.readFileSync('site/'+name));
 const entries=JSON.parse(fs.readFileSync('tests/test_advanced_search_vectors.json','utf8')).entries;
 const evidence={One:{raw:{original:'sensitive original evidence'},upstream_version:'a'.repeat(40)}};
 const files={
  'catalog.json':canonical({version:1,count:entries.length,entries})+'\n',
  'data.json':canonical({count:entries.length,entries})+'\n',
  'evidence.json':canonical({version:1,entries:Object.fromEntries(entries.map(e=>[e.id,evidence]))})+'\n',
  'graph.json':canonical({version:1,nodes:[],edges:[],diagnostics:[]})+'\n',
  'techniques.json':canonical({version:1,count:0,registry:{},techniques:[]})+'\n',
  'identities.json':canonical({version:1,count:0,identities:[]})+'\n',
  'registry-license.txt':'fixture license\n'
 };
 for(const entry of entries)files['evidence-records/'+hash(entry.id)+'.json']=canonical(evidence)+'\n';
 let manifest;
 function install(){for(const [name,raw] of Object.entries(files))php.writeFile('/site/'+name,raw);manifest={version:1,entries:entries.length,registry_checksum:'sha256:'+'c'.repeat(64),files:Object.fromEntries(Object.entries(files).map(([name,raw])=>[name,'sha256:'+hash(raw)]))};php.writeFile('/site/build-manifest.json',canonical(manifest)+'\n');}
 install();
 async function request(query='',headers={},method='GET',directory='/site'){
  const uri=directory+'/api-v1.php'+(query?'?'+query:'');const response=await php.run({scriptPath:directory+'/api-v1.php',relativeUri:uri,method,$_SERVER:{REQUEST_URI:uri,REQUEST_METHOD:method,QUERY_STRING:query,...headers},usePrimaryPhp:true});
  assert.equal(response.errors,'',query+' PHP diagnostic leaked');
  if(response.text){assert(!response.text.includes('/site/'),query+' leaked filesystem path');}
  return response;
 }
 const body=r=>JSON.parse(r.text);
 let response=await request('resource=entries');assert.equal(response.httpStatusCode,200);assert.equal(body(response).api_version,'1');
 for(const query of [
  'resource=search&q[]=Alpha','resource=search&q=Alpha&q=Beta','resource=entries&limit[]=1',
  'resource=entries&limit=1.5','resource=entries&limit=1e2','resource=entries&limit=01',
  'resource=entries&limit=-1','resource=entries&limit=201','resource=entries&limit=999999999999999999999999',
  'resource=entries&offset=10000001','resource=entries&offset=01','resource=entries&offset=-1',
  'resource=search&q=%FF','resource=search&q=%C0%AF','resource=search&q=%ED%A0%80','resource=search&q=%',
  'resource=search&q=%00','resource=search&q=%7F','resource=search&q=unknown%3Avalue',
  'resource=entry&id=a&id=b','resource=entry&id[]=a','resource=entries&unknown=1',
  'resource=entries&resource=search'
 ])assert.equal((await request(query)).httpStatusCode,400,query);
 for(const literal of ['a'.repeat(4097),'é'.repeat(2049),'('.repeat(17)+'a'+')'.repeat(17),Array(130).fill('a').join(' ')])assert.equal((await request('resource=search&q='+encodeURIComponent(literal))).httpStatusCode,400,'bounded grammar');
 assert.equal((await request('resource=search&q='+encodeURIComponent('é'.repeat(2048)))).httpStatusCode,200,'4096 UTF8bytes is allowed');
 for(const query of ['resource=entries&limit=1&offset=0','resource=entries&limit=200&offset=10000000'])assert.equal((await request(query)).httpStatusCode,200,query);
 for(const query of ['resource=entry&id=..%2Fsecret','resource=evidence&id=..%2Fsecret','resource=evidence&id=%2Fsite%2Fbuild-manifest.json'])assert.equal((await request(query)).httpStatusCode,404,query);
 response=await request('resource=evidence&id=a');assert.equal(response.httpStatusCode,200);assert.deepEqual(body(response).data,evidence);
 response=await request('resource=search&q='+encodeURIComponent('capability:A confidence:high'));
 assert.equal(response.httpStatusCode,200);assert.deepEqual(body(response).data.map(x=>x.entry.id),['b']);
 response=await request('resource=search&q=/releases/r-'+ 'f'.repeat(64)+'/');
 assert.equal(response.httpStatusCode,200);
 assert(!(response.headers['cache-control']||[]).join().includes('immutable'),'query text cannot impersonate an immutable release path');
 for(const [query,ids] of [
  ['resource=search&q='+encodeURIComponent('NOT (capability:A confidence:high)'),['a','c','d']],
  ['resource=search&capability=A&confidence=high',['b']],
  ['resource=search&q='+encodeURIComponent('capability:A OR capability:B')+'&confidence=high',['a','b','c']],
  ['resource=search&q='+encodeURIComponent('claim-exclusive confidence:high'),['b']],
  ['resource=search&q='+encodeURIComponent('Alpha confidence:high'),['a']],
  ['resource=search&source=Two&confidence=high',['c']]
 ]){const result=await request(query);assert.equal(result.httpStatusCode,200);assert.deepEqual(body(result).data.map(x=>x.entry.id),ids,query);}
 const valid=await request('resource=entries&limit=1');const etag=(valid.headers.etag||valid.headers.ETag||[])[0];assert(etag);
 const reordered=await request('limit=1&resource=entries');assert.equal((reordered.headers.etag||reordered.headers.ETag||[])[0],etag,'ETag uses normalized parameter order');
 response=await request('resource=entries&limit=1',{HTTP_IF_NONE_MATCH:etag});assert.equal(response.httpStatusCode,304);
 php.writeFile('/site/catalog.json','{}');response=await request('resource=entries&limit=1',{HTTP_IF_NONE_MATCH:etag});assert.equal(response.httpStatusCode,503,'304 must not bypass current dataset integrity');install();
 const shard='evidence-records/'+hash('a')+'.json';php.writeFile('/site/'+shard,'{}');assert.equal((await request('resource=evidence&id=a')).httpStatusCode,503);install();
 php.unlink('/site/'+shard);assert.equal((await request('resource=evidence&id=a')).httpStatusCode,503);install();
 php.writeFile('/site/build-manifest.json','{broken');assert.equal((await request('resource=entries')).httpStatusCode,503);install();
 assert.equal((await request('resource=entries',{},'POST')).httpStatusCode,405);
 response=await request('resource=entries',{},'HEAD');assert.equal(response.httpStatusCode,200);assert.equal(response.text,'');
 response=await request('',{},'OPTIONS');assert.equal(response.httpStatusCode,204);assert.equal(response.text,'');
 // A retained release must identify and read only its own immutable snapshot.
 php.mkdir('/releases');
 const payload={version:1,commit:'d'.repeat(40),files:{...manifest.files,'build-manifest.json':'sha256:'+hash(canonical(manifest)+'\n')}};
 for(const name of ['api-v1.php','api-v1-core.php','search-engine.php'])payload.files[name]='sha256:'+hash(fs.readFileSync('site/'+name));
 const release={...payload,release_id:'r-'+hash(canonical(payload))};const directory='/releases/'+release.release_id;
 php.mkdir(directory);php.mkdir(directory+'/evidence-records');
 for(const [name,raw] of Object.entries(files))php.writeFile(directory+'/'+name,raw);
 for(const name of ['api-v1.php','api-v1-core.php','search-engine.php'])php.writeFile(directory+'/'+name,fs.readFileSync('site/'+name));
 php.writeFile(directory+'/build-manifest.json',canonical(manifest)+'\n');php.writeFile(directory+'/release.json',canonical(release));
 response=await request('resource=entries',{},'GET',directory);assert.equal(response.httpStatusCode,200);assert.equal(body(response).dataset.release_id,release.release_id);assert.equal(body(response).dataset.commit,payload.commit);
 const oldTag=(response.headers.etag||response.headers.ETag||[])[0];
 const otherPayload={...payload,commit:'e'.repeat(40)};const otherRelease={...otherPayload,release_id:'r-'+hash(canonical(otherPayload))};const otherDirectory='/releases/'+otherRelease.release_id;
 php.mkdir(otherDirectory);php.mkdir(otherDirectory+'/evidence-records');
 for(const [name,raw] of Object.entries(files))php.writeFile(otherDirectory+'/'+name,raw);
 for(const name of ['api-v1.php','api-v1-core.php','search-engine.php'])php.writeFile(otherDirectory+'/'+name,fs.readFileSync('site/'+name));
 php.writeFile(otherDirectory+'/build-manifest.json',canonical(manifest)+'\n');php.writeFile(otherDirectory+'/release.json',canonical(otherRelease));
 const other=await request('resource=entries',{HTTP_IF_NONE_MATCH:oldTag},'GET',otherDirectory);assert.equal(other.httpStatusCode,200,'same datasets in another release must not reuse an ETag for different release metadata');
 assert.notEqual((other.headers.etag||other.headers.ETag||[])[0],oldTag);
 php.unlink(directory+'/release.json');
 assert.equal((await request('resource=entries',{},'GET',directory)).httpStatusCode,503,'retained release missing its authority cannot silently become a dev snapshot');
 php.writeFile(directory+'/release.json',canonical(release));
 php.writeFile(directory+'/catalog.json','{}');assert.equal((await request('resource=entries',{},'GET',directory)).httpStatusCode,503,'retained release must not fall back to healthy sibling/local catalog');
 php.writeFile(directory+'/catalog.json',files['catalog.json']);
 php.writeFile(directory+'/build-manifest.json',canonical({...manifest,registry_checksum:'sha256:'+'e'.repeat(64)})+'\n');
 assert.equal((await request('resource=root',{},'GET',directory)).httpStatusCode,503,'release must bind the exact build manifest even on root');
 php.exit();console.log('API v1 independent adversarial requests PASS');
})().catch(error=>{console.error(error);process.exit(1)});
