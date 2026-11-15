<?php
/** Version 1 API: immutable release-local datasets; no upstream I/O or writes. */
require_once __DIR__ . '/search-engine.php';
class LoldexApiError extends Exception {
    public $status; public $apiCode;
    function __construct($status,$code,$message) { parent::__construct($message); $this->status=$status; $this->apiCode=$code; }
}
function loldex_v1_fail($status,$code,$message) { throw new LoldexApiError($status,$code,$message); }
function loldex_v1_json($value) { return json_encode($value,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_LINE_TERMINATORS|JSON_THROW_ON_ERROR); }
function loldex_v1_canonical($value) {
    if (is_object($value)) { $map=get_object_vars($value); uksort($map,'strcmp'); $out=new stdClass(); foreach($map as $key=>$item) $out->$key=loldex_v1_canonical($item); return $out; }
    if (is_array($value)) return array_map('loldex_v1_canonical',$value);
    return $value;
}
function loldex_v1_decode($raw) {
    try { return json_decode($raw,false,128,JSON_THROW_ON_ERROR); }
    catch (Exception $e) { loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); }
}
function loldex_v1_keys($value,$keys) {
    if (!is_object($value)) return false;
    $actual=array_keys(get_object_vars($value)); sort($actual,SORT_STRING); sort($keys,SORT_STRING); return $actual===$keys;
}
function loldex_v1_hash($value) { return is_string($value) && preg_match('/\Asha256:[a-f0-9]{64}\z/',$value)===1; }
function loldex_v1_context($directory) {
    $path=$directory.'/build-manifest.json';
    if (is_link($path) || !is_file($path) || @filesize($path)>4194304) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $raw=@file_get_contents($path); if ($raw===false) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $manifest=loldex_v1_decode($raw);
    if (!loldex_v1_keys($manifest,array('version','files','entries','registry_checksum')) || $manifest->version!==1 || !is_int($manifest->entries) || $manifest->entries<0 || !is_object($manifest->files) || !loldex_v1_hash($manifest->registry_checksum)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    if (loldex_v1_json(loldex_v1_canonical($manifest))."\n"!==$raw) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    foreach (get_object_vars($manifest->files) as $name=>$hash) {
        if (!preg_match('/\A(?:[a-z][a-z0-9-]*\.(?:json|txt)|evidence-records\/[a-f0-9]{64}\.json)\z/',$name) || !loldex_v1_hash($hash)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    }
    $dataset=array('manifest_sha256'=>'sha256:'.hash('sha256',$raw),'entry_count'=>$manifest->entries,'registry_checksum'=>$manifest->registry_checksum,'release_id'=>null,'commit'=>null);
    $retained=preg_match('/\Ar-[a-f0-9]{64}\z/',basename($directory)) || basename(dirname($directory))==='releases';
    if (is_link($directory.'/release.json') || ($retained && !is_file($directory.'/release.json'))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    if (is_file($directory.'/release.json')) {
        if (is_link($directory.'/release.json')) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $releaseRaw=@file_get_contents($directory.'/release.json');
        $release=loldex_v1_decode($releaseRaw);
        if (!loldex_v1_keys($release,array('version','commit','files','release_id')) || $release->version!==1 || !is_object($release->files) || !is_string($release->release_id) || !preg_match('/\Ar-[a-f0-9]{64}\z/',$release->release_id) || !is_string($release->commit) || !preg_match('/\A[a-f0-9]{40}\z/',$release->commit) || basename($directory)!==$release->release_id) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $releasePayload=(object)array('version'=>1,'commit'=>$release->commit,'files'=>$release->files);
        if (loldex_v1_json(loldex_v1_canonical($release))!==$releaseRaw || $release->release_id!=='r-'.hash('sha256',loldex_v1_json(loldex_v1_canonical($releasePayload))) || loldex_get($release->files,'build-manifest.json')!==$dataset['manifest_sha256']) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $dataset['release_id']=$release->release_id; $dataset['commit']=$release->commit;
    }
    return array('directory'=>$directory,'manifest'=>$manifest,'dataset'=>$dataset,'loaded'=>array(),'raw'=>array());
}
function loldex_v1_load(&$context,$name) {
    if (array_key_exists($name,$context['loaded'])) return $context['loaded'][$name];
    if (!property_exists($context['manifest']->files,$name)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $path=$context['directory'].'/'.$name;
    if (is_link($path) || !is_file($path) || @filesize($path)>33554432) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    if (strpos($name,'evidence-records/')===0 && (is_link($context['directory'].'/evidence-records') || !is_dir($context['directory'].'/evidence-records'))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $raw=@file_get_contents($path);
    if ($raw===false || !hash_equals($context['manifest']->files->$name,'sha256:'.hash('sha256',$raw))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $context['raw'][$name]=$raw;
    return $context['loaded'][$name]=loldex_v1_decode($raw);
}
function loldex_v1_query($raw) {
    if (!is_string($raw) || strlen($raw)>16384 || preg_match('/%(?![a-f0-9]{2})/i',$raw)) loldex_v1_fail(400,'INVALID_QUERY','Query parameters are malformed.');
    $params=array(); if ($raw==='') return $params;
    foreach (explode('&',$raw) as $pair) {
        if ($pair==='') loldex_v1_fail(400,'INVALID_QUERY','Query parameters are malformed.');
        $parts=explode('=',$pair,2); $key=urldecode($parts[0]); $value=urldecode($parts[1]??'');
        if (!preg_match('/\A[a-z][a-z_]*\z/',$key) || array_key_exists($key,$params) || !preg_match('//u',$value)) loldex_v1_fail(400,'INVALID_QUERY','Query parameters must be unique scalar UTF-8 values.');
        if (($key==='q' && preg_match('/[\x00-\x08\x0e-\x1f\x7f]/',$value)) || ($key!=='q' && preg_match('/[\x00-\x1f\x7f]/',$value))) loldex_v1_fail(400,'INVALID_QUERY','Query parameters contain invalid control characters.');
        if (($key==='q' && strlen($value)>4096) || ($key!=='q' && strlen($value)>4096)) loldex_v1_fail(400,'INVALID_QUERY','Query parameter exceeds its size limit.');
        $params[$key]=$value;
    }
    return $params;
}
function loldex_v1_integer($params,$key,$default,$minimum,$maximum) {
    if (!isset($params[$key])) return $default;
    $value=$params[$key];
    if (!preg_match('/\A(?:0|[1-9][0-9]*)\z/',$value) || strlen($value)>10 || (float)$value>$maximum || (int)$value<$minimum) loldex_v1_fail(400,'INVALID_PAGINATION','Pagination must use bounded canonical decimal integers.');
    return (int)$value;
}
function loldex_v1_pagination($total,$offset,$limit) { return array('total'=>$total,'offset'=>$offset,'limit'=>$limit,'next_offset'=>$offset+$limit<$total?$offset+$limit:null); }
function loldex_v1_list($value,$key) { $list=loldex_get($value,$key); if (!is_array($list)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); return $list; }
function loldex_v1_catalog(&$context) {
    $catalog=loldex_v1_load($context,'catalog.json');
    if (loldex_get($catalog,'version')!==1 || loldex_get($catalog,'count')!==$context['manifest']->entries) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $entries=loldex_v1_list($catalog,'entries');
    if (count($entries)!==$context['manifest']->entries) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
    $seen=array();
    foreach ($entries as $entry) { $id=loldex_get($entry,'id'); if (!is_string($id) || $id==='' || isset($seen[$id]) || !is_object(loldex_get($entry,'claims',new stdClass()))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); $seen[$id]=true; }
    usort($entries,function($a,$b){return strcmp($a->id,$b->id);}); return $entries;
}
function loldex_v1_find($entries,$id) { foreach ($entries as $entry) if ($entry->id===$id) return $entry; loldex_v1_fail(404,'NOT_FOUND','The requested resource was not found in this dataset.'); }
function loldex_v1_required_id($params) { if (!isset($params['id']) || $params['id']==='') loldex_v1_fail(400,'INVALID_QUERY','A non-empty id is required.'); return $params['id']; }
function loldex_v1_filters($params) {
    $out=array(); foreach (LOLDEX_SEARCH_FIELDS as $field) if (isset($params[$field])) { if ($params[$field]==='') loldex_v1_fail(400,'INVALID_QUERY','Filter values must not be empty.'); $out[]=array('field'=>$field,'value'=>$params[$field]); } return $out;
}
function loldex_v1_resource(&$context,$resource,$params) {
    $listResources=array('entries','search','graph','techniques','identities');
    $limit=in_array($resource,$listResources,true)?loldex_v1_integer($params,'limit',50,1,200):50;
    $offset=in_array($resource,$listResources,true)?loldex_v1_integer($params,'offset',0,0,10000000):0;
    if ($resource==='root') return array('data'=>array('name'=>'LOLDEX API','resources'=>array('entries','entry','evidence','search','graph','techniques','technique','identities','identity','resolve'),'read_only'=>true,'max_limit'=>200,'search_version'=>1));
    if ($resource==='resolve') {
        $id=loldex_v1_required_id($params); $entries=loldex_v1_catalog($context); $current=array();
        foreach ($entries as $entry) { $current[$entry->id]=true; if ($entry->id===$id) return array('data'=>array('kind'=>'entry','entry_id'=>$id)); }
        $identities=loldex_v1_load($context,'identities.json');
        if (loldex_get($identities,'version')!==1) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $aliases=loldex_v1_list($identities,'aliases'); $seen=array(); $found=null;
        foreach ($aliases as $alias) {
            $old=loldex_get($alias,'old_entry_id'); $targets=loldex_get($alias,'new_entry_ids'); $status=loldex_get($alias,'status');
            if (!is_string($old) || isset($seen[$old]) || !is_array($targets) || !$targets || !in_array($status,array('active','split'),true) || ($status==='active' && count($targets)!==1) || ($status==='split' && count($targets)<2)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
            $seen[$old]=true; $targetSeen=array();
            foreach ($targets as $target) { if (!is_string($target) || !isset($current[$target]) || isset($targetSeen[$target])) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); $targetSeen[$target]=true; }
            if ($old===$id) $found=$alias;
        }
        if ($found!==null) return array('data'=>array('kind'=>'alias','alias'=>$found));
        loldex_v1_fail(404,'NOT_FOUND','The requested resource was not found in this dataset.');
    }
    if (in_array($resource,array('entry','evidence','entries','search'),true)) {
        $entries=loldex_v1_catalog($context);
        if ($resource==='entry' || $resource==='evidence') {
            $entry=loldex_v1_find($entries,loldex_v1_required_id($params));
            if (isset($params['include']) && $params['include']!=='evidence') loldex_v1_fail(400,'INVALID_QUERY','Only include=evidence is supported.');
            $evidence=null;
            if ($resource==='evidence' || ($params['include']??null)==='evidence') {
                $evidence=loldex_v1_load($context,'evidence-records/'.hash('sha256',$entry->id).'.json');
                if (!is_object($evidence)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
            }
            $shard='evidence-records/'.hash('sha256',$entry->id).'.json';
            if ($resource==='evidence') return array('data'=>$evidence,'_raw_data_json'=>$context['raw'][$shard]);
            $data=array('entry'=>$entry);
            if ($evidence!==null) return array('data'=>$data,'_raw_data_json'=>'{"entry":'.loldex_v1_json($entry).',"evidence":'.rtrim($context['raw'][$shard]).'}');
            return array('data'=>$data);
        }
        $filters=loldex_v1_filters($params);
        if ($resource==='search') {
            $query=$params['q']??'';
            $result=loldex_search($entries,$query,$offset,$limit,$filters);
            return array('data'=>$result['results'],'pagination'=>loldex_v1_pagination($result['total'],$offset,$limit),'facets'=>$result['facets'],'query'=>array('text'=>$query,'ast'=>loldex_search_parse($query),'filters'=>$filters,'semantics'=>'search-v1-ascii-fold-exact-unicode'));
        }
        $parsed=array('version'=>1,'clauses'=>array($filters)); $hits=array();
        foreach ($entries as $entry) if (loldex_search_evaluate($entry,$parsed)!==null) $hits[]=$entry;
        return array('data'=>array_slice($hits,$offset,$limit),'pagination'=>loldex_v1_pagination(count($hits),$offset,$limit));
    }
    if ($resource==='graph') {
        $graph=loldex_v1_load($context,'graph.json');
        if (loldex_get($graph,'version')!==1) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $nodes=loldex_v1_list($graph,'nodes'); $edges=loldex_v1_list($graph,'edges'); $nodeMap=array(); $edgeIDs=array();
        foreach ($nodes as $node) { $id=loldex_get($node,'id'); if (!is_string($id) || isset($nodeMap[$id])) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); $nodeMap[$id]=$node; }
        $entryNode=isset($params['entry_id'])?'entry:'.$params['entry_id']:null;
        if ($entryNode!==null && !isset($nodeMap[$entryNode])) loldex_v1_fail(404,'NOT_FOUND','The requested resource was not found in this dataset.');
        $allowedRelations=array('implements','has_capability','operates_in','belongs_to','sourced_from');
        if (isset($params['relation']) && !in_array($params['relation'],$allowedRelations,true)) loldex_v1_fail(400,'INVALID_QUERY','Unknown graph relation.');
        $hits=array();
        foreach ($edges as $edge) {
            $id=loldex_get($edge,'id'); $from=loldex_get($edge,'from'); $to=loldex_get($edge,'to');
            if (!is_string($id) || isset($edgeIDs[$id]) || !isset($nodeMap[$from],$nodeMap[$to]) || !is_object(loldex_get($edge,'provenance')) || !is_object(loldex_get($edge,'confidence'))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
            $edgeIDs[$id]=true;
            if ($entryNode!==null && $from!==$entryNode && $to!==$entryNode) continue;
            if (isset($params['relation']) && loldex_get($edge,'type')!==$params['relation']) continue;
            $hits[]=$edge;
        }
        usort($hits,function($a,$b){return strcmp($a->id,$b->id);}); $page=array_slice($hits,$offset,$limit);
        $used=array(); if ($entryNode!==null) $used[$entryNode]=true;
        foreach ($page as $edge) { $used[$edge->from]=true; $used[$edge->to]=true; }
        $ids=array_keys($used); sort($ids,SORT_STRING); $included=array(); foreach ($ids as $id) $included[]=$nodeMap[$id];
        return array('data'=>array('nodes'=>$included,'edges'=>$page),'pagination'=>loldex_v1_pagination(count($hits),$offset,$limit));
    }
    if ($resource==='techniques' || $resource==='technique') {
        $dataset=loldex_v1_load($context,'techniques.json');
        if (loldex_get($dataset,'version')!==1) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $items=loldex_v1_list($dataset,'techniques'); $seen=array();
        foreach ($items as $item) { $id=loldex_get($item,'id'); if (!is_string($id) || isset($seen[$id])) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); $seen[$id]=true; }
        usort($items,function($a,$b){return strcmp($a->id,$b->id);});
        if ($resource==='technique') return array('data'=>loldex_v1_find($items,loldex_v1_required_id($params)));
        if (isset($params['q'])) $items=array_values(array_filter($items,function($item)use($params){return strpos(loldex_norm($item->id.' '.loldex_get($item,'name','')),loldex_norm($params['q']))!==false;}));
        return array('data'=>array_slice($items,$offset,$limit),'pagination'=>loldex_v1_pagination(count($items),$offset,$limit));
    }
    if ($resource==='identities' || $resource==='identity') {
        $dataset=loldex_v1_load($context,'identities.json');
        if (loldex_get($dataset,'version')!==1) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
        $entities=loldex_v1_list($dataset,'entities'); $candidates=loldex_v1_list($dataset,'candidates'); $seen=array();
        foreach ($entities as $entity) { $id=loldex_get($entity,'id'); if (!is_string($id) || isset($seen[$id]) || !is_array(loldex_get($entity,'members'))) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.'); $seen[$id]=true; }
        usort($entities,function($a,$b){return strcmp($a->id,$b->id);});
        if ($resource==='identity') {
            $entity=loldex_v1_find($entities,loldex_v1_required_id($params)); $suggestions=array();
            foreach ($candidates as $candidate) if (loldex_get($candidate,'entity_id')===$entity->id) $suggestions[]=$candidate;
            usort($suggestions,function($a,$b){return strcmp($a->id,$b->id);});
            return array('data'=>array('entity'=>$entity,'candidates'=>$suggestions,'equivalence'=>'not_inferred'));
        }
        if (isset($params['entry_id'])) {
            $index=loldex_get($dataset,'entry_index');
            if (!is_object($index)) loldex_v1_fail(503,'DATASET_UNAVAILABLE','The pinned dataset is unavailable.');
            $refs=loldex_get($index,$params['entry_id'],array()); $allowed=array(); foreach ($refs as $ref) $allowed[loldex_get($ref,'entity_id')]=true;
            $entities=array_values(array_filter($entities,function($entity)use($allowed){return isset($allowed[$entity->id]);}));
        }
        return array('data'=>array_slice($entities,$offset,$limit),'pagination'=>loldex_v1_pagination(count($entities),$offset,$limit),'identity_policy'=>array('membership'=>'explicit_active_curation','candidates_are_members'=>false,'equivalence'=>'not_inferred'));
    }
    loldex_v1_fail(404,'NOT_FOUND','Unknown API resource.');
}
function loldex_v1_handle($method,$queryString,$directory,$ifNoneMatch=null,$requestUri='') {
    $headers=array('Content-Type'=>'application/json; charset=utf-8','X-Content-Type-Options'=>'nosniff','Access-Control-Allow-Origin'=>'*','Access-Control-Allow-Methods'=>'GET, HEAD, OPTIONS','Access-Control-Allow-Headers'=>'If-None-Match, Content-Type','Access-Control-Expose-Headers'=>'ETag, X-LOLDEX-Dataset','Allow'=>'GET, HEAD, OPTIONS','Cache-Control'=>'no-store');
    $dataset=null;
    set_error_handler(function($severity,$message,$file,$line){ if (error_reporting() & $severity) throw new ErrorException('Dataset operation failed',0,$severity); return true; });
    try {
        if ($method==='OPTIONS') return array('status'=>204,'headers'=>$headers,'body'=>'');
        if ($method!=='GET' && $method!=='HEAD') loldex_v1_fail(405,'METHOD_NOT_ALLOWED','Only GET, HEAD and OPTIONS are supported.');
        $params=loldex_v1_query($queryString); $resource=$params['resource']??'root';
        $allowed=array(
            'root'=>array(), 'entries'=>array_merge(array('limit','offset'),LOLDEX_SEARCH_FIELDS),
            'entry'=>array('id','include'),'evidence'=>array('id'),
            'search'=>array_merge(array('q','limit','offset'),LOLDEX_SEARCH_FIELDS),
            'graph'=>array('entry_id','relation','limit','offset'),
            'techniques'=>array('q','limit','offset'),'technique'=>array('id'),
            'identities'=>array('entry_id','limit','offset'),'identity'=>array('id'),'resolve'=>array('id'));
        if (!isset($allowed[$resource])) loldex_v1_fail(404,'NOT_FOUND','Unknown API resource.');
        foreach ($params as $key=>$value) if ($key!=='resource' && !in_array($key,$allowed[$resource],true)) loldex_v1_fail(400,'INVALID_QUERY','Unsupported parameter for this resource.');
        $params['resource']=$resource; ksort($params,SORT_STRING);
        $context=loldex_v1_context($directory); $dataset=$context['dataset'];
        $result=loldex_v1_resource($context,$resource,$params);
        $envelope=array('api_version'=>'1','dataset'=>$dataset);
        $rawData=$result['_raw_data_json']??null; unset($result['_raw_data_json']);
        if ($rawData!==null) {
            unset($result['data']);
            $envelope=array_merge($envelope,$result);
            $encoded=loldex_v1_json($envelope);
            // Verified original JSON preserves opaque evidence numbers and {} / [].
            $encoded=substr($encoded,0,-1).',"data":'.rtrim($rawData).'}';
        } else $encoded=loldex_v1_json(array_merge($envelope,$result));
        $encoded.="\n";
        $etag='"loldex-v1-'.hash('sha256',$encoded).'"';
        $headers['ETag']=$etag; $headers['X-LOLDEX-Dataset']=$dataset['manifest_sha256'];
        $uriPath=parse_url($requestUri,PHP_URL_PATH);
        $prefix=$dataset['release_id']!==null?'/releases/'.$dataset['release_id'].'/':null;
        $headers['Cache-Control']=$prefix!==null && is_string($uriPath) && strpos($uriPath,$prefix)===0?'public, max-age=31536000, immutable':'public, max-age=0, must-revalidate';
        $matches=false;
        if (is_string($ifNoneMatch) && strlen($ifNoneMatch)<=8192) foreach (explode(',',$ifNoneMatch) as $candidate) { $candidate=trim($candidate); if ($candidate==='*' || $candidate===$etag || $candidate==='W/'.$etag) $matches=true; }
        if ($matches) return array('status'=>304,'headers'=>$headers,'body'=>'');
        $headers['Content-Length']=(string)strlen($encoded);
        return array('status'=>200,'headers'=>$headers,'body'=>$method==='HEAD'?'':$encoded);
    } catch (LoldexQueryError $error) {
        $status=400; $code='INVALID_SEARCH_QUERY'; $message=$error->getMessage();
    } catch (LoldexApiError $error) {
        $status=$error->status; $code=$error->apiCode; $message=$error->getMessage();
    } catch (Throwable $error) {
        $status=503; $code='DATASET_UNAVAILABLE'; $message='The pinned dataset is unavailable.';
    } finally { restore_error_handler(); }
    $body=loldex_v1_json(array('api_version'=>'1','dataset'=>$dataset,'data'=>null,'error'=>array('code'=>$code,'message'=>$message)))."\n";
    return array('status'=>$status,'headers'=>$headers,'body'=>$method==='HEAD'?'':$body);
}
