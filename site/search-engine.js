/* Phase 8 literal, bounded, explainable search. No query execution or regex. */
(function(root){
'use strict';
const FIELDS=['platform','source','capability','phase','type','privilege','technique','confidence','provenance','freshness'];
const CLAIM={capability:'capabilities',phase:'phases',privilege:'privilege_required',technique:'attack_techniques'};
const norm=v=>String(v??'').replace(/[A-Z]/g,c=>c.toLowerCase());
function compare(a,b){const x=Array.from(a),y=Array.from(b);for(let i=0;i<Math.min(x.length,y.length);i++){const d=x[i].codePointAt(0)-y[i].codePointAt(0);if(d)return d;}return x.length-y.length;}
class QueryError extends Error { constructor(message){super(message);this.name='QueryError';} }
function parse(query){
 if(typeof query!=='string')throw new QueryError('Query must be text');
 for(let p=0;p<query.length;p++){const c=query.charCodeAt(p);if(c>=0xD800&&c<=0xDBFF){const next=query.charCodeAt(++p);if(!(next>=0xDC00&&next<=0xDFFF))throw new QueryError('Invalid Unicode query');}else if(c>=0xDC00&&c<=0xDFFF)throw new QueryError('Invalid Unicode query');}
 if(/[\x00-\x08\x0E-\x1F\x7F]/.test(query))throw new QueryError('Invalid query control character');
 if(new TextEncoder().encode(query).length>4096)throw new QueryError('Query exceeds 4096 UTF-8 bytes');
 const tokens=[];let i=0;
 while(i<query.length){
  if(/[\x09-\x0D\x20]/.test(query[i])){i++;continue;}
  if('()'.includes(query[i])){tokens.push({kind:query[i++]});continue;}
  let value='',quoted=false,colon=-1;
  while(i<query.length&&!/[\x09-\x0D\x20]/.test(query[i])&&!'()'.includes(query[i])){
   if(query[i]==='"'){
    quoted=true;i++;let closed=false;
    while(i<query.length){const c=query[i++];if(c==='"'){closed=true;break;}if(c==='\\'){if(i>=query.length||!['"','\\'].includes(query[i]))throw new QueryError('Only quote and backslash escapes are supported');value+=query[i++];}else value+=c;}
    if(!closed)throw new QueryError('Unclosed quoted phrase');
   }else {if(query[i]===':'&&colon<0)colon=value.length;value+=query[i++];}
  }
  if(!value)throw new QueryError('Empty search value');
  if(!quoted&&['AND','OR','NOT'].includes(value)){tokens.push({kind:value});continue;}
  let field=null;
  if(colon>=0){field=value.slice(0,colon);value=value.slice(colon+1);if(!FIELDS.includes(field))throw new QueryError('Unknown search field: '+field);if(!value)throw new QueryError('Missing field value');}
  tokens.push({kind:'atom',field,value});
  if(tokens.length>128)throw new QueryError('Too many query tokens');
 }
 if(tokens.length>128)throw new QueryError('Too many query tokens');
 let pos=0,depth=0;
 const peek=()=>tokens[pos]?.kind;
 function primary(){if(++depth>16)throw new QueryError('Query nesting exceeds 16');let node;
  if(peek()==='NOT'){pos++;node={op:'not',child:primary()};}
  else if(peek()==='('){pos++;node=or();if(peek()!==')')throw new QueryError('Missing closing parenthesis');pos++;}
  else if(peek()==='atom'){node={op:'atom',...tokens[pos++]};}
  else throw new QueryError('Expected a search term');depth--;return node;}
 function and(){let node=primary();while(peek()==='AND'||['atom','NOT','('].includes(peek())){if(peek()==='AND')pos++;node={op:'and',left:node,right:primary()};}return node;}
 function or(){let node=and();while(peek()==='OR'){pos++;node={op:'or',left:node,right:and()};}return node;}
 if(!tokens.length)return {version:1,clauses:[[]]};
 const ast=or();if(pos!==tokens.length)throw new QueryError('Unexpected query token');
 function dnf(node){
  if(node.op==='atom')return [[{field:node.field,value:node.value}]];
  // NOT owns an independent evidence scope. De Morgan would invalidate correlated claims.
  if(node.op==='not')return [[{op:'not',clauses:dnf(node.child)}]];
  const a=dnf(node.left),b=dnf(node.right),union=node.op==='or';
  if((union?a.length+b.length:a.length*b.length)>64)throw new QueryError('Query expands beyond 64 alternatives');
  return union?a.concat(b):a.flatMap(x=>b.map(y=>x.concat(y)));
 }
 const clauses=dnf(ast);let expanded=0;
 function count(scope){for(const clause of scope)for(const atom of clause){if(++expanded>4096)throw new QueryError('Query expands beyond 4096 atoms');if(atom.op==='not')count(atom.clauses);}}
 count(clauses);return {version:1,clauses};
}
function claims(entry){return Object.entries(entry.claims||{}).flatMap(([field,values])=>(Array.isArray(values)?values:[values]).filter(v=>v&&typeof v==='object').map((claim,index)=>({field,index,claim})));}
function sources(e){return (e.sources||[]).map(s=>s.project).filter(x=>typeof x==='string');}
function textFields(e){const out=[],evidence=claims(e);const add=(path,value,weight)=>{if(typeof value==='string'&&value){const field=path.split('.')[0],claimField=Object.values(CLAIM).includes(field);out.push({path,value,weight,claimField,evidence:claimField?evidence.filter(x=>x.field===field&&norm(x.claim.value)===norm(value)):[]});}};
 for(const [key,weight] of [['id',100],['name',90],['platform',10],['type',10],['privilege_required',15]])add(key,e[key],weight);
 for(const [key,weight] of [['aliases',70],['attack_techniques',60],['technique_names',60],['capabilities',30],['phases',25],['references',5]])(e[key]||[]).forEach((v,i)=>add(key+'.'+i,v,weight));
 (e.commands||[]).forEach((c,i)=>add('commands.'+i+'.template',c.template,40));sources(e).forEach((s,i)=>add('sources.'+i+'.project',s,10));return out;}
function atomMatch(e,a){const value=norm(a.value),field=a.field;
 if(!field){const matches=textFields(e).filter(x=>norm(x.value).includes(value));return {ok:!!matches.length,reasons:matches.flatMap(x=>{const base={field:x.path,value:x.value,query:a.value,claim_field:x.claimField,score:x.weight+(norm(x.value)===value?20:0)};return x.evidence.length?x.evidence.map(c=>({...base,claim:c.claim,claim_path:'claims.'+c.field+'.'+c.index})):[base];})};}
 let values=[];
 if(field==='source')values=sources(e);
 else if(field==='confidence'||field==='provenance'){
  const matches=claims(e).filter(x=>norm(field==='confidence'?x.claim.confidence?.level:x.claim.provenance?.type)===value);
  return {ok:!!matches.length,reasons:matches.map(x=>({field:'claims.'+x.field+'.'+x.index,claim:x.claim,query:a.value,score:10}))};
 }else if(CLAIM[field])values=Array.isArray(e[CLAIM[field]])?e[CLAIM[field]]:[e[CLAIM[field]]];
 else if(field==='freshness')values=[e.freshness?.classification||'NOT_OBSERVED'];
 else values=[e[field]];
 const matches=values.filter(x=>typeof x==='string'&&norm(x)===value);
 return {ok:!!matches.length,reasons:matches.map(x=>({field:field==='source'?'sources':CLAIM[field]||field,value:x,query:a.value,score:20}))};
}
function evaluate(e,parsed,memo=new WeakMap()){if(memo.has(parsed))return memo.get(parsed);let best=null;
 for(const clause of parsed.clauses){let reasons=[],ok=true,eligibleClaim=null;
  for(const atom of clause){if(atom.op==='not'){if(evaluate(e,atom,memo)){ok=false;break;}continue;}const result=atomMatch(e,atom);if(!result.ok){ok=false;break;}reasons.push(...result.reasons);}
  if(!ok)continue;
  const positive=clause.filter(a=>a.op!=='not'),qualifiers=positive.filter(a=>['confidence','provenance'].includes(a.field)),sourceFilters=positive.filter(a=>a.field==='source');
  const sourceClaims=sourceFilters.length&&(positive.some(a=>CLAIM[a.field])||positive.filter(a=>!a.field).some(a=>atomMatch(e,a).reasons.every(r=>r.claim_field)));
  if(qualifiers.length||sourceClaims){const supporting=claims(e).filter(x=>qualifiers.every(a=>norm(a.field==='confidence'?x.claim.confidence?.level:x.claim.provenance?.type)===norm(a.value))&&sourceFilters.every(a=>norm(x.claim.provenance?.source)===norm(a.value)));
   const facets=positive.filter(a=>CLAIM[a.field]);
   const evidence=facets.length?facets.map(a=>supporting.filter(x=>x.field===CLAIM[a.field]&&norm(x.claim.value)===norm(a.value))):[supporting];
   if(evidence.some(group=>!group.length))continue;
   const eligible=reason=>supporting.some(x=>x.claim===reason.claim);eligibleClaim=eligible;
   const free=positive.filter(a=>!a.field).map(a=>atomMatch(e,a).reasons);
   if(free.some(matches=>matches.every(r=>r.claim_field)&&!matches.some(eligible)))continue;
   reasons=reasons.filter(r=>r.claim_field?eligible(r):!r.claim);for(const group of evidence)for(const x of group)reasons.push({field:'claims.'+x.field+'.'+x.index,claim:x.claim,score:10});
  }
  // One strongest reason per positive atom prevents metadata repetition inflating rank.
  const score=positive.reduce((total,a)=>{const r=atomMatch(e,a).reasons.filter(reason=>!eligibleClaim||!reason.claim_field||eligibleClaim(reason));return total+Math.max(0,...r.map(x=>x.score));},0);
  if(!best||score>best.score)best={entry:e,score,reasons};
 }
 memo.set(parsed,best);return best;
}
function search(entries,query,options={}){
 const parsed=parse(query);if(!Array.isArray(entries))throw new TypeError('Entries must be an array');
 const offset=options.offset??0,limit=options.limit??50;if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>500)throw new QueryError('Invalid pagination');
 const memos=new WeakMap();const run=(entry,scope)=>{if(!memos.has(entry))memos.set(entry,new WeakMap());return evaluate(entry,scope,memos.get(entry));};
 const results=entries.map(e=>run(e,parsed)).filter(Boolean).sort((a,b)=>b.score-a.score||compare(a.entry.id,b.entry.id));
 const facets={};for(const field of FIELDS){const counts=new Map();for(const result of results){const e=result.entry;let values=field==='source'?sources(e):field==='confidence'?claims(e).map(x=>x.claim.confidence?.level):field==='provenance'?claims(e).map(x=>x.claim.provenance?.type):field==='freshness'?[e.freshness?.classification||'NOT_OBSERVED']:CLAIM[field]?(Array.isArray(e[CLAIM[field]])?e[CLAIM[field]]:[e[CLAIM[field]]]):[e[field]];for(const value of new Set(values.filter(x=>typeof x==='string'))){const constrained={clauses:parsed.clauses.map(clause=>clause.concat({field,value}))};if(run(e,constrained))counts.set(value,(counts.get(value)||0)+1);}}facets[field]=[...counts].sort((a,b)=>compare(a[0],b[0])).map(([value,count])=>({value,count}));}
 return {version:1,total:results.length,offset,limit,results:results.slice(offset,offset+limit),facets};
}
const api={parse,evaluate,search,QueryError,FIELDS};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.LoldexSearch=api;
})(typeof window!=='undefined'?window:globalThis);
