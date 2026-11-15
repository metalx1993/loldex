<?php
ini_set('display_errors','stderr');ini_set('log_errors','0');error_reporting(E_ALL);
/** Opt-in CLI-only test: private disposable state, synthetic addresses, no HTTP/mail. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
if (($argv[1] ?? '') === '--child') {
    require $argv[2]; putenv('LOLDEX_RATE_LIMIT_DIR='.$argv[3]);
    $_SERVER['REMOTE_ADDR']=$argv[5];
    echo json_encode(loldex_guard_rate($argv[4],true)); exit;
}
if (($argv[1] ?? '') === '--hold') {
    $file=fopen($argv[2],'c+b'); flock($file,LOCK_EX); echo 'READY'; fflush(STDOUT); usleep(800000); exit;
}
function check($value,$message) { if (!$value) throw new RuntimeException($message); }
function child_start($guard,$directory,$scope,$ip) {
    $pipes=[];$process=proc_open([PHP_BINARY,__FILE__,'--child',$guard,$directory,$scope,$ip],[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
    check(is_resource($process),'child start failed');fclose($pipes[0]);return [$process,$pipes];
}
function child_end($child) {
    [$process,$pipes]=$child;$out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);$code=proc_close($process);
    check($code===0 && $err==='', 'child error: '.$err);$value=json_decode($out,true,16,JSON_THROW_ON_ERROR);check(is_array($value),'invalid child result');return $value;
}
function batch($guard,$directory,$addresses) {
    $children=[];foreach($addresses as $ip)$children[]=child_start($guard,$directory,'contact',$ip);
    return array_map('child_end',$children);
}
function counts($results) { $counts=[];foreach($results as $r){$s=$r['status'];$counts[$s]=($counts[$s]??0)+1;}ksort($counts);return $counts; }
$guard=$argv[1]??'';$parent=$argv[2]??'';
check(is_file($guard) && is_dir($parent) && is_writable($parent),'Usage: php security-native.php /private/harness/request-guard.php /private/test-parent');
$root=$parent.'/native-quota-'.bin2hex(random_bytes(8));check(mkdir($root,0700),'test root creation failed');
try {
    // First creation is native, with no fixture permissions/chmod supplied by this harness.
    $one=$root.'/one';$first=child_end(child_start($guard,$one,'api','192.0.2.1'));check($first['status']===200,'initial native admission failed');
    foreach(['key','state.lock','state.json'] as $name){clearstatcache(true,$one.'/'.$name);check((fileperms($one.'/'.$name)&0777)===0600,'private file mode incorrect: '.$name);}
    check((fileperms($one)&0777)===0700,'private directory mode incorrect');
    $same=batch($guard,$one,array_fill(0,20,'2001:db8::1'));check(counts($same)===[200=>3,429=>17],'concurrent per-client cap incorrect: '.json_encode(counts($same)));
    $equivalent=child_end(child_start($guard,$one,'contact','2001:0db8:0:0:0:0:0:1'));check($equivalent['status']===429,'canonical IPv6 bypass');
    $two=$root.'/two';check(child_end(child_start($guard,$two,'api','192.0.2.1'))['status']===200,'global fixture init');
    $addresses=[];for($i=1;$i<=20;$i++){ $addresses[]='198.51.100.'.$i;$addresses[]='198.51.100.'.$i; }
    $global=batch($guard,$two,$addresses);check(counts($global)===[200=>30,429=>10],'concurrent global cap incorrect: '.json_encode(counts($global)));
    $state=json_decode(file_get_contents($two.'/state.json'),true,16,JSON_THROW_ON_ERROR);check($state['global']['contact'][1]===30,'global persisted count incorrect');
    $pipes=[];$holder=proc_open([PHP_BINARY,__FILE__,'--hold',$two.'/state.lock'],[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);fclose($pipes[0]);check(fread($pipes[1],5)==='READY','lock holder not ready');
    $start=microtime(true);$blocked=child_end(child_start($guard,$two,'api','203.0.113.1'));$elapsed=microtime(true)-$start;
    check($blocked['status']===503 && $elapsed<0.75,'lock contention did not fail closed within bound');stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);check(proc_close($holder)===0 && $err==='','lock holder failed');
    file_put_contents($two.'/state.json','{corrupt');$corrupt=child_end(child_start($guard,$two,'api','203.0.113.2'));check($corrupt['status']===503,'corrupt state not closed');
    echo json_encode(['passed'=>true,'php'=>PHP_VERSION,'private_native_creation'=>true,'concurrent_same_ip'=>counts($same),'concurrent_global'=>counts($global),'bounded_lock_contention'=>true,'corrupt_fail_closed'=>true],JSON_UNESCAPED_SLASHES)."\n";
} finally {
    // Only delete paths created by this invocation under its random private root.
    foreach(glob($root.'/*') as $dir){foreach(glob($dir.'/*') as $file)unlink($file);rmdir($dir);}rmdir($root);
}
