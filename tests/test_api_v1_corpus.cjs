/* Real generated corpus through hosting-compatible PHP 8.2; no network data acquisition. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
const engine=require('../site/search-engine.js');
(async()=>{
 const manifest=JSON.parse(fs.readFileSync('site/build-manifest.json','utf8'));
 const catalog=JSON.parse(fs.readFileSync('site/catalog.json','utf8'));
 assert.equal(catalog.count,manifest.entries);assert(catalog.count>0);
 const identities=JSON.parse(fs.readFileSync('site/identities.json','utf8'));
 const techniques=JSON.parse(fs.readFileSync('site/techniques.json','utf8'));
 const php=new PHP(await loadNodeRuntime('8.2',{emscriptenOptions:{processId:process.pid}}));
 php.mkdir('/development');php.mkdir('/development/evidence-records');
 const names=new Set(['api-v1.php','api-v1-core.php','search-engine.php','build-manifest.json',...Object.keys(manifest.files)]);
 for(const name of names)php.writeFile('/development/'+name,fs.readFileSync('site/'+name));
 php.writeFile('/development/limits.php',"<?php echo json_encode(array('version'=>PHP_VERSION,'memory_limit'=>ini_get('memory_limit')));");
 let probe=await php.run({scriptPath:'/development/limits.php',usePrimaryPhp:true});assert.equal(probe.errors,'');const limits=JSON.parse(probe.text);assert(limits.version.startsWith('8.2.'));
 const run=async q=>{const start=Date.now();const r=await php.run({scriptPath:'/development/api-v1.php',relativeUri:'/api-v1.php?'+q,method:'GET',$_SERVER:{REQUEST_METHOD:'GET',QUERY_STRING:q,REQUEST_URI:'/api-v1.php?'+q},usePrimaryPhp:true});assert.equal(r.errors,'',q);assert.equal(r.httpStatusCode,200,q+' '+r.text.slice(0,200));return {body:JSON.parse(r.text),elapsed_ms:Date.now()-start};};
 const timings={};
 for(const resource of ['root','entries','graph','techniques','identities']){const r=await run('resource='+resource);assert.equal(r.body.dataset.entry_count,catalog.count);timings[resource]=r.elapsed_ms;}
 const first=catalog.entries[0],id=encodeURIComponent(first.id);
 const detail=await run('resource=entry&id='+id);assert.equal(detail.body.data.entry.id,first.id);
 const evidence=await run('resource=evidence&id='+id);const shard='evidence-records/'+crypto.createHash('sha256').update(first.id).digest('hex')+'.json';assert.deepEqual(evidence.body.data,JSON.parse(fs.readFileSync('site/'+shard,'utf8')));
 if(techniques.techniques.length){const t=techniques.techniques[0];await run('resource=technique&id='+encodeURIComponent(t.id));}
 if(identities.entities.length){const e=identities.entities[0];const r=await run('resource=identity&id='+encodeURIComponent(e.id));assert.equal(r.body.data.entity.id,e.id);}
 for(const alias of identities.aliases){const r=await run('resource=resolve&id='+encodeURIComponent(alias.old_entry_id));assert.equal(r.body.data.kind,'alias');assert.deepEqual(r.body.data.alias,alias);}
 const queries=['source:GTFOBins capability:command-execution','platform:windows confidence:high','NOT (capability:discovery AND confidence:high)','certutil OR source:WADComs'];
 for(const q of queries){const expected=engine.search(catalog.entries,q,{offset:0,limit:5});const actual=await run('resource=search&limit=5&q='+encodeURIComponent(q));assert.deepEqual(actual.body.data,expected.results,q);assert.deepEqual(actual.body.facets,expected.facets,q);assert.equal(actual.body.pagination.total,expected.total);timings[q]=actual.elapsed_ms;}
 {
  let q='NoSuchLiteralForBoundedProbe';for(let i=0;i<5;i++)q='NOT ((freshness:NOT_OBSERVED OR freshness:NOT_OBSERVED OR freshness:NOT_OBSERVED OR freshness:NOT_OBSERVED) AND '+q+')';
  const r=await run('resource=search&limit=1&q='+encodeURIComponent(q));timings.worst_full_corpus=r.elapsed_ms;assert.equal(r.body.pagination.total,catalog.count);const expected=engine.search(catalog.entries,q,{limit:1});assert.deepEqual(r.body.data,expected.results);assert.deepEqual(r.body.facets,expected.facets);assert(r.elapsed_ms<10000,'Worst valid full-corpus search exceeds local 10s gate');console.log('Worst valid full corpus API probe ms='+r.elapsed_ms);
 }
 // Source-only qualifiers must constrain claim-backed facets/text but preserve metadata predicates.
 const base=JSON.parse(fs.readFileSync('tests/test_advanced_search_vectors.json','utf8')).entries[0];
 const synthetic=structuredClone(base);synthetic.id='multi';synthetic.name='Alpha';synthetic.sources=[{project:'A'},{project:'B'}];synthetic.capabilities=['exclusiveclaim'];synthetic.claims={capabilities:[{value:'exclusiveclaim',provenance:{type:'adapter',source:'A'},confidence:{level:'high'}}]};
 php.writeFile('/development/source-test.json',JSON.stringify([synthetic,{id:'bare',name:'Bare',sources:[{project:'B'}],claims:{}}]));
 php.writeFile('/development/source-test.php',`<?php require '/development/search-engine.php';$entries=json_decode(file_get_contents('/development/source-test.json'));$out=array();foreach(array('source:B capability:exclusiveclaim','source:B exclusiveclaim','source:B Alpha','source:B') as $q)$out[]=loldex_search($entries,$q);echo json_encode($out);`);
 probe=await php.run({scriptPath:'/development/source-test.php',usePrimaryPhp:true});assert.equal(probe.errors,'');const actual=JSON.parse(probe.text);for(const [i,q]of ['source:B capability:exclusiveclaim','source:B exclusiveclaim','source:B Alpha','source:B'].entries())assert.deepEqual(actual[i],engine.search([synthetic,{id:'bare',name:'Bare',sources:[{project:'B'}],claims:{}}],q));assert.deepEqual(actual.map(r=>r.total),[0,0,1,2]);
 let worst='Alpha';for(let i=0;i<5;i++)worst='NOT ((Alpha OR Alpha OR Alpha OR Alpha) AND '+worst+')';
 php.writeFile('/development/worst.php',`<?php require '/development/search-engine.php';$entry=json_decode(file_get_contents('/development/source-test.json'))[0];$parsed=loldex_search_parse(base64_decode('${Buffer.from(worst).toString('base64')}'));$start=microtime(true);for($i=0;$i<50;$i++)loldex_search_evaluate($entry,$parsed);echo json_encode(array('evaluations'=>50,'elapsed_ms'=>(microtime(true)-$start)*1000));`);
 probe=await php.run({scriptPath:'/development/worst.php',usePrimaryPhp:true});assert.equal(probe.errors,'');const worstTiming=JSON.parse(probe.text);assert(worstTiming.elapsed_ms<3000);timings.worst_nested_50=worstTiming.elapsed_ms;
 php.exit();console.log('API corpus PHP '+limits.version+' PASS: '+catalog.count+' entries, all resources, '+identities.aliases.length+' real aliases, evidence shard, full JS search parity; memory_limit='+limits.memory_limit+'; timings_ms='+JSON.stringify(timings));
})().catch(error=>{console.error(error);process.exit(1)});
