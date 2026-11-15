<?php
/**
 * loldex API — PHP edition (for SiteGround / any PHP host).
 *
 * Reads data.json in the same folder and serves filtered JSON. Read-only,
 * self-contained, no database. Mirrors the Cloudflare Worker version.
 *
 * Usage (query-param routing works on any host, no .htaccess needed):
 *   api.php?action=stats
 *   api.php?action=search&q=tar&os=linux&priv=sudo&cap=&phase=&type=&limit=&offset=
 *   api.php?action=entries&limit=&offset=
 *   api.php?action=entry&id=lolbas/certutil/download/0
 *
 * os shorthands: win -> windows, ad -> active-directory.
 */

require_once __DIR__.'/request-guard.php';
loldex_guard_json_headers();
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, HEAD, OPTIONS');
header('Access-Control-Expose-Headers: Retry-After');
set_error_handler(function($severity,$message,$file,$line) {
    if (error_reporting() & $severity) throw new ErrorException('Request operation failed',0,$severity);
    return true;
});

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if ($method === 'OPTIONS') { http_response_code(204); exit; }
if ($method !== 'GET' && $method !== 'HEAD') { header('Allow: GET, HEAD, OPTIONS'); http_response_code(405); echo '{"error":"method not allowed"}'; exit; }
$guard = loldex_guard_rate('api');
if (!$guard['allowed']) { header('Retry-After: '.$guard['retry_after']); http_response_code($guard['status']); if ($method !== 'HEAD') echo json_encode(array('error'=>$guard['status']===429?'too many requests':'service unavailable')); exit; }


$DATA_FILE = __DIR__ . '/data.json';
$MAX_LIMIT = 200;

function out($v, $code = 200) {
    http_response_code($code);
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') echo json_encode($v, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR);
    exit;
}

function norm_platform($v) {
    if ($v === null) return null;
    $m = array('win' => 'windows', 'ad' => 'active-directory');
    return isset($m[$v]) ? $m[$v] : $v;
}
function clamp_int($v, $def, $max = 0) {
    if ($v === null || !is_numeric($v) || (int)$v < 0) return $def;
    $n = (int)$v;
    return $max ? min($n, $max) : $n;
}
function matches($e, $p) {
    if ($p['q'] !== '') {
        $hay = strtolower($e['name'] . ' ' . $e['id'] . ' ' .
               (isset($e['aliases']) ? implode(' ', $e['aliases']) : ''));
        if (strpos($hay, strtolower($p['q'])) === false) return false;
    }
    if ($p['platform'] && $e['platform'] !== $p['platform']) return false;
    if ($p['priv'] && $e['privilege_required'] !== $p['priv']) return false;
    if ($p['cap'] && (!isset($e['capabilities']) || !in_array($p['cap'], $e['capabilities']))) return false;
    if ($p['phase'] && (!isset($e['phases']) || !in_array($p['phase'], $e['phases']))) return false;
    if ($p['type'] && $e['type'] !== $p['type']) return false;
    return true;
}

try {
    $params = loldex_guard_pairs($_SERVER['QUERY_STRING'] ?? '');
    foreach ($params as $key=>$value) {
        if (!in_array($key,array('action','q','platform','os','priv','cap','phase','type','limit','offset','id'),true) || strlen($value)>4096 || preg_match('/[\r\n\t]/',$value)) throw new InvalidArgumentException('Invalid parameters');
    }
    foreach (array('limit','offset') as $key) if (isset($params[$key]) && $params[$key] !== '' && (!preg_match('/^(0|[1-9][0-9]{0,7})$/D',$params[$key]) || (int)$params[$key]>10000000)) throw new InvalidArgumentException('Invalid pagination');
    if (!is_readable($DATA_FILE) || filesize($DATA_FILE)>67108864) out(array('error'=>'index unavailable'),502);
    $blob = json_decode(file_get_contents($DATA_FILE),true,64,JSON_THROW_ON_ERROR);
    if (!is_array($blob) || !is_array($blob['entries'] ?? null)) throw new RuntimeException('Invalid index');
    $entries = $blob['entries'];
    foreach ($entries as $entry) {
        if (!is_array($entry)) throw new RuntimeException('Invalid index');
        foreach (array('id','name','platform','privilege_required','type') as $key) if (!is_string($entry[$key] ?? null)) throw new RuntimeException('Invalid index');
        foreach (array('aliases','capabilities','phases') as $key) if (isset($entry[$key])) {
            if (!is_array($entry[$key])) throw new RuntimeException('Invalid index');
            foreach ($entry[$key] as $value) if (!is_string($value)) throw new RuntimeException('Invalid index');
        }
    }
$action = isset($params['action']) ? $params['action'] : 'root';

if ($action === 'root') {
    out(array(
        'name' => 'loldex API',
        'version' => 0,
        'endpoints' => array('?action=stats', '?action=search', '?action=entries', '?action=entry&id=<id>'),
        'count' => count($entries),
    ));
}

if ($action === 'stats') {
    $byPlatform = array(); $byCap = array(); $byPriv = array();
    foreach ($entries as $e) {
        $pl = $e['platform']; $byPlatform[$pl] = (isset($byPlatform[$pl]) ? $byPlatform[$pl] : 0) + 1;
        $pv = $e['privilege_required']; $byPriv[$pv] = (isset($byPriv[$pv]) ? $byPriv[$pv] : 0) + 1;
        if (isset($e['capabilities'])) foreach ($e['capabilities'] as $c) {
            $byCap[$c] = (isset($byCap[$c]) ? $byCap[$c] : 0) + 1;
        }
    }
    out(array('count' => count($entries), 'byPlatform' => $byPlatform,
              'byPriv' => $byPriv, 'byCapability' => $byCap));
}

if ($action === 'search' || $action === 'entries') {
    $p = array(
        'q'        => isset($params['q']) ? $params['q'] : '',
        'platform' => norm_platform(isset($params['platform']) ? $params['platform'] : (isset($params['os']) ? $params['os'] : null)),
        'priv'     => isset($params['priv']) ? $params['priv'] : null,
        'cap'      => isset($params['cap']) ? $params['cap'] : null,
        'phase'    => isset($params['phase']) ? $params['phase'] : null,
        'type'     => isset($params['type']) ? $params['type'] : null,
    );
    $limit  = clamp_int(isset($params['limit']) ? $params['limit'] : null, 50, $MAX_LIMIT);
    $offset = clamp_int(isset($params['offset']) ? $params['offset'] : null, 0);
    $hits = array();
    foreach ($entries as $e) { if (matches($e, $p)) $hits[] = $e; }
    out(array(
        'count'   => count($hits),
        'limit'   => $limit,
        'offset'  => $offset,
        'results' => array_slice($hits, $offset, $limit),
    ));
}

if ($action === 'entry') {
    $id = isset($params['id']) ? $params['id'] : '';
    foreach ($entries as $e) { if ($e['id'] === $id) out($e); }
    out(array('error' => 'not found', 'id' => $id), 404);
}

out(array('error' => 'unknown action', 'action' => $action), 404);

} catch (InvalidArgumentException $error) { out(array('error'=>'invalid parameters'),400); }
catch (Throwable $error) { out(array('error'=>'index unavailable'),502); }
