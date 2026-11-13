'use strict';
const assert=require('node:assert/strict');
const {matches,sources,claims,safeURL}=require('../site/experience-core.js');
const entry={id:'lolbas/certutil/download/0',name:'Certutil',platform:'windows',sources:[{project:'LOLBAS'}],commands:[{template:'certutil -urlcache http://example.org'}],attack_techniques:['T1105'],capabilities:['file-download'],phases:['command-and-control'],privilege_required:'user',claims:{capabilities:[{value:'file-download',confidence:{level:'low'},provenance:{type:'heuristic'}}],attack_techniques:[{value:'T1105',confidence:{level:'high'},provenance:{type:'upstream'}}]},freshness:{classification:'NOT_OBSERVED'}};
for(const q of ['certutil','T1105','-urlcache','file-download','LOLBAS','certutil T1105'])assert(matches(entry,{q}));
assert(!matches(entry,{q:'T1105 unrelated'}));
assert(matches(entry,{platform:'windows',source:'LOLBAS'}));
assert(matches(entry,{confidence:'high'})); // independent claims retain both levels
assert(!matches(entry,{confidence:'verified'}));
assert(!matches(entry,{cap:'file-download',confidence:'high'}));
assert(matches(entry,{cap:'file-download',confidence:'low'}));
assert(matches(entry,{technique:'T1105',confidence:'high',provenance:'upstream'}));
assert(!matches(entry,{technique:'T1105',confidence:'low'}));
assert(!matches(entry,{source:'LOLBAS',confidence:'high'})); // no source on the fixture claim: never infer
assert(!matches(entry,{platform:'linux'}));
assert(!matches(entry,{technique:'T1003'}));
assert(!matches(entry,{freshness:'ACTIVE'}));
assert(matches(entry,{freshness:'NOT_OBSERVED'}));
assert.deepEqual(sources(entry),['LOLBAS']);assert.equal(claims(entry).length,2);
for(const url of ['javascript:alert(1)','data:text/html,x','//evil.test','file:///etc/passwd','https:evil.test','\nhttps://evil.test'])assert.equal(safeURL(url),null);
assert.equal(safeURL('https://example.org'), 'https://example.org/');
assert.equal(safeURL(null),null);
console.log('Experience search and URL regression checks passed');
