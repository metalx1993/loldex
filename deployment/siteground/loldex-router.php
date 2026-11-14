<?php
/** Stable SiteGround entrypoint. No uploads, shell execution or credentials.
 * Install alongside public_html/.htaccess only after the first verified release.
 * The private control directory must be a sibling of public_html.
 */
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');
function unavailable() {
    http_response_code(503);
    header('Retry-After: 60');
    echo 'The index is temporarily unavailable. Please try again shortly.';
    exit;
}
$raw = @file_get_contents(dirname(__DIR__) . '/loldex-control/active.json');
if ($raw === false) unavailable();
$state = json_decode($raw, true);
if (!is_array($state)) unavailable();
$keys = array_keys($state); sort($keys);
if ($keys !== array('commit', 'generation', 'previous_release_id', 'release_id', 'version')) unavailable();
if ($state['version'] !== 1 || !is_int($state['generation']) || $state['generation'] < 1) unavailable();
if ($state['generation'] > 9007199254740991) unavailable();
if (!is_string($state['release_id']) || !preg_match('/\Ar-[0-9a-f]{64}\z/', $state['release_id'])) unavailable();
if (!is_string($state['commit']) || !preg_match('/\A[0-9a-f]{40}\z/', $state['commit'])) unavailable();
if ($state['previous_release_id'] !== null && (!is_string($state['previous_release_id']) ||
    !preg_match('/\Ar-[0-9a-f]{64}\z/', $state['previous_release_id']))) unavailable();
// Exact canonical bytes reject duplicates, trailing data and alternate encodings.
$canonical = json_encode(array('commit' => $state['commit'], 'generation' => $state['generation'],
    'previous_release_id' => $state['previous_release_id'], 'release_id' => $state['release_id'], 'version' => 1),
    JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
if ($canonical !== $raw) unavailable();
$release = $state['release_id'];
$folder = __DIR__ . '/releases/' . $release;
if (is_link($folder) || !is_dir($folder)) unavailable();
$manifest = json_decode(@file_get_contents($folder . '/release.json'), true);
if (!is_array($manifest) || !isset($manifest['release_id'], $manifest['commit']) ||
    $manifest['release_id'] !== $release || $manifest['commit'] !== $state['commit']) unavailable();
$uri = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/';
$parts = explode('?', $uri, 2);
$path = ltrim($parts[0], '/');
if ($path === '') $path = 'index.html';
$segments = explode('/', $path);
$encoded = array();
foreach ($segments as $segment) {
    $value = rawurldecode($segment);
    if ($value === '' || $value === '.' || $value === '..' || $value[0] === '.' ||
        preg_match('/[\x00-\x20\x7f\\\\\/]/', $value)) {
        http_response_code(400); echo 'Invalid path.'; exit;
    }
    $encoded[] = rawurlencode($value);
}
$query = isset($parts[1]) ? '?' . $parts[1] : '';
if (preg_match('/[\r\n]/', $query)) { http_response_code(400); exit; }
// Public read-only API redirects need CORS too. Preflight cannot redirect.
$isPublicApi = $path === 'api-v1.php' || $path === 'api/v1' || strpos($path, 'api/v1/') === 0;
if ($isPublicApi) {
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: GET, HEAD, OPTIONS');
    header('Access-Control-Allow-Headers: If-None-Match, Content-Type');
    header('Access-Control-Expose-Headers: ETag, X-LOLDEX-Dataset');
    if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
        http_response_code(204); exit;
    }
}
// A visible version prefix binds all relative requests to this retained release.
// 307 preserves POST (contact) and query strings. No permanent redirect caching.
header('Location: /releases/' . $release . '/' . implode('/', $encoded) . $query, true, 307);
exit;
