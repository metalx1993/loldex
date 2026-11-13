/* Pure search helpers shared by browser and executable regression tests. */
(function(root){
  'use strict';
  const claims = e => Object.entries(e.claims||{}).flatMap(([field, values]) =>
    (Array.isArray(values)?values:[values]).filter(v=>v&&typeof v==='object').map(v=>({field,...v})));
  const sources = e => [...new Set((e.sources||[]).map(s=>s.project).filter(Boolean))].sort();
  const normalized = v => String(v??'').normalize('NFC').toLocaleLowerCase('en');
  function matches(e, f={}) {
    const hay=normalized([e.id,e.name,e.platform,e.privilege_required,...(e.aliases||[]),...(e.attack_techniques||[]),...(e.technique_names||[]),...(e.capabilities||[]),...(e.phases||[]),...sources(e),...(e.commands||[]).map(c=>c.template)].join(' '));
    if(normalized(f.q).trim().split(/\s+/).filter(Boolean).some(t=>!hay.includes(t))) return false;
    if(f.platform&&e.platform!==f.platform) return false;
    if(f.source&&!sources(e).includes(f.source)) return false;
    if(f.priv&&e.privilege_required!==f.priv) return false;
    for(const [key,field] of [['cap','capabilities'],['phase','phases'],['technique','attack_techniques']]) if(f[key]&&!(e[field]||[]).includes(f[key])) return false;
    if(f.confidence||f.provenance){
      const evidence=claims(e).filter(c=>(!f.confidence||c.confidence?.level===f.confidence)&&(!f.provenance||c.provenance?.type===f.provenance)&&(!f.source||c.provenance?.source===f.source));
      const selected=[['cap','capabilities'],['phase','phases'],['technique','attack_techniques'],['priv','privilege_required']].filter(([key])=>f[key]);
      if(selected.length){if(selected.some(([key,field])=>!evidence.some(c=>c.field===field&&c.value===f[key])))return false;}
      else if(!evidence.length)return false;
    }
    if(f.freshness&&(e.freshness?.classification||'NOT_OBSERVED')!==f.freshness) return false;
    return true;
  }
  function safeURL(value){
    if(typeof value!=='string'||!/^https?:\/\//i.test(value)) return null;
    try {const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch{return null;}
  }
  const api={claims,sources,matches,safeURL};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
  else root.Loldex=api;
})(typeof window!=='undefined'?window:globalThis);
