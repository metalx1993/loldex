<?php
/** Contact endpoint: bounded scalar fields, fixed mail headers, private quotas. */
require_once __DIR__.'/request-guard.php';
function loldex_contact_payload($raw, $contentType) {
    if (!is_string($raw) || strlen($raw) > 16384) throw new LengthException('Request too large.');
    $type = strtolower(trim(explode(';', $contentType)[0]));
    if ($type === 'application/json') $fields = loldex_guard_json_fields($raw);
    elseif ($type === 'application/x-www-form-urlencoded') $fields = loldex_guard_pairs($raw,16384,4);
    else throw new UnexpectedValueException('Unsupported content type.');
    $limits = array('name'=>120,'email'=>254,'message'=>8000,'botcheck'=>200);
    foreach ($fields as $key=>$value) {
        if (!isset($limits[$key]) || !loldex_guard_text($value,$limits[$key])) throw new InvalidArgumentException('Invalid contact fields.');
    }
    $data = array(); foreach ($limits as $key=>$max) $data[$key] = trim($fields[$key] ?? '');
    if ($data['botcheck'] !== '') return $data;
    if ($data['name'] === '' || preg_match('/[\r\n]/',$data['name'])) throw new InvalidArgumentException('A valid name is required.');
    if (!filter_var($data['email'],FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/',$data['email'])) throw new InvalidArgumentException('A valid email is required.');
    if (strlen($data['message']) < 2) throw new InvalidArgumentException('Message is too short.');
    return $data;
}
function loldex_contact_mail_parts($data) {
    $body = "New message from loldex.sh contact form\n\nName:    ".$data['name']."\nEmail:   ".$data['email']."\n-----------------------------------------\n\n".$data['message']."\n";
    $headers = "From: loldex.sh <contact@loldex.sh>\r\nReply-To: ".$data['email']."\r\nContent-Type: text/plain; charset=utf-8\r\nX-Mailer: loldex-contact\r\n";
    return array($body,$headers);
}
function loldex_contact_respond($message,$code,$success=false,$head=false) {
    http_response_code($code);
    if (!$head) echo json_encode(array('success'=>$success,'message'=>$message),JSON_UNESCAPED_SLASHES);
}
if (!defined('LOLDEX_CONTACT_LIBRARY')) {
    set_error_handler(function($severity,$message,$file,$line) {
        if (error_reporting() & $severity) throw new ErrorException('Request operation failed',0,$severity);
        return true;
    });
    loldex_guard_json_headers();
    header('Content-Type: application/json; charset=utf-8'); header('Cache-Control: no-store'); header('X-Content-Type-Options: nosniff');
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    if ($method !== 'POST') {
        header('Allow: POST'); loldex_contact_respond('Method not allowed.',405,false,$method==='HEAD');
    } else {
        try {
            $length = $_SERVER['CONTENT_LENGTH'] ?? null;
            if ($length !== null && (!is_string($length) || !preg_match('/^[0-9]{1,8}$/D',$length))) throw new InvalidArgumentException('Invalid request.');
            if ($length !== null && (int)$length > 16384) throw new LengthException('Request too large.');
            $raw = file_get_contents('php://input',false,null,0,16385);
            if (!is_string($raw) || ($length !== null && strlen($raw) !== (int)$length)) throw new InvalidArgumentException('Invalid request.');
            $data = loldex_contact_payload($raw,$_SERVER['CONTENT_TYPE'] ?? '');
            // Admission is persisted before any mail side effect. Honeypot requests
            // consume the same budget and can never send mail.
            $guard = loldex_guard_rate('contact',true);
            if (!$guard['allowed']) {
                header('Retry-After: '.$guard['retry_after']);
                loldex_contact_respond($guard['status']===429 ? 'Too many requests. Please try again later.' : 'Could not send right now. Please try again later.',$guard['status']);
            } elseif ($data['botcheck'] !== '') loldex_contact_respond('Message sent.',200,true);
            else {
                list($body,$headers) = loldex_contact_mail_parts($data);
                $sent = @mail('contact@loldex.sh','New loldex contact message',$body,$headers);
                loldex_contact_respond($sent ? "Message sent. Thanks — we'll get back to you." : 'Could not send right now. Please try again later.',$sent ? 200 : 503,$sent);
            }
        } catch (LengthException $error) { loldex_contact_respond('Request too large.',413); }
        catch (UnexpectedValueException $error) { loldex_contact_respond('Unsupported content type.',415); }
        catch (InvalidArgumentException | JsonException $error) { loldex_contact_respond('Invalid contact fields.',400); }
        catch (Throwable $error) { loldex_contact_respond('Could not send right now. Please try again later.',503); }
    }
}
