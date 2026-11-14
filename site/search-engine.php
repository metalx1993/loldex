<?php
/** Phase 8 shared search contract, mirrored from search-engine.js. No query execution. */
class LoldexQueryError extends Exception {}
const LOLDEX_SEARCH_FIELDS = array('platform','source','capability','phase','type','privilege','technique','confidence','provenance','freshness');
const LOLDEX_SEARCH_CLAIM = array('capability'=>'capabilities','phase'=>'phases','privilege'=>'privilege_required','technique'=>'attack_techniques');
function loldex_get($object, $key, $default=null) {
    if (is_object($object) && property_exists($object, $key)) return $object->$key;
    if (is_array($object) && array_key_exists($key, $object)) return $object[$key];
    return $default;
}
function loldex_norm($value) { return strtr(is_string($value) ? $value : '', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'); }
function loldex_ws($char) { return $char !== '' && strpos("\x09\x0a\x0b\x0c\x0d ", $char) !== false; }
class LoldexSearchParser {
    private $tokens = array(); private $pos = 0; private $depth = 0;
    function __construct($query) {
        if (!is_string($query) || !preg_match('//u', $query)) throw new LoldexQueryError('Query must be valid UTF-8 text');
        if (strlen($query)>4096) throw new LoldexQueryError('Query exceeds 4096 UTF-8 bytes');
        if (preg_match('/[\x00-\x08\x0e-\x1f\x7f]/', $query)) throw new LoldexQueryError('Invalid query control character');
        $i=0; $length=strlen($query);
        while ($i<$length) {
            if (loldex_ws($query[$i])) { $i++; continue; }
            if ($query[$i]==='(' || $query[$i]===')') { $this->tokens[]=array('kind'=>$query[$i++]); continue; }
            $value=''; $quoted=false; $colon=-1;
            while ($i<$length && !loldex_ws($query[$i]) && $query[$i]!=='(' && $query[$i]!==')') {
                if ($query[$i]==='"') {
                    $quoted=true; $i++; $closed=false;
                    while ($i<$length) {
                        $char=$query[$i++];
                        if ($char==='"') { $closed=true; break; }
                        if ($char==='\\') {
                            if ($i>=$length || ($query[$i]!=='"' && $query[$i]!=='\\')) throw new LoldexQueryError('Only quote and backslash escapes are supported');
                            $value.=$query[$i++];
                        } else $value.=$char;
                    }
                    if (!$closed) throw new LoldexQueryError('Unclosed quoted phrase');
                } else {
                    if ($query[$i]===':' && $colon<0) $colon=strlen($value);
                    $value.=$query[$i++];
                }
            }
            if ($value==='') throw new LoldexQueryError('Empty search value');
            if (!$quoted && in_array($value, array('AND','OR','NOT'), true)) $this->tokens[]=array('kind'=>$value);
            else {
                $field=null;
                if ($colon>=0) {
                    $field=substr($value,0,$colon); $value=substr($value,$colon+1);
                    if (!in_array($field, LOLDEX_SEARCH_FIELDS, true)) throw new LoldexQueryError('Unknown search field');
                    if ($value==='') throw new LoldexQueryError('Missing field value');
                }
                $this->tokens[]=array('kind'=>'atom','field'=>$field,'value'=>$value);
            }
            if (count($this->tokens)>128) throw new LoldexQueryError('Too many query tokens');
        }
        if (count($this->tokens)>128) throw new LoldexQueryError('Too many query tokens');
    }
    private function peek() { return isset($this->tokens[$this->pos]) ? $this->tokens[$this->pos]['kind'] : null; }
    private function primary() {
        if (++$this->depth>16) throw new LoldexQueryError('Query nesting exceeds 16');
        $kind=$this->peek();
        if ($kind==='NOT') { $this->pos++; $node=array('op'=>'not','child'=>$this->primary()); }
        elseif ($kind==='(') { $this->pos++; $node=$this->orNode(); if ($this->peek()!==')') throw new LoldexQueryError('Missing closing parenthesis'); $this->pos++; }
        elseif ($kind==='atom') { $node=$this->tokens[$this->pos++]; $node['op']='atom'; }
        else throw new LoldexQueryError('Expected a search term');
        $this->depth--; return $node;
    }
    private function andNode() {
        $node=$this->primary();
        while ($this->peek()==='AND' || in_array($this->peek(), array('atom','NOT','('), true)) {
            if ($this->peek()==='AND') $this->pos++;
            $node=array('op'=>'and','left'=>$node,'right'=>$this->primary());
        }
        return $node;
    }
    private function orNode() {
        $node=$this->andNode();
        while ($this->peek()==='OR') { $this->pos++; $node=array('op'=>'or','left'=>$node,'right'=>$this->andNode()); }
        return $node;
    }
    private function dnf($node) {
        if ($node['op']==='atom') return array(array(array('field'=>$node['field'],'value'=>$node['value'])));
        // NOT is an opaque evidence scope; never apply De Morgan to correlated claims.
        if ($node['op']==='not') return array(array(array('op'=>'not','clauses'=>$this->dnf($node['child']))));
        $a=$this->dnf($node['left']); $b=$this->dnf($node['right']); $union=$node['op']==='or';
        if (($union ? count($a)+count($b) : count($a)*count($b))>64) throw new LoldexQueryError('Query expands beyond 64 alternatives');
        if ($union) return array_merge($a,$b);
        $out=array(); foreach ($a as $left) foreach ($b as $right) $out[]=array_merge($left,$right); return $out;
    }
    private function expandedCost($clauses,&$remaining) {
        foreach ($clauses as $clause) foreach ($clause as $atom) {
            if (--$remaining<0) throw new LoldexQueryError('Query expands beyond 4096 atoms');
            if (($atom['op']??null)==='not') $this->expandedCost($atom['clauses'],$remaining);
        }
    }
    function parse() {
        if (!$this->tokens) return array('version'=>1,'clauses'=>array(array()));
        $ast=$this->orNode();
        if ($this->pos!==count($this->tokens)) throw new LoldexQueryError('Unexpected query token');
        $clauses=$this->dnf($ast); $remaining=4096; $this->expandedCost($clauses,$remaining);
        return array('version'=>1,'clauses'=>$clauses);
    }
}
function loldex_search_parse($query) { return (new LoldexSearchParser($query))->parse(); }
function loldex_search_claims($entry) {
    $out=array();
    foreach ((array)loldex_get($entry,'claims',new stdClass()) as $field=>$payload) {
        $items=is_array($payload) ? $payload : array($payload);
        $index=0;
        foreach ($items as $claim) if (is_object($claim) || is_array($claim)) $out[]=array('field'=>$field,'index'=>$index++,'claim'=>$claim);
    }
    return $out;
}
function loldex_search_sources($entry) {
    $out=array(); foreach (loldex_get($entry,'sources',array()) as $source) { $value=loldex_get($source,'project'); if (is_string($value)) $out[]=$value; } return $out;
}
function loldex_search_text_fields($entry) {
    $out=array();
    foreach (array('id'=>100,'name'=>90,'platform'=>10,'type'=>10,'privilege_required'=>15) as $key=>$weight) { $v=loldex_get($entry,$key); if (is_string($v) && $v!=='') $out[]=array('path'=>$key,'value'=>$v,'weight'=>$weight); }
    foreach (array('aliases'=>70,'attack_techniques'=>60,'technique_names'=>60,'capabilities'=>30,'phases'=>25,'references'=>5) as $key=>$weight) foreach (loldex_get($entry,$key,array()) as $i=>$v) if (is_string($v) && $v!=='') $out[]=array('path'=>$key.'.'.$i,'value'=>$v,'weight'=>$weight);
    foreach (loldex_get($entry,'commands',array()) as $i=>$command) { $v=loldex_get($command,'template'); if (is_string($v) && $v!=='') $out[]=array('path'=>'commands.'.$i.'.template','value'=>$v,'weight'=>40); }
    foreach (loldex_search_sources($entry) as $i=>$source) $out[]=array('path'=>'sources.'.$i.'.project','value'=>$source,'weight'=>10);
    $evidence=loldex_search_claims($entry);
    foreach ($out as &$item) {
        $field=explode('.', $item['path'])[0];
        $item['claimField']=in_array($field, array_values(LOLDEX_SEARCH_CLAIM), true);
        $item['evidence']=array();
        if ($item['claimField']) foreach ($evidence as $claim) if ($claim['field']===$field && loldex_norm(loldex_get($claim['claim'],'value'))===loldex_norm($item['value'])) $item['evidence'][]=$claim;
    }
    unset($item);
    return $out;
}
function loldex_search_atom($entry,$atom) {
    $value=loldex_norm($atom['value']); $field=$atom['field']; $reasons=array();
    if ($field===null) {
        foreach (loldex_search_text_fields($entry) as $item) if (strpos(loldex_norm($item['value']),$value)!==false) {
            $base=array('field'=>$item['path'],'value'=>$item['value'],'query'=>$atom['value'],'claim_field'=>$item['claimField'],'score'=>$item['weight']+(loldex_norm($item['value'])===$value?20:0));
            if ($item['evidence']) foreach ($item['evidence'] as $claim) $reasons[]=array_merge($base,array('claim'=>$claim['claim'],'claim_path'=>'claims.'.$claim['field'].'.'.$claim['index']));
            else $reasons[]=$base;
        }
    } elseif ($field==='confidence' || $field==='provenance') {
        foreach (loldex_search_claims($entry) as $item) {
            $metadata=loldex_get($item['claim'],$field==='confidence'?'confidence':'provenance');
            if (loldex_norm(loldex_get($metadata,$field==='confidence'?'level':'type'))===$value) $reasons[]=array('field'=>'claims.'.$item['field'].'.'.$item['index'],'claim'=>$item['claim'],'query'=>$atom['value'],'score'=>10);
        }
    } else {
        if ($field==='source') $values=loldex_search_sources($entry);
        elseif (isset(LOLDEX_SEARCH_CLAIM[$field])) { $v=loldex_get($entry,LOLDEX_SEARCH_CLAIM[$field]); $values=is_array($v)?$v:array($v); }
        elseif ($field==='freshness') $values=array(loldex_get(loldex_get($entry,'freshness'),'classification','NOT_OBSERVED'));
        else $values=array(loldex_get($entry,$field));
        foreach ($values as $v) if (is_string($v) && loldex_norm($v)===$value) $reasons[]=array('field'=>$field==='source'?'sources':(LOLDEX_SEARCH_CLAIM[$field]??$field),'value'=>$v,'query'=>$atom['value'],'score'=>20);
    }
    return array('ok'=>count($reasons)>0,'reasons'=>$reasons);
}
function loldex_search_evaluate($entry,$parsed,&$memo=null) {
    if ($memo===null) $memo=array();
    // Opaque NOT scopes are context-independent within one entry evaluation.
    $memoKey=($parsed['op']??null)==='not'?($parsed['_memo_key']??hash('sha256',serialize($parsed['clauses']))):null;
    if ($memoKey!==null && array_key_exists($memoKey,$memo)) return $memo[$memoKey];
    $best=null;
    foreach ($parsed['clauses'] as $clause) {
        $reasons=array(); $ok=true; $positive=array(); $eligibleClaim=null;
        foreach ($clause as $atom) {
            if (($atom['op']??null)==='not') { if (loldex_search_evaluate($entry,$atom,$memo)!==null) { $ok=false; break; } continue; }
            $positive[]=$atom; $match=loldex_search_atom($entry,$atom);
            if (!$match['ok']) { $ok=false; break; } $reasons=array_merge($reasons,$match['reasons']);
        }
        if (!$ok) continue;
        $qualifiers=array_values(array_filter($positive,function($a){return in_array($a['field'],array('confidence','provenance'),true);}));
        $sourceFilters=array_values(array_filter($positive,function($a){return $a['field']==='source';}));
        $hasClaimFacet=false; $hasClaimOnlyText=false;
        foreach ($positive as $atom) {
            if (isset(LOLDEX_SEARCH_CLAIM[$atom['field']])) $hasClaimFacet=true;
            if ($atom['field']===null) {
                $matches=loldex_search_atom($entry,$atom)['reasons']; $onlyClaims=(bool)$matches;
                foreach ($matches as $reason) if (empty($reason['claim_field'])) $onlyClaims=false;
                if ($onlyClaims) $hasClaimOnlyText=true;
            }
        }
        if ($qualifiers || ($sourceFilters && ($hasClaimFacet || $hasClaimOnlyText))) {
            $supporting=array_values(array_filter(loldex_search_claims($entry),function($x)use($qualifiers,$sourceFilters){
                foreach ($qualifiers as $a) { $meta=loldex_get($x['claim'],$a['field']==='confidence'?'confidence':'provenance'); if (loldex_norm(loldex_get($meta,$a['field']==='confidence'?'level':'type'))!==loldex_norm($a['value'])) return false; }
                foreach ($sourceFilters as $a) if (loldex_norm(loldex_get(loldex_get($x['claim'],'provenance'),'source'))!==loldex_norm($a['value'])) return false;
                return true;
            }));
            $facets=array_values(array_filter($positive,function($a){return isset(LOLDEX_SEARCH_CLAIM[$a['field']]);}));
            $groups=array();
            if ($facets) foreach ($facets as $a) $groups[]=array_values(array_filter($supporting,function($x)use($a){return $x['field']===LOLDEX_SEARCH_CLAIM[$a['field']] && loldex_norm(loldex_get($x['claim'],'value'))===loldex_norm($a['value']);}));
            else $groups=array($supporting);
            foreach ($groups as $group) if (!$group) { $ok=false; break; }
            if (!$ok) continue;
            $eligible=function($reason)use($supporting){
                if (!array_key_exists('claim',$reason)) return false;
                foreach ($supporting as $item) if ($item['claim']===$reason['claim']) return true;
                return false;
            };
            $eligibleClaim=$eligible;
            foreach ($positive as $atom) if ($atom['field']===null) {
                $matches=loldex_search_atom($entry,$atom)['reasons']; $onlyClaims=true; $anyEligible=false;
                foreach ($matches as $match) { if (empty($match['claim_field'])) $onlyClaims=false; if ($eligible($match)) $anyEligible=true; }
                if ($onlyClaims && !$anyEligible) { $ok=false; break; }
            }
            if (!$ok) continue;
            $reasons=array_values(array_filter($reasons,function($r)use($eligible){return !empty($r['claim_field'])?$eligible($r):!array_key_exists('claim',$r);}));
            foreach ($groups as $group) foreach ($group as $x) $reasons[]=array('field'=>'claims.'.$x['field'].'.'.$x['index'],'claim'=>$x['claim'],'score'=>10);
        }
        $score=0;
        foreach ($positive as $atom) { $strongest=0; foreach (loldex_search_atom($entry,$atom)['reasons'] as $r) if ($eligibleClaim===null || empty($r['claim_field']) || $eligibleClaim($r)) $strongest=max($strongest,$r['score']); $score+=$strongest; }
        if ($best===null || $score>$best['score']) $best=array('entry'=>$entry,'score'=>$score,'reasons'=>$reasons);
    }
    if ($memoKey!==null) $memo[$memoKey]=$best;
    return $best;
}
function loldex_search_values($entry,$field) {
    if ($field==='source') return loldex_search_sources($entry);
    if ($field==='confidence' || $field==='provenance') { $out=array(); foreach (loldex_search_claims($entry) as $claim) $out[]=loldex_get(loldex_get($claim['claim'],$field==='confidence'?'confidence':'provenance'),$field==='confidence'?'level':'type'); return $out; }
    if ($field==='freshness') return array(loldex_get(loldex_get($entry,'freshness'),'classification','NOT_OBSERVED'));
    if (isset(LOLDEX_SEARCH_CLAIM[$field])) { $value=loldex_get($entry,LOLDEX_SEARCH_CLAIM[$field]); return is_array($value)?$value:array($value); }
    return array(loldex_get($entry,$field));
}
function loldex_search_prepare($clauses) {
    foreach ($clauses as &$clause) foreach ($clause as &$atom) {
        if (($atom['op']??null)==='not') {
            $atom['_memo_key']=hash('sha256',serialize($atom['clauses']));
            $atom['clauses']=loldex_search_prepare($atom['clauses']);
        }
    }
    unset($clause,$atom); return $clauses;
}
function loldex_search($entries,$query,$offset=0,$limit=50,$extra=array()) {
    if (!is_array($entries)) throw new LoldexQueryError('Entries must be an array');
    if (!is_int($offset) || $offset<0 || !is_int($limit) || $limit<1 || $limit>500) throw new LoldexQueryError('Invalid pagination');
    $parsed=loldex_search_parse($query);
    $parsed['clauses']=loldex_search_prepare($parsed['clauses']);
    foreach ($parsed['clauses'] as &$clause) $clause=array_merge($clause,$extra); unset($clause);
    $results=array(); $entryMemos=array();
    foreach ($entries as $entry) {
        $key=is_object($entry)?'o'.spl_object_id($entry):'a'.hash('sha256',serialize($entry));
        $memo=array(); $result=loldex_search_evaluate($entry,$parsed,$memo);
        if ($result!==null) { $results[]=$result; $entryMemos[$key]=$memo; }
    }
    usort($results,function($a,$b){return $b['score']<=>$a['score'] ?: strcmp(loldex_get($a['entry'],'id'),loldex_get($b['entry'],'id'));});
    $facets=array();
    foreach (LOLDEX_SEARCH_FIELDS as $field) {
        $counts=array();
        foreach ($results as $result) {
            $entry=$result['entry']; $values=array();
            $key=is_object($entry)?'o'.spl_object_id($entry):'a'.hash('sha256',serialize($entry));
            $memo=&$entryMemos[$key];
            foreach (loldex_search_values($entry,$field) as $value) if (is_string($value) && !in_array($value,$values,true)) $values[]=$value;
            foreach ($values as $value) {
                $constrained=$parsed;
                foreach ($constrained['clauses'] as &$clause) $clause[]=array('field'=>$field,'value'=>$value); unset($clause);
                if (loldex_search_evaluate($entry,$constrained,$memo)!==null) $counts[$value]=($counts[$value]??0)+1;
            }
        }
        unset($memo);
        uksort($counts,'strcmp'); $facets[$field]=array();
        foreach ($counts as $value=>$count) $facets[$field][]=array('value'=>(string)$value,'count'=>$count);
    }
    return array('version'=>1,'total'=>count($results),'offset'=>$offset,'limit'=>$limit,
                 'results'=>array_slice($results,$offset,$limit),'facets'=>$facets);
}
