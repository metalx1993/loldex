<?php
/** Immutable release-local API v1. Legacy api.php is deliberately separate. */
require_once __DIR__ . '/api-v1-core.php';
$response=loldex_v1_handle($_SERVER['REQUEST_METHOD']??'GET',$_SERVER['QUERY_STRING']??'',__DIR__,$_SERVER['HTTP_IF_NONE_MATCH']??null,$_SERVER['REQUEST_URI']??'');
http_response_code($response['status']);
foreach ($response['headers'] as $name=>$value) header($name.': '.$value);
echo $response['body'];
