<?php
// recording.php advertises Accept-Ranges: bytes. Before this helper existed it
// ignored Range entirely and always answered 200 with the whole mp3, which is
// what stalled <audio> on iOS Safari and broke seeking and the loop-region UI.
declare(strict_types=1);

require dirname(__DIR__) . '/avian/api/serve-media.php';

$checks = 0;
function check(bool $condition, string $message): void {
    global $checks;
    $checks++;
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
}

// Deterministic fixture: byte[i] == i % 251, so any slice is verifiable.
$size = 10000;
$data = '';
for ($i = 0; $i < $size; $i++) $data .= chr($i % 251);
$path = tempnam(sys_get_temp_dir(), 'avian-range-');
file_put_contents($path, $data);

/** @return array{0:int,1:string} status and body */
function serve(string $path, ?string $range, string $method = 'GET'): array {
    http_response_code(200);
    if ($range === null) unset($_SERVER['HTTP_RANGE']);
    else $_SERVER['HTTP_RANGE'] = $range;
    $_SERVER['REQUEST_METHOD'] = $method;
    ob_start();
    avian_serve_file_with_ranges($path, 'audio/mpeg', 60);
    return [http_response_code(), (string)ob_get_clean()];
}

[$st, $body] = serve($path, null);
check($st === 200 && $body === $data, 'no Range serves the whole file with 200');

[$st, $body] = serve($path, 'bytes=0-499');
check($st === 206 && $body === substr($data, 0, 500), 'bytes=0-499 returns the first 500 bytes');

[$st, $body] = serve($path, 'bytes=500-');
check($st === 206 && $body === substr($data, 500), 'open-ended range runs to the last byte');

[$st, $body] = serve($path, 'bytes=-500');
check($st === 206 && $body === substr($data, -500), 'suffix range returns the final bytes');

[$st, $body] = serve($path, 'bytes=9990-99999');
check($st === 206 && $body === substr($data, 9990), 'an end past EOF is clamped, not an error');

[$st, $body] = serve($path, 'bytes=0-0');
check($st === 206 && $body === substr($data, 0, 1), 'a single-byte range is honoured');

[$st, $body] = serve($path, 'bytes=' . $size . '-');
check($st === 416 && $body === '', 'a start past EOF is 416 with no body');

[$st, $body] = serve($path, 'bytes=abc');
check($st === 200 && $body === $data, 'a malformed Range falls back to the whole file');

[$st, $body] = serve($path, 'bytes=0-9,20-29');
check($st === 200 && $body === $data, 'multi-range is answered in full, which RFC 9110 permits');

[$st, $body] = serve($path, 'bytes=0-499', 'HEAD');
check($st === 206 && $body === '', 'HEAD reports the range without a body');

// Headers are invisible under the CLI SAPI, so shell out to php-cgi for those.
$cgi = trim((string)@shell_exec('command -v php-cgi 2>/dev/null'));
if ($cgi !== '' && is_executable($cgi)) {
    $driver = tempnam(sys_get_temp_dir(), 'avian-range-drv-') . '.php';
    file_put_contents($driver, "<?php require " . var_export(dirname(__DIR__) . '/avian/api/serve-media.php', true)
        . "; avian_serve_file_with_ranges(getenv('FIXTURE'), 'audio/mpeg', 60);");

    $headersFor = function (?string $range) use ($cgi, $driver, $path): string {
        $env = 'FIXTURE=' . escapeshellarg($path) . ' REQUEST_METHOD=GET REDIRECT_STATUS=1 '
            . 'SCRIPT_FILENAME=' . escapeshellarg($driver);
        if ($range !== null) $env .= ' HTTP_RANGE=' . escapeshellarg($range);
        $out = (string)shell_exec($env . ' ' . escapeshellarg($cgi) . ' -q ' . escapeshellarg($driver) . ' 2>/dev/null');
        return substr($out, 0, strpos($out, "\r\n\r\n") ?: strlen($out));
    };

    $h = $headersFor(null);
    check(stripos($h, 'Accept-Ranges: bytes') !== false, 'Accept-Ranges is advertised');
    check(stripos($h, 'Content-Length: 10000') !== false, 'full response sets the full length');

    $h = $headersFor('bytes=0-499');
    check(stripos($h, 'Content-Range: bytes 0-499/10000') !== false, 'partial sets Content-Range');
    check(stripos($h, 'Content-Length: 500') !== false, 'partial sets the slice length');

    $h = $headersFor('bytes=' . $size . '-');
    check(stripos($h, 'Content-Range: bytes */10000') !== false, '416 reports the full size');

    @unlink($driver);
} else {
    fwrite(STDERR, "note: php-cgi not found, skipping header assertions\n");
}

@unlink($path);
echo "serve-media range tests passed ({$checks} checks)\n";
