<?php
/** Shared bounded request parsing and private, lock-serialized abuse budgets. */
function loldex_guard_json_headers() {
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
}
function loldex_guard_text($value, $max) {
    return is_string($value) && strlen($value) <= $max && preg_match('//u', $value) === 1
        && preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/', $value) !== 1;
}
function loldex_guard_pairs($raw, $maxBytes = 16384, $maxFields = 16) {
    if (!is_string($raw) || strlen($raw) > $maxBytes) throw new InvalidArgumentException('Invalid parameters');
    if ($raw === '') return array();
    $parts = explode('&', $raw);
    if (count($parts) > $maxFields) throw new InvalidArgumentException('Invalid parameters');
    $result = array();
    foreach ($parts as $part) {
        if ($part === '' || preg_match('/%(?![a-fA-F0-9]{2})/', $part)) throw new InvalidArgumentException('Invalid parameters');
        $pair = explode('=', $part, 2); $key = urldecode($pair[0]); $value = urldecode($pair[1] ?? '');
        if (!preg_match('/^[a-z][a-z0-9_]*$/D', $key) || array_key_exists($key, $result) || !loldex_guard_text($value, 8192)) throw new InvalidArgumentException('Invalid parameters');
        $result[$key] = $value;
    }
    return $result;
}
function loldex_guard_json_fields($raw) {
    $decoded = json_decode($raw, false, 8, JSON_THROW_ON_ERROR);
    if (!is_object($decoded)) throw new InvalidArgumentException('Invalid fields');
    // Parse the small string-only object a second time so repeated decoded keys
    // cannot disappear through json_decode's last-value-wins behavior.
    $offset = 0; $length = strlen($raw); $fields = array();
    if (!preg_match('/\A\s*\{\s*/', $raw, $start)) throw new InvalidArgumentException('Invalid fields');
    $offset = strlen($start[0]);
    if (preg_match('/\G\}\s*\z/A', $raw, $empty, 0, $offset)) return $fields;
    $token = '"(?:[^"\\\\]|\\\\.)*"';
    $pattern = '/\G\s*('.$token.')\s*:\s*('.$token.')\s*([,}])/As';
    while ($offset < $length && preg_match($pattern, $raw, $match, 0, $offset)) {
        $key = json_decode($match[1], true, 8, JSON_THROW_ON_ERROR);
        $value = json_decode($match[2], true, 8, JSON_THROW_ON_ERROR);
        if (array_key_exists($key, $fields) || count($fields) >= 4) throw new InvalidArgumentException('Invalid fields');
        $fields[$key] = $value; $offset += strlen($match[0]);
        if ($match[3] === '}') {
            if (trim(substr($raw, $offset)) !== '') throw new InvalidArgumentException('Invalid fields');
            return $fields;
        }
    }
    throw new InvalidArgumentException('Invalid fields');
}
function loldex_guard_directory() {
    $explicit = getenv('LOLDEX_RATE_LIMIT_DIR');
    if ($explicit !== false && $explicit !== '') return $explicit;
    $base = __DIR__;
    if (preg_match('/^r-[a-f0-9]{64}$/D', basename($base)) && basename(dirname($base)) === 'releases' && basename(dirname($base, 2)) === 'public_html') {
        return dirname($base, 3).'/loldex-control/rate-limits';
    }
    return null;
}
function loldex_guard_rate($scope, $required = false) {
    $failure = array('allowed'=>false, 'status'=>503, 'retry_after'=>60);
    $directory = loldex_guard_directory();
    if ($directory === null) return $required ? $failure : array('allowed'=>true, 'status'=>200, 'retry_after'=>0, 'configured'=>false);
    $policies = array('api'=>array(60,120,3000), 'contact'=>array(900,3,30));
    if (!isset($policies[$scope])) return $failure;
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    if (!is_string($ip) || filter_var($ip, FILTER_VALIDATE_IP) === false) return $failure;
    $lock = null;
    try {
        if ($directory === '' || $directory[0] !== '/' || strpos($directory, "\0") !== false) return $failure;
        // No symlinks in the configured path; keep state outside all served files.
        $walk = '';
        foreach (explode('/', trim($directory, '/')) as $part) {
            if ($part === '' || $part === '.' || $part === '..') return $failure;
            $walk .= '/'.$part;
            if (is_link($walk)) return $failure;
        }
        $site = realpath(__DIR__);
        $docValue = $_SERVER['DOCUMENT_ROOT'] ?? null;
        $document = is_string($docValue) && $docValue !== '' && $docValue[0] === '/' ? realpath($docValue) : false;
        $releasePublic = basename(dirname(__DIR__)) === 'releases' && basename(dirname(__DIR__,2)) === 'public_html' ? realpath(dirname(__DIR__,2)) : false;
        foreach (array($site, $document, $releasePublic) as $public) if ($public && (rtrim($directory,'/') === $public || strncmp($directory, $public.'/', strlen($public)+1) === 0)) return $failure;
        if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) return $failure;
        $real = realpath($directory);
        if (!$real || (@fileperms($real) & 0077) !== 0) return $failure;
        $stateFile = $real.'/state.json'; $keyFile = $real.'/key'; $lockFile=$real.'/state.lock'; $nextFile=$real.'/state.next';
        if (is_link($lockFile) || (file_exists($lockFile) && (!is_file($lockFile) || (@fileperms($lockFile)&0077)!==0 || (@lstat($lockFile)['nlink']??0)!==1))) return $failure;
        $oldMask = umask(0077);
        try { $newLock = !file_exists($lockFile); $lock = @fopen($lockFile, $newLock ? 'x+b' : 'c+b'); if (!$lock && $newLock && !is_link($lockFile)) { $newLock=false; $lock=@fopen($lockFile,'c+b'); } if ($lock && $newLock && !@chmod($lockFile,0600)) { fclose($lock); $lock=null; } } finally { umask($oldMask); }
        if (!$lock) return $failure;
        $deadline = microtime(true)+0.25;
        while (!@flock($lock, LOCK_EX|LOCK_NB)) { if (microtime(true)>=$deadline) return $failure; usleep(1000); }
        clearstatcache();
        foreach (array($stateFile, $keyFile, $nextFile) as $file) {
            if (is_link($file) || (file_exists($file) && (!is_file($file) || (@fileperms($file) & 0077) !== 0 || (@lstat($file)['nlink'] ?? 0) !== 1))) return $failure;
        }

        $stat = @fstat($lock);
        if (!$stat || $stat['size'] > 262144 || ($stat['mode'] & 0077) !== 0 || $stat['nlink'] !== 1) return $failure;
        if (!file_exists($keyFile)) {
            $oldMask = umask(0077);
            try { $keyHandle = @fopen($keyFile, 'x+b'); } finally { umask($oldMask); }
            if (!$keyHandle) return $failure;
            if (!@chmod($keyFile,0600)) { fclose($keyHandle); return $failure; }
            $secret = random_bytes(32);
            $written = @fwrite($keyHandle, $secret); $flushed = @fflush($keyHandle); fclose($keyHandle);
            if ($written !== 32 || !$flushed) return $failure;
        }
        $secret = @file_get_contents($keyFile, false, null, 0, 33);
        if (!is_string($secret) || strlen($secret) !== 32) return $failure;
        if (file_exists($stateFile) && @filesize($stateFile)>262144) return $failure;
        $raw = file_exists($stateFile) ? @file_get_contents($stateFile,false,null,0,262145) : '';
        if (!is_string($raw)) return $failure;
        $state = $raw === '' ? array('version'=>1,'clients'=>array(),'global'=>array()) : json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
        if (!is_array($state) || ($state['version'] ?? null) !== 1 || !is_array($state['clients'] ?? null) || !is_array($state['global'] ?? null) || count($state['clients']) > 1024 || count($state['global']) > 2) return $failure;
        $now = time();
        foreach ($state['clients'] as $id => $bucket) {
            if (!preg_match('/^(api|contact):[a-f0-9]{64}$/D', $id) || !is_array($bucket) || count($bucket) !== 2 || !is_int($bucket[0] ?? null) || !is_int($bucket[1] ?? null) || $bucket[0] > $now || $bucket[1] < 1 || $bucket[1] > 3000) return $failure;
            $age = strncmp($id, 'contact:', 8) === 0 ? 900 : 60;
            if ($now - $bucket[0] >= $age) unset($state['clients'][$id]);
        }
        foreach ($state['global'] as $id=>$bucket) {
            if (!isset($policies[$id]) || !is_array($bucket) || count($bucket) !== 2 || !is_int($bucket[0] ?? null) || !is_int($bucket[1] ?? null) || $bucket[0] > $now || $bucket[1] < 1 || $bucket[1] > 3000) return $failure;
            if ($now-$bucket[0] >= ($id === 'contact' ? 3600 : 60)) unset($state['global'][$id]);
        }
        list($window,$limit,$globalLimit) = $policies[$scope];
        $client = $scope.':'.hash_hmac('sha256', inet_pton($ip), $secret);
        $bucket = $state['clients'][$client] ?? array($now,0);
        $global = $state['global'][$scope] ?? array($now,0); $globalWindow = $scope === 'contact' ? 3600 : 60;
        if ($bucket[1] >= $limit || $global[1] >= $globalLimit || (!isset($state['clients'][$client]) && count($state['clients']) >= 1024)) {
            return array('allowed'=>false,'status'=>429,'retry_after'=>max(1, $bucket[1] >= $limit ? $window-($now-$bucket[0]) : ($global[1] >= $globalLimit ? $globalWindow-($now-$global[0]) : 60)));
        }
        $state['clients'][$client] = array($bucket[0],$bucket[1]+1);
        $state['global'][$scope] = array($global[0],$global[1]+1);
        $encoded = json_encode($state, JSON_THROW_ON_ERROR);
        if (strlen($encoded)>262144) return $failure;
        // Keep the previous counters intact if a worker dies during persistence.
        // A stable separate lock inode serializes atomic state replacements.
        if (file_exists($nextFile) && !@unlink($nextFile)) return $failure;
        $oldMask=umask(0077);
        try { $next=@fopen($nextFile,'x+b'); } finally { umask($oldMask); }
        if (!$next) return $failure;
        if (!@chmod($nextFile,0600)) { fclose($next); return $failure; }
        $written=@fwrite($next,$encoded); $flushed=@fflush($next);
        if ($flushed && function_exists('fsync')) $flushed=@fsync($next);
        fclose($next);
        if ($written!==strlen($encoded) || !$flushed || !@rename($nextFile,$stateFile)) return $failure;
        return array('allowed'=>true,'status'=>200,'retry_after'=>0,'configured'=>true);
    } catch (Throwable $error) { return $failure; }
    finally { if (is_resource($lock)) { @flock($lock,LOCK_UN); fclose($lock); } }
}
