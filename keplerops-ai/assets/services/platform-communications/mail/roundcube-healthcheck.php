<?php

$socket = @fsockopen('127.0.0.1', 8000, $errorCode, $errorMessage, 2.0);
if ($socket === false) {
    fwrite(STDERR, "Roundcube HTTP listener is unavailable: {$errorCode} {$errorMessage}\n");
    exit(1);
}
fwrite($socket, "GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n");
$status = fgets($socket);
fclose($socket);
if ($status === false || !preg_match('/^HTTP\/1\.[01] [23]\d{2}/', $status)) {
    fwrite(STDERR, "Roundcube returned an unhealthy HTTP status\n");
    exit(1);
}
