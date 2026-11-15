/* Real PHP integration: no mail invocation and no external requests. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const modules=process.env.LOLDEX_PHP_WASM_MODULES||path.resolve('work/php-runtime/node_modules');
const {PHP}=require(path.join(modules,'@php-wasm/universal'));
const {loadNodeRuntime}=require(path.join(modules,'@php-wasm/node'));
(async()=>{
 const php=new PHP(await loadNodeRuntime('8.3',{emscriptenOptions:{processId:process.pid}}));
 php.mkdir('/www'); php.mkdir('/private');
 for(const name of ['api.php','contact.php','request-guard.php'])php.writeFile('/www/'+name,fs.readFileSync('site/'+name));
 php.writeFile('/www/data.json',JSON.stringify({entries:[{id:'gtfobins/tar',name:'tar',platform:'linux',privilege_required:'sudo',type:'binary',aliases:['archive'],capabilities:['read'],phases:['execution']}]}));
 const header=(r,key)=>(r.headers[key.toLowerCase()]||r.headers[key]||[])[0];
 let configured=false;
 const run=async(file,q='',method='GET',body='',type='application/json',extra={})=>php.run({scriptPath:'/www/'+file,relativeUri:'/'+file+(q?'?'+q:''),method,env:configured?{LOLDEX_RATE_LIMIT_DIR:'/private/quota'}:{},body:Buffer.from(body),headers:{'Content-Type':type},$_SERVER:{REQUEST_METHOD:method,QUERY_STRING:q,CONTENT_TYPE:type,CONTENT_LENGTH:String(Buffer.byteLength(body)),REMOTE_ADDR:'192.0.2.1',...extra},usePrimaryPhp:true});
 const check=(r,status)=>{assert.equal(r.errors,'');assert.equal(r.httpStatusCode,status,r.text);if(r.text)assert.doesNotThrow(()=>JSON.parse(r.text));};
 for(const q of ['', 'action=stats','action=search&q=archive&os=linux&priv=sudo&cap=read&phase=execution&type=binary','action=entries&limit=999&offset=0','action=entry&id=gtfobins%2Ftar'])check(await run('api.php',q),200);
 let response=await run('api.php','action=entries&limit=999');assert.equal(JSON.parse(response.text).limit,200);assert.equal(JSON.parse(response.text).results[0].id,'gtfobins/tar');
 check(await run('api.php','action=entry&id=absent'),404);
 for(const q of ['q[]=x','q=x&q=y','q=x&%71=y','q=%ff','q=%ZZ','limit=-1','offset=10000001','q='+('a'.repeat(4097)),'constructor=bad','q=%00','q=%0a'])check(await run('api.php',q),400);
 check(await run('api.php','','POST'),405);
 response=await run('api.php','','HEAD');check(response,200);assert.equal(response.text,'');
 response=await run('api.php','','OPTIONS');check(response,204);assert.equal(response.text,'');assert(header(response,'access-control-allow-methods').includes('HEAD'));assert(header(response,'access-control-expose-headers').includes('Retry-After'));
 php.writeFile('/www/data.json','{"entries":[null]}');response=await run('api.php');check(response,502);assert(!response.text.includes('/www'));
 php.writeFile('/www/data.json','broken');check(await run('api.php'),502);
 // A readable directory causes a genuine file_get_contents stream diagnostic;
 // even display_errors=On must leave only the generic API JSON response.
 php.unlink('/www/data.json');php.mkdir('/www/data.json');
 php.writeFile('/www/read-failure.php',"<?php ini_set('display_errors','1');error_reporting(E_ALL);require '/www/api.php';");
 response=await run('read-failure.php');check(response,502);assert(!response.text.includes('/www'));
 php.rmdir('/www/data.json');
 const good={name:'Ada',email:'ada@example.com',message:'Hello LOLDEX'};
 for(const data of [{...good,name:[]},{...good,message:{}},{...good,email:3},{...good,name:'x\r\nBcc: other@example.com'},{...good,name:'x'.repeat(121)},{...good,message:'x'.repeat(8001)},[],{...good,extra:'x'},{...good,botcheck:[]}])check(await run('contact.php','','POST',JSON.stringify(data)),400);
 for(const raw of ['{','null','{"name":"a","name":"b"}','{"name":"a","\\u006eame":"b"}','{"name":"a","email":"a@example.com","message":"hello",}','{"name":"\u0000"}'])check(await run('contact.php','','POST',raw),400);
 for(const raw of ['name=a&%6eame=b','name[]=a','name=a&email=ada%40example.com&message=x&message=y','name=a&email=%ff&message=hi'])check(await run('contact.php','','POST',raw,'application/x-www-form-urlencoded'),400);
 check(await run('contact.php','','POST',JSON.stringify(good),'text/plain'),415);
 check(await run('contact.php','','POST','x'.repeat(16385)),413);
 check(await run('contact.php','','POST',JSON.stringify(good),'application/json',{CONTENT_LENGTH:'-1'}),400);
 response=await run('contact.php','','HEAD');check(response,405);assert.equal(response.text,'');
 // Valid bodies fail closed locally unless private quota storage is configured.
 check(await run('contact.php','','POST',JSON.stringify({...good,botcheck:'bot'})),503);
 php.writeFile('/www/setup.php',"<?php mkdir('/private/quota',0700); chmod('/private/quota',0700);");await php.run({scriptPath:'/www/setup.php',usePrimaryPhp:true}); configured=true;
 check(await run('contact.php','','POST','name=Ada&email=ada%40example.com&message=Hello&botcheck=bot','application/x-www-form-urlencoded'),200);
 for(let i=0;i<2;i++)check(await run('contact.php','','POST',JSON.stringify({...good,botcheck:'bot'})),200);
 response=await run('contact.php','','POST',JSON.stringify({...good,botcheck:'bot'}));check(response,429);assert(Number(header(response,'retry-after'))>0);
 // Library-only invocation verifies exact mail headers without calling mail().
 php.writeFile('/www/parts.php',`<?php define('LOLDEX_CONTACT_LIBRARY',true); require '/www/contact.php'; $data=loldex_contact_payload(${JSON.stringify(JSON.stringify(good))},'application/json'); echo json_encode(loldex_contact_mail_parts($data));`);
 response=await php.run({scriptPath:'/www/parts.php',usePrimaryPhp:true});assert.equal(response.errors,'');const [mailBody,headers]=JSON.parse(response.text);assert(headers.includes('Reply-To: ada@example.com\r\n'));assert(!headers.includes('Reply-To: Ada'));assert(mailBody.includes('Hello LOLDEX'));
 const state=php.readFileAsText('/private/quota/state.json');assert(!state.includes('192.0.2.1'));assert(state.length<262144);assert.equal(php.readFileAsBuffer('/private/quota/key').length,32);
 php.exit();console.log('Contact/legacy real PHP passed: bounded types, UTF8, duplicates, safe mail headers, no-mail honeypot, private quotas, fail-closed storage, GET/HEAD/OPTIONS.');
})().catch(error=>{console.error(error);process.exit(1)});
