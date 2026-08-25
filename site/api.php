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

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$DATA_FILE = __DIR__ . '/data.json';
$MAX_LIMIT = 200;

function out($v, $code = 200) {
    http_response_code($code);
    echo json_encode($v, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    exit;
}

if (!is_readable($DATA_FILE)) {
    out(array('error' => 'index unavailable'), 502);
}
$blob = json_decode(file_get_contents($DATA_FILE), true);
$entries = isset($blob['entries']) ? $blob['entries'] : array();

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

$action = isset($_GET['action']) ? $_GET['action'] : 'root';

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
        'q'        => isset($_GET['q']) ? $_GET['q'] : '',
        'platform' => norm_platform(isset($_GET['platform']) ? $_GET['platform'] : (isset($_GET['os']) ? $_GET['os'] : null)),
        'priv'     => isset($_GET['priv']) ? $_GET['priv'] : null,
        'cap'      => isset($_GET['cap']) ? $_GET['cap'] : null,
        'phase'    => isset($_GET['phase']) ? $_GET['phase'] : null,
        'type'     => isset($_GET['type']) ? $_GET['type'] : null,
    );
    $limit  = clamp_int(isset($_GET['limit']) ? $_GET['limit'] : null, 50, $MAX_LIMIT);
    $offset = clamp_int(isset($_GET['offset']) ? $_GET['offset'] : null, 0);
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
    $id = isset($_GET['id']) ? $_GET['id'] : '';
    foreach ($entries as $e) { if ($e['id'] === $id) out($e); }
    out(array('error' => 'not found', 'id' => $id), 404);
}

out(array('error' => 'unknown action', 'action' => $action), 404);
