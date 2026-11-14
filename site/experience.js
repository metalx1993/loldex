/* Static experience: upstream text enters textContent, never HTML templates. */
'use strict';
const LX=Loldex, $=s=>document.querySelector(s);
const entryURL=id=>'./entry.html?id='+encodeURIComponent(id);
const techURL=id=>'./technique.html?id='+encodeURIComponent(id);
const techniquePill=id=>pill(id,/^T\d{4}(?:\.\d{3})?$/.test(id)?techURL(id):null);
const searchURL=filters=>'./search.html?'+new URLSearchParams(filters);
function el(tag,attrs={},...children){
  const n=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs)) {if(k==='class')n.className=v;else n.setAttribute(k,String(v));}
  for(const c of children.flat(Infinity)) if(c!==null&&c!==undefined)n.append(c instanceof Node?c:document.createTextNode(String(c)));
  return n;
}
function replace(node,...children){node.replaceChildren(...children);}
async function data(file){
  const response=await fetch('./'+file,{cache:'no-cache'});
  if(!response.ok)throw new Error('Dataset unavailable');
  return response.json();
}
function fail(target,message='The index could not be loaded. Please try again.'){
  const retry=el('button',{type:'button'},'Try again');retry.addEventListener('click',()=>location.reload());
  replace(target,el('div',{class:'notice error',role:'alert'},el('p',{},message),retry));
}
function pill(text,href){return el(href?'a':'span',href?{class:'pill',href}:{class:'pill'},text);}
function freshness(e){return ({ACTIVE:'Present in last reliable observation',STALE_CANDIDATE:'Stale candidate',NOT_OBSERVED:'Not observed'})[e.freshness?.classification]||'Not observed';}
function row(e){
  const out=el('article',{class:'entry-row'},el('div',{class:'rowhead'},el('h2',{},el('a',{href:entryURL(e.id)},e.name||e.id)),pill(e.platform||'Unspecified')),
    el('div',{class:'entry-id'},e.id));
  out.append(el('div',{class:'pills'},LX.sources(e).map(s=>pill(s,searchURL({source:s}))), (e.attack_techniques||[]).map(techniquePill)));
  out.append(el('div',{class:'rowmeta'},(e.capabilities||[]).join(' · ')||'No capability claim', ' / ',e.privilege_required||'Privilege not claimed'));
  if(e.commands?.length)out.append(el('pre',{class:'command'},e.commands[0].template));
  out.append(el('div',{class:'status'},freshness(e),' · ',LX.claims(e).length,' attributed claims'));
  return out;
}
function techniqueCard(t){return el('article',{class:'tech-card'},el('a',{href:techURL(t.id)},t.id),t.name?el('h3',{},t.name):null,el('div',{class:'pills'},t.revoked?pill('Revoked'):null,t.deprecated?pill('Deprecated'):null),el('p',{class:'muted'},t.entry_ids.length+' entries · '+t.platforms.join(', ')),el('small',{},t.sources.join(' · ')));}
async function home(){
  try{
    const [catalog,techniques]=await Promise.all([data('catalog.json'),data('techniques.json')]);
    const sourceCount=new Set(catalog.entries.flatMap(LX.sources)).size;
    const values=[[catalog.count.toLocaleString('en'),'Indexed entries'],[sourceCount,'Source projects'],[techniques.count,'Technique identifiers'],[new Set(catalog.entries.map(e=>e.platform)).size,'Platforms']];
    replace($('#stats'),...values.map(([v,label])=>el('div',{class:'stat'},el('strong',{},v),el('span',{},label))));
    replace($('#featured'),...techniques.techniques.slice().sort((a,b)=>b.entry_ids.length-a.entry_ids.length||a.id.localeCompare(b.id)).slice(0,3).map(techniqueCard));
  }catch{fail($('#stats'));}
}
const facetConfig=[['platform','Platform','platform'],['source','Source project','source'],['type','Entry type','type'],['priv','Required privilege','privilege_required'],['cap','Capability','capabilities'],['phase','Phase','phases'],['technique','ATT&CK identifier','attack_techniques'],['confidence','Claim confidence','confidence'],['provenance','Claim origin','provenance'],['freshness','CORE classification','freshness']];
async function search(){
  const q=$('#q'), params=new URLSearchParams(location.search);q.value=params.get('q')||'';
  try{
    const [catalog,techniques]=await Promise.all([data('catalog.json'),data('techniques.json').catch(()=>({techniques:[]}))]), entries=catalog.entries;
    const names=new Map(techniques.techniques.map(t=>[t.id,t.name]));
    for(const entry of entries)entry.technique_names=(entry.attack_techniques||[]).map(id=>names.get(id)).filter(Boolean);
    const fieldNames={cap:'capability',priv:'privilege'};
    const selects=new Map();
    for(const [key,label,field] of facetConfig){
      let values;
      if(key==='source')values=entries.flatMap(LX.sources);
      else if(key==='confidence')values=entries.flatMap(e=>LX.claims(e).map(c=>c.confidence?.level).filter(Boolean));
      else if(key==='provenance')values=entries.flatMap(e=>LX.claims(e).map(c=>c.provenance?.type).filter(Boolean));
      else if(key==='freshness')values=entries.map(e=>e.freshness?.classification||'NOT_OBSERVED');
      else values=entries.flatMap(e=>Array.isArray(e[field])?e[field]:e[field]?[e[field]]:[]);
      const select=el('select',{id:'f-'+key,name:key},el('option',{value:''},'All'));
      for(const v of [...new Set(values)].sort())select.append(el('option',{value:v},v));
      if(params.get(key)&&![...select.options].some(o=>o.value===params.get(key)))select.append(el('option',{value:params.get(key)},params.get(key)));
      select.value=params.get(key)||'';selects.set(key,select);
      $('#filters').append(el('div',{},el('label',{for:select.id},label),select));
    }
    let shown=0,combined='';
    const error=el('p',{class:'notice error',role:'alert',hidden:''});$('#search-form').after(error);
    function render(reset=true){
      if(reset){
        shown=0;
        const filters={q:q.value};for(const[k,s]of selects)filters[k]=s.value;
        const url=new URLSearchParams(Object.entries(filters).filter(([,v])=>v));
        history.replaceState(null,'',location.pathname+(url.size?'?'+url:''));
        const terms=q.value.trim()?['('+q.value+')']:[];
        for(const[k,s]of selects)if(s.value)terms.push((fieldNames[k]||k)+':'+JSON.stringify(s.value));
        combined=terms.join(' AND ');
      }
      try{
        const page=LoldexSearch.search(entries,combined,{offset:shown,limit:30});
        error.hidden=true;error.textContent='';
        const rows=page.results.map(hit=>{
          const article=row(hit.entry),why=el('details',{class:'match-explanation'},el('summary',{},'Why this result · relevance '+hit.score));
          why.append(el('p',{class:'muted'},'Relevance reflects matching fields, not confidence, risk or freshness.'));
          const seen=new Set();
          for(const reason of hit.reasons){
            const key=JSON.stringify(reason);if(seen.has(key))continue;seen.add(key);
            const claim=reason.claim, value=claim?.value??reason.value??'';
            why.append(el('p',{},el('code',{},reason.field),': ',String(value),claim?' · '+claim.provenance?.type+' / '+claim.confidence?.level+' / '+(claim.provenance?.source||'No source declared'):''));
          }
          article.append(why);return article;
        });
        if(reset)replace($('#results'),...rows);else $('#results').append(...rows);
        shown+=rows.length;
        $('#result-count').textContent=page.total.toLocaleString('en')+' results · showing '+shown;
        if(!page.total)replace($('#results'),el('div',{class:'empty'},el('h2',{},'No matching entries'),el('p',{},'Try fewer filters or a different query.')));
        $('#more').hidden=shown>=page.total;
        for(const[k,s]of selects){const counts=new Map((page.facets[fieldNames[k]||k]||[]).map(v=>[v.value,v.count]));for(const option of s.options)if(option.value)option.textContent=option.value+' ('+(counts.get(option.value)||0)+')';}
      }catch(e){
        if(!(e instanceof LoldexSearch.QueryError))throw e;
        error.hidden=false;error.textContent='Invalid query: '+e.message;
        replace($('#results'));$('#more').hidden=true;$('#result-count').textContent='Query needs correction';
      }
    }
    $('#search-form').addEventListener('submit',event=>{event.preventDefault();render();});
    q.addEventListener('input',()=>render());
    for(const s of selects.values())s.addEventListener('change',()=>render());
    $('#reset').addEventListener('click',()=>{q.value='';for(const s of selects.values())s.value='';render();q.focus();});
    $('#more').addEventListener('click',()=>render(false));render();
  }catch{fail($('#results'));$('#result-count').textContent='Index unavailable';}
}
async function techniques(){
  try{
    const all=(await data('techniques.json')).techniques;
    function render(){const q=$('#tech-q').value.trim().toLowerCase(), hits=all.filter(t=>(t.id+' '+(t.name||'')).toLowerCase().includes(q));
      $('#result-count').textContent=hits.length+' technique identifiers';
      replace($('#tech-results'),...(hits.length?hits.map(techniqueCard):[el('p',{class:'empty'},'No matching technique IDs.')]));}
    $('#tech-q').addEventListener('input',render);render();
  }catch{fail($('#tech-results'));$('#result-count').textContent='Techniques unavailable';}
}
function title(target,kicker,name,id){
  target.removeAttribute('aria-busy');document.title=name+' — LOLDEX';$('#crumb-label').textContent=id;
  replace(target,el('p',{class:'eyebrow'},kicker),el('h1',{class:'detail-title'},name),el('p',{class:'entry-id'},id));
}
function claimTable(claims){
  return el('div',{class:'table-scroll'},el('table',{class:'claims'},el('caption',{class:'muted'},'Confidence belongs to each claim.'),el('thead',{},el('tr',{},['Field / value','Provenance','Confidence'].map(v=>el('th',{scope:'col'},v)))),
    el('tbody',{},claims.map(c=>el('tr',{},el('td',{},el('strong',{},c.field),el('br'),String(c.value)),el('td',{},c.provenance?.type||'Not declared',el('br'),el('small',{},[c.provenance?.source,c.provenance?.adapter,c.provenance?.note].filter(Boolean).join(' · '))),el('td',{},c.confidence?.level||'Not declared'))))));
}
function svgEl(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;return n;}
function relationshipView(graph,nodeId){
  const edges=graph.edges.filter(e=>e.from===nodeId||e.to===nodeId), nodes=new Map(graph.nodes.map(n=>[n.id,n]));
  const allTargets=[...new Set(edges.map(e=>e.from===nodeId?e.to:e.from))];
  const section=el('section',{},el('h2',{},'Relationship evidence'),el('p',{class:'muted'},'Connections preserve the source claim. They do not imply equivalence between entries.'));
  if(!edges.length){section.append(el('p',{class:'empty'},'No documented relationships for this item.'));return section;}
  const subset=allTargets.slice(0,8),svg=svgEl('svg',{viewBox:'0 0 700 340',role:'img','aria-label':'Local relationship overview. The full accessible relationship list follows.'});
  subset.forEach((id,i)=>{const angle=2*Math.PI*i/subset.length,x=350+240*Math.cos(angle),y=170+115*Math.sin(angle);
    svg.append(svgEl('line',{x1:350,y1:170,x2:x,y2:y,stroke:'#75878d'}));
    svg.append(svgEl('circle',{cx:x,cy:y,r:6,fill:'#9ce5d4'}));
    const label=nodes.get(id)?.label||id;
    svg.append(svgEl('text',{x:x,y:y+22,'text-anchor':'middle'},label.length>25?label.slice(0,22)+'…':label));});
  svg.append(svgEl('circle',{cx:350,cy:170,r:10,fill:'#9ce5d4'}));svg.append(svgEl('text',{x:350,y:202,'text-anchor':'middle'},'This item'));
  section.append(el('div',{class:'graph'},svg));
  if(allTargets.length>8)section.append(el('p',{class:'muted'},'Overview shows 8 of '+allTargets.length+' connected nodes. All relationships are listed below.'));
  const disclosure=el('details',{},el('summary',{},'Explore all '+edges.length+' relationship claims'));
  for(const edge of edges){const other=nodes.get(edge.from===nodeId?edge.to:edge.from),href=other?.kind==='entry'?entryURL(other.entry_id):other?.kind==='technique'?techURL(other.technique_id):null;
    disclosure.append(el('div',{class:'relationship'},el('span',{class:'relation-type'},edge.type.replaceAll('_',' ')),el('div',{},href?el('a',{href},other.label):el('span',{},other?.label||'Unknown node'),el('small',{},[edge.provenance.type,edge.confidence.level,edge.provenance.source,edge.provenance.note].filter(Boolean).join(' · ')))));}
  section.append(disclosure);return section;
}
async function entry(){
  const target=$('#detail'),id=new URLSearchParams(location.search).get('id');
  try{
    const catalog=await data('catalog.json'),e=catalog.entries.find(e=>e.id===id);
    if(!e){title(target,'Entry not found','This entry is not in the index.',id||'No ID supplied');try{const identities=await data('identities.json'),alias=identities.aliases.find(a=>a.old_entry_id===id);if(alias){target.append(el('p',{class:'notice'},'An explicit source-ID mapping exists. No target is selected automatically; these are source records, not a claim of technique equivalence.'));for(const next of alias.new_entry_ids)target.append(el('p',{},el('a',{href:entryURL(next)},next)));target.append(el('pre',{},JSON.stringify(alias,null,2)));}}catch{}target.append(el('a',{href:'./search.html'},'Return to search'));return;}
    title(target,e.platform,e.name||e.id,e.id);
    target.append(el('div',{class:'pills'},LX.sources(e).map(s=>pill(s,searchURL({source:s}))), (e.attack_techniques||[]).map(techniquePill)));
    target.append(el('div',{class:'notice'},freshness(e),'. CORE classification describes observations, not elapsed-time freshness.'));
    const commands=el('section',{},el('h2',{},'Documented commands'));
    if(!e.commands?.length)commands.append(el('p',{class:'muted'},'No command recorded.'));
    for(const c of e.commands||[]){const copy=el('button',{type:'button'},'Copy command'), status=el('span',{role:'status',class:'muted'});
      copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(c.template);status.textContent='Copied';}catch{status.textContent='Select the command text to copy it.';}});
      commands.append(el('pre',{class:'command'},c.template),el('div',{class:'actionline'},copy,status));if(c.comment)commands.append(el('p',{class:'muted'},c.comment));}
    target.append(commands,el('section',{},el('h2',{},'Claims and provenance'),claimTable(LX.claims(e))));
    if(e.opsec)target.append(el('section',{},el('h2',{},'Operational notes'),el('pre',{},JSON.stringify(e.opsec,null,2))));
    const source=el('section',{},el('h2',{},'Source evidence'));
    for(const ref of e.references||[]){const url=LX.safeURL(ref);if(url)source.append(el('p',{},el('a',{href:url,target:'_blank',rel:'noopener noreferrer'},ref)));}
    const disclosure=el('details',{},el('summary',{},'Inspect original source data'));
    let loaded=false;
    disclosure.addEventListener('toggle',async()=>{if(!disclosure.open||loaded)return;loaded=true;const box=el('div',{},'Loading source evidence…');disclosure.append(box);
      try{const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(id));const ref='evidence-records/'+Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('')+'.json';if(e.evidence_ref!==ref)throw new Error('Evidence reference mismatch');const response=await fetch('./'+ref,{cache:'no-cache'});if(!response.ok)throw new Error('Source evidence unavailable');const raw=await response.text();JSON.parse(raw);replace(box,el('pre',{},raw));}catch{loaded=false;fail(box,'Source evidence could not be loaded. Close and reopen this section to retry.');}});
    source.append(disclosure);target.append(source);
    try{target.append(await entryIdentities(e));}catch{target.append(el('p',{class:'notice error'},'Tool identity evidence is unavailable; no membership is inferred.'));}
    try{const graph=await data('graph.json');target.append(relationshipView(graph,'entry:'+id));
      const diagnostics=(graph.diagnostics||[]).filter(d=>d.entry_id===id);
      if(diagnostics.length)target.append(el('section',{},el('h2',{},'Data quality notes'),el('p',{class:'muted'},'A source claim could not form a valid relationship. The original claim is preserved above.'),el('pre',{},JSON.stringify(diagnostics,null,2))));
    }catch{target.append(el('p',{class:'notice'},'Relationships are unavailable. The entry evidence above remains accessible.'));}
  }catch{target.removeAttribute('aria-busy');fail(target);}
}
async function technique(){
  const target=$('#detail'),id=new URLSearchParams(location.search).get('id');
  try{
    const [techniques,catalog,graph]=await Promise.all([data('techniques.json'),data('catalog.json'),data('graph.json')]),t=techniques.techniques.find(t=>t.id===id);
    if(!t){title(target,'Technique not found','This technique is not in the index.',id||'No ID supplied');target.append(el('a',{href:'./techniques.html'},'Return to techniques'));return;}
    title(target,'ATT&CK technique / '+t.id,t.name||t.id,'Technique / '+t.id);
    if(t.registry_status==='verified'){
      const url=LX.safeURL(t.url);
      target.append(el('div',{class:'notice'},'Metadata matches the pinned Enterprise ATT&CK '+techniques.registry.version+' snapshot. This identifies the technique; it does not verify the entry claims.',url?el('p',{},el('a',{href:url,target:'_blank',rel:'noopener noreferrer'},'Read the official MITRE technique →')):null));
      if(t.revoked)target.append(el('p',{class:'notice error'},'This identifier is revoked in the registry.'));
      if(t.deprecated)target.append(el('p',{class:'notice error'},'This identifier is deprecated in the registry.'));
      if(t.description){
        const first=t.description.split(/\n\s*\n/)[0],excerpt=first.length>420?first.slice(0,420)+'…':first;
        const description=el('section',{},el('h2',{},'Registry description'),el('p',{class:'registry-description'},excerpt));
        if(t.description!==excerpt)description.append(el('details',{},el('summary',{},'Read the full official description'),el('p',{class:'registry-description'},t.description)));
        target.append(description);
      }
      if(t.tactics?.length)target.append(el('section',{},el('h2',{},'Registry tactics'),el('div',{class:'pills'},t.tactics.map(p=>pill(p)))));
    }else target.append(el('p',{class:'notice'},'Identifier from source-attributed claims. It does not match the pinned registry; no name or description is inferred.'));
    target.append(el('section',{},el('h2',{},'Context of the associated entries'),el('div',{class:'pills'},t.platforms.map(p=>pill(p)),t.sources.map(s=>pill(s))),el('p',{class:'muted'},'Capabilities recorded on these entries: '+(t.capabilities.join(', ')||'none')+'. These are entry attributes, not registry properties of the technique.')));
    target.append(el('section',{},el('h2',{},'Evidence by claim'),el('p',{class:'muted'},Object.entries(t.confidence_counts).map(([k,v])=>v+' '+k+' confidence').join(' · ')),el('p',{class:'muted'},'These counts describe claims, not independent confirmation or a score for the technique.')));
    const ids=new Set(t.entry_ids), supporting=catalog.entries.filter(e=>ids.has(e.id));
    const list=el('div'),more=el('button',{type:'button',class:'more'},'Show more entries'),count=el('p',{class:'muted',role:'status'});let limit=30;
    function renderEntries(){replace(list,...supporting.slice(0,limit).map(row));count.textContent='Showing '+Math.min(limit,supporting.length)+' of '+supporting.length+' entries';more.hidden=limit>=supporting.length;}
    more.addEventListener('click',()=>{limit+=30;renderEntries();});renderEntries();
    target.append(el('section',{},el('h2',{},'Entries documenting '+t.id),count,list,more),relationshipView(graph,'technique:'+t.id));
  }catch{target.removeAttribute('aria-busy');fail(target);}
}
const identityURL=id=>'./identity.html?id='+encodeURIComponent(id);
function membershipBlock(member,catalog){
  const entry=catalog.entries.find(e=>e.id===member.entry_id),box=el('article',{class:'identity-member'});
  box.append(el('h3',{},entry?el('a',{href:entryURL(entry.id)},entry.name||entry.id):member.entry_id),el('p',{class:'entry-id'},member.entry_id));
  box.append(el('p',{},member.relation.replaceAll('_',' '),' · ',member.status==='active'?'Witness matches this dataset':member.status));
  box.append(claimTable([{field:member.relation,value:member.entry_id,provenance:member.provenance,confidence:member.confidence}]));
  box.append(el('p',{class:'muted'},'Curator: '+(member.provenance?.curator||'Not declared')+'. This association does not equate techniques or prove runtime binary resolution.'));
  const evidence=el('details',{},el('summary',{},'Inspect identity witnesses'));
  evidence.append(el('pre',{},JSON.stringify({review_revision:member.review_revision,current_revision:member.current_revision,evidence:member.evidence},null,2)));box.append(evidence);return box;
}
async function identities(){
  try{
    const registry=await data('identities.json');
    if(registry.version!==1||!Array.isArray(registry.entities))throw new Error('Invalid identity registry');
    const q=$('#identity-q');
    function render(){const needle=q.value.toLowerCase(),hits=registry.entities.filter(e=>(e.id+' '+e.label).toLowerCase().includes(needle));
      $('#result-count').textContent=hits.length+' declared tool identities · '+registry.stats.active_memberships+' current witness associations';
      replace($('#identity-results'),...hits.map(e=>el('article',{class:'tech-card'},el('a',{href:identityURL(e.id)},e.label),el('p',{class:'entry-id'},e.id),el('p',{},e.members.filter(m=>m.status==='active').length+' current associations'),el('small',{},'Tool identity only; techniques stay distinct.'))));
      if(!hits.length)replace($('#identity-results'),el('p',{class:'empty'},'No declared identity matches. Search entries for the broader source catalogue.'));
    }
    q.addEventListener('input',render);render();
  }catch{fail($('#identity-results'));$('#result-count').textContent='Identity registry unavailable';}
}
async function identity(){
  const target=$('#detail'),id=new URLSearchParams(location.search).get('id');
  try{
    const [registry,catalog]=await Promise.all([data('identities.json'),data('catalog.json')]);
    const entity=registry.entities.find(e=>e.id===id);
    if(!entity){title(target,'Identity not found','No declared tool identity matches.',id||'No ID supplied');return;}
    title(target,'Declared tool identity',entity.label,entity.id);
    target.append(el('p',{class:'notice'},'Memberships preserve their own provenance and confidence. They never make the techniques equivalent, and no confidence is assigned to this entire identity.'));
    target.append(el('p',{},'Documented runtime scope: '+entity.platform_scope.runtime.join(', ')+'. Entry contexts: '+entity.platform_scope.contexts.join(', ')+'.'));
    if(entity.scope_note)target.append(el('p',{class:'muted'},entity.scope_note));
    const active=entity.members.filter(m=>m.status==='active'),inactive=entity.members.filter(m=>m.status!=='active');
    target.append(el('section',{},el('h2',{},'Current source witnesses'),...active.map(m=>membershipBlock(m,catalog))));
    if(!active.length)target.append(el('p',{class:'empty'},'No reviewed witness currently matches this dataset. The stable identity record is retained.'));
    if(inactive.length)target.append(el('section',{},el('h2',{},'Retained historical associations'),el('p',{class:'muted'},'These records remain visible for audit and are excluded from active membership.'),...inactive.map(m=>membershipBlock(m,catalog))));
    const candidates=registry.candidates.filter(c=>c.entity_id===id);
    if(candidates.length){const section=el('section',{},el('h2',{},'Unconfirmed candidates'),el('p',{class:'muted'},'These low-confidence suggestions are not identity memberships. A matching executable token is insufficient to prove equivalence.'));
      for(const c of candidates){const e=catalog.entries.find(v=>v.id===c.entry_id);section.append(el('p',{},el('a',{href:entryURL(c.entry_id)},e?.name||c.entry_id),' · '+c.status+' / '+c.confidence.level));}target.append(section);}
  }catch{target.removeAttribute('aria-busy');fail(target,'The identity evidence could not be loaded.');}
}
async function api(){
  const form=$('#api-form'),status=$('#api-status'),box=$('#api-response');
  form.addEventListener('submit',async event=>{
    event.preventDefault();status.textContent='Reading this release’s API…';box.textContent='';
    try{const response=await fetch('./api-v1.php?resource=search&limit=5&q='+encodeURIComponent($('#api-q').value));const envelope=await response.json();
      box.textContent=JSON.stringify(envelope,null,2);status.textContent=response.ok?'API v'+envelope.api_version+' · '+envelope.pagination.total+' results · five shown':(envelope.error?.message||'API request rejected');
    }catch{status.textContent='API unavailable. This read-only explorer requires the PHP hosting environment.';}
  });
}
async function entryIdentities(e){
  const registry=await data('identities.json'),refs=registry.entry_index[e.id]||[];
  const section=el('section',{},el('h2',{},'Tool identity evidence'),el('p',{class:'muted'},'Tool associations do not equate this technique with other entries. Candidate suggestions are kept separate.'));
  for(const ref of refs){const entity=registry.entities.find(v=>v.id===ref.entity_id),member=entity?.members.find(m=>m.id===ref.claim_id&&m.status==='active');
    if(!member)throw new Error('Inconsistent identity reference');section.append(el('h3',{},el('a',{href:identityURL(entity.id)},entity.label)),claimTable([{field:member.relation,value:e.id,provenance:member.provenance,confidence:member.confidence}]));}
  if(!refs.length)section.append(el('p',{},'No active declared tool membership for this entry.'));
  const candidates=registry.candidates.filter(c=>c.entry_id===e.id);
  for(const c of candidates)section.append(el('p',{class:'muted'},'Unconfirmed candidate: ',el('a',{href:identityURL(c.entity_id)},c.entity_id),' · heuristic / low; not an identity membership.'));
  return section;
}
({home,search,techniques,entry,technique,identities,identity,api}[document.body.dataset.view]||(()=>{}))();
