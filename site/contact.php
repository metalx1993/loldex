<?php
/**
 * loldex contact form handler.
 *
 * Receives a JSON (or form-encoded) POST from contact.html and emails it to the
 * project inbox. Self-contained: no third-party service, no API key. On
 * SiteGround, mail() delivers locally to a mailbox on the same domain, so
 * messages to contact@loldex.sh land reliably in webmail.
 *
 * If you ever want submissions somewhere else, change $TO below.
 */

header('Content-Type: application/json; charset=utf-8');

// --- config -----------------------------------------------------------------
$TO      = 'contact@loldex.sh';          // where submissions are delivered
$SUBJECT = 'New loldex contact message';
// ----------------------------------------------------------------------------

function fail($msg, $code = 400) {
    http_response_code($code);
    echo json_encode(array('success' => false, 'message' => $msg));
    exit;
}
function ok($msg) {
    echo json_encode(array('success' => true, 'message' => $msg));
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    fail('Method not allowed', 405);
}

// Accept both JSON and normal form posts.
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!is_array($data)) {
    $data = $_POST;
}

// Honeypot: bots fill hidden fields; humans leave them empty.
if (!empty($data['botcheck'])) {
    ok('Message sent.');   // silently accept-and-drop
}

$name    = isset($data['name'])    ? trim($data['name'])    : '';
$email   = isset($data['email'])   ? trim($data['email'])   : '';
$message = isset($data['message']) ? trim($data['message']) : '';

if ($name === '')  fail('Name is required.');
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) fail('A valid email is required.');
if (strlen($message) < 2) fail('Message is too short.');

// Basic hardening: strip header-injection attempts from the reply-to.
$email = str_replace(array("\r", "\n", "%0a", "%0d"), '', $email);
$name  = str_replace(array("\r", "\n"), ' ', $name);

$body  = "New message from loldex.sh contact form\n\n";
$body .= "Name:    $name\n";
$body .= "Email:   $email\n";
$body .= "-----------------------------------------\n\n";
$body .= $message . "\n";

$headers  = "From: loldex.sh <contact@loldex.sh>\r\n";
$headers .= "Reply-To: $name <$email>\r\n";
$headers .= "Content-Type: text/plain; charset=utf-8\r\n";
$headers .= "X-Mailer: loldex-contact\r\n";

$sent = @mail($TO, $SUBJECT, $body, $headers);

if ($sent) {
    ok('Message sent. Thanks — we\'ll get back to you.');
} else {
    fail('Could not send right now. Please try again later.', 500);
}
