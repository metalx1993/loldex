<?php
/** Stable security bridge for retained immutable PHP endpoints. Static assets stay pinned. */
function loldex_retained_fail($status, $v1=false, $code='REQUEST_REJECTED', $retry=null) {
    http_response_code($status);
    if ($retry !== null) header('Retry-After: '.max(1,(int)$retry));
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') {
        $message=$status===429?'Too many requests. Please retry later.':($status===503?'Service temporarily unavailable.':'Request rejected.');
        echo json_encode($v1 ? array('api_version'=>'1','dataset'=>null,'data'=>null,'error'=>array('code'=>$code,'message'=>$message)) : array('error'=>$message),JSON_UNESCAPED_SLASHES);
    }
    exit;
}
function loldex_retained_canonical($value) {
    if (is_object($value)) { $keys=get_object_vars($value); uksort($keys,'strcmp'); $out=new stdClass(); foreach($keys as $key=>$item)$out->$key=loldex_retained_canonical($item); return $out; }
    if (is_array($value)) return array_map('loldex_retained_canonical',$value);
    return $value;
}
function loldex_retained_json($value) { return json_encode(loldex_retained_canonical($value),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_LINE_TERMINATORS|JSON_THROW_ON_ERROR); }
function loldex_retained_regular($path) {
    if (!is_string($path) || $path==='' || $path[0]!=='/') return false;
    $walk=''; foreach(explode('/',trim($path,'/')) as $part) { if ($part==='' || $part==='.' || $part==='..')return false; $walk.='/'.$part; if(is_link($walk))return false; }
    return is_file($path);
}
function loldex_retained_manifest($folder,$id) {
    $path=$folder.'/release.json';
    if (!loldex_retained_regular($path) || filesize($path)>4194304) throw new RuntimeException('Unavailable release');
    $raw=file_get_contents($path);$manifest=json_decode($raw,false,16,JSON_THROW_ON_ERROR);
    if (!is_object($manifest))throw new RuntimeException('Unavailable release');
    $keys=array_keys(get_object_vars($manifest));sort($keys);
    if ($keys!==array('commit','files','release_id','version') || $manifest->version!==1 || $manifest->release_id!==$id || !is_string($manifest->commit) || !preg_match('/\A[a-f0-9]{40}\z/',$manifest->commit) || !is_object($manifest->files) || count(get_object_vars($manifest->files))>20000 || loldex_retained_json($manifest)!==$raw)throw new RuntimeException('Unavailable release');
    foreach(get_object_vars($manifest->files) as $name=>$digest)if(strlen($name)>255 || $name==='' || !is_string($digest) || !preg_match('/\Asha256:[a-f0-9]{64}\z/',$digest))throw new RuntimeException('Unavailable release');
    $payload=(object)array('version'=>1,'commit'=>$manifest->commit,'files'=>$manifest->files);
    if ('r-'.hash('sha256',loldex_retained_json($payload))!==$id)throw new RuntimeException('Unavailable release');
    return $manifest;
}
function loldex_retained_verify($folder,$manifest,$name) {
    $digest=$manifest->files->$name ?? null; $path=$folder.'/'.$name;
    return is_string($digest) && loldex_retained_regular($path) && filesize($path)<=67108864 && hash_equals($digest,'sha256:'.hash_file('sha256',$path));
}
function loldex_retained_pairs($raw,$v1) {
    if (!is_string($raw) || strlen($raw)>16384 || preg_match('/%(?![a-f0-9]{2})/i',$raw))throw new InvalidArgumentException('Invalid query');
    $out=array();if($raw==='')return $out;$pairs=explode('&',$raw);if(count($pairs)>32)throw new InvalidArgumentException('Invalid query');
    foreach($pairs as $pair){
        if($pair==='')throw new InvalidArgumentException('Invalid query');$parts=explode('=',$pair,2);$key=urldecode($parts[0]);$value=urldecode($parts[1]??'');
        $controls=$v1 && $key==='q'?'/[\x00-\x08\x0e-\x1f\x7f]/':'/[\x00-\x1f\x7f]/';
        if(!preg_match('/\A[a-z][a-z_]*\z/',$key) || array_key_exists($key,$out) || strlen($value)>4096 || !preg_match('//u',$value) || preg_match($controls,$value))throw new InvalidArgumentException('Invalid query');$out[$key]=$value;
    }
    return $out;
}
header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');header('Referrer-Policy: strict-origin-when-cross-origin');header('Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()');header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
set_error_handler(function($severity,$message,$file,$line){if(error_reporting()&$severity)throw new ErrorException('Request operation failed',0,$severity);return true;});
$v1=false;$bufferLevel=ob_get_level();
try {
    $uri=$_SERVER['REQUEST_URI']??'';if(!is_string($uri) || strlen($uri)>24576)loldex_retained_fail(400);
    $parts=explode('?',$uri,2);$path=$parts[0];
    if(!preg_match('~\A/releases/(r-[a-f0-9]{64})/(api\.php|api-v1\.php|contact\.php|api/v1(?:/([a-z]+))?|api/([a-z]+))/?\z~',$path,$match))loldex_retained_fail(400);
    $id=$match[1];$route=$match[2];$v1=$route==='api-v1.php' || $route==='api/v1' || strpos($route,'api/v1/')===0;
    $contact=$route==='contact.php';$file=$contact?'contact.php':($v1?'api-v1.php':'api.php');
    $method=$_SERVER['REQUEST_METHOD']??'GET';
    if(!$contact){
        header('Access-Control-Allow-Origin: *');header('Access-Control-Allow-Methods: GET, HEAD, OPTIONS');header('Access-Control-Allow-Headers: If-None-Match, Content-Type');header('Access-Control-Expose-Headers: ETag, X-LOLDEX-Dataset, Retry-After');header('Allow: GET, HEAD, OPTIONS');
        if($method==='OPTIONS'){http_response_code(204);exit;}
        if($method!=='GET' && $method!=='HEAD')loldex_retained_fail(405,$v1,'METHOD_NOT_ALLOWED');
    } elseif($method!=='POST'){header('Allow: POST');loldex_retained_fail(405);}
    $params=loldex_retained_pairs($parts[1]??'',$v1);
    if($route==='api/v1' || strpos($route,'api/v1/')===0){if(isset($params['resource']))throw new InvalidArgumentException('Ambiguous route');$params=array_merge(array('resource'=>$match[3]??'root'),$params);}
    elseif(strpos($route,'api/')===0){if(isset($params['action']))throw new InvalidArgumentException('Ambiguous route');$params=array_merge(array('action'=>$match[4]),$params);}
    // Preserve validated raw bytes, including V1 whitespace and byte-budget
    // semantics; pretty routes add only their fixed trusted routing parameter.
    $query=$parts[1]??'';
    if($route==='api/v1' || strpos($route,'api/v1/')===0)$query='resource='.($match[3]??'root').($query!==''?'&'.$query:'');
    elseif(strpos($route,'api/')===0)$query='action='.$match[4].($query!==''?'&'.$query:'');
    $folder=__DIR__.'/releases/'.$id;$manifest=loldex_retained_manifest($folder,$id);
    if(!loldex_retained_verify($folder,$manifest,$file))throw new RuntimeException('Unavailable endpoint');
    $guarded=property_exists($manifest->files,'request-guard.php');
    if($guarded && !loldex_retained_verify($folder,$manifest,'request-guard.php'))throw new RuntimeException('Unavailable guard');
    if($contact && !$guarded){
        // Never execute an old mail handler. A rollback to an unguarded active
        // version returns503 rather than redirecting back into the same handler.
        $activePath=dirname(__DIR__).'/loldex-control/active.json';
        if(!loldex_retained_regular($activePath) || filesize($activePath)>8192)throw new RuntimeException('Unavailable state');
        $raw=file_get_contents($activePath);$active=json_decode($raw,false,8,JSON_THROW_ON_ERROR);
        if(!is_object($active))throw new RuntimeException('Unavailable state');$keys=array_keys(get_object_vars($active));sort($keys);
        if($keys!==array('commit','generation','previous_release_id','release_id','version') || $active->version!==1 || !is_int($active->generation) || $active->generation<1 || $active->generation>9007199254740991 || !is_string($active->release_id) || !preg_match('/\Ar-[a-f0-9]{64}\z/',$active->release_id) || loldex_retained_json($active)!==$raw)throw new RuntimeException('Unavailable state');
        $currentFolder=__DIR__.'/releases/'.$active->release_id;$current=loldex_retained_manifest($currentFolder,$active->release_id);
        if($current->commit!==$active->commit || !loldex_retained_verify($currentFolder,$current,'request-guard.php') || !loldex_retained_verify($currentFolder,$current,'contact.php'))throw new RuntimeException('Unavailable contact');
        $_SERVER['REQUEST_URI']='/contact.php'.($query!==''?'?'.$query:'');require __DIR__.'/loldex-router.php';exit;
    }
    $_SERVER['QUERY_STRING']=$query;$_GET=$params;
    if(!$guarded){
        if(!$v1){
            foreach($params as $key=>$value)if(!in_array($key,array('action','q','platform','os','priv','cap','phase','type','limit','offset','id'),true))throw new InvalidArgumentException('Invalid query');
            foreach(array('limit','offset') as $key)if(isset($params[$key]) && $params[$key]!=='' && (!preg_match('/\A(?:0|[1-9][0-9]{0,7})\z/',$params[$key]) || (int)$params[$key]>10000000))throw new InvalidArgumentException('Invalid pagination');
        }
        $private=dirname(__DIR__).'/loldex-control';$helper=$private.'/tools/security/request-guard.php';
        if(!loldex_retained_regular($helper))throw new RuntimeException('Unavailable guard');
        putenv('LOLDEX_RATE_LIMIT_DIR='.$private.'/rate-limits');require_once $helper;
        $budget=loldex_guard_rate('api',true);
        if(!$budget['allowed'])loldex_retained_fail($budget['status'],$v1,$budget['status']===429?'RATE_LIMITED':'TEMPORARILY_UNAVAILABLE',$budget['retry_after']);
        if(!$v1 && !loldex_retained_verify($folder,$manifest,'data.json'))throw new RuntimeException('Unavailable dataset');
        if($v1){
            foreach(array('api-v1-core.php','search-engine.php') as $dependency)if(!loldex_retained_verify($folder,$manifest,$dependency))throw new RuntimeException('Unavailable endpoint');
            require_once $folder.'/api-v1-core.php';
            if(!function_exists('loldex_v1_query'))throw new RuntimeException('Unavailable endpoint');
            try { loldex_v1_query($query); } catch (LoldexApiError $error) { if($error->status===400)loldex_retained_fail(400,true,'INVALID_QUERY'); throw $error; }
        }
    }
    ob_start(function($body)use($method){return $method==='HEAD'?'':$body;});
    require $folder.'/'.$file;
    ob_end_flush();restore_error_handler();
} catch(InvalidArgumentException $error){while(ob_get_level()>$bufferLevel)ob_end_clean();loldex_retained_fail(400,$v1,'INVALID_QUERY');}
catch(Throwable $error){while(ob_get_level()>$bufferLevel)ob_end_clean();loldex_retained_fail(503,$v1,'TEMPORARILY_UNAVAILABLE',60);}
