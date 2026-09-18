<?php
// Shared media serving that honours HTTP Range.
//
// We advertise Accept-Ranges, so we have to mean it. Safari (iOS especially)
// opens <audio> with a Range request and treats a 200-with-full-body reply as
// a broken stream; that is why some recordings never played on a phone.
// Seeking and the modal loop-region UI both set currentTime, which is a range
// request too, so without this they silently refetch or stall.
//
// Lives in its own file so it can be exercised without the educator scope
// machinery that recording.php pulls in at load time.

declare(strict_types=1);

if (!function_exists('avian_serve_file_with_ranges')) {

function avian_serve_file_with_ranges(string $path, string $contentType, int $maxAge): void
{
    $size = filesize($path);
    $mtime = filemtime($path);
    $etag = '"' . md5($path . '|' . $size . '|' . $mtime) . '"';

    header('Content-Type: ' . $contentType);
    header('Accept-Ranges: bytes');
    header('Cache-Control: public, max-age=' . $maxAge);
    header('ETag: ' . $etag);
    header('Last-Modified: ' . gmdate('D, d M Y H:i:s', $mtime) . ' GMT');

    $start = 0;
    $end = $size - 1;
    $partial = false;
    $range = trim((string)($_SERVER['HTTP_RANGE'] ?? ''));

    // A conditional range whose validator no longer matches must be answered
    // with the whole entity, not a slice of a file the client has not seen.
    $ifRange = trim((string)($_SERVER['HTTP_IF_RANGE'] ?? ''));
    if ($ifRange !== '' && $ifRange !== $etag) {
        $range = '';
    }

    // Single byte range only. A multi-range request is answered in full, which
    // RFC 9110 permits and every browser handles.
    if ($range !== '' && preg_match('/^bytes=(\d*)-(\d*)$/', $range, $m)
        && ($m[1] !== '' || $m[2] !== '')) {
        if ($m[1] === '') {
            // bytes=-N : the final N bytes.
            $len = (int)$m[2];
            if ($len > 0) {
                $start = max(0, $size - $len);
                $partial = true;
            }
        } else {
            $start = (int)$m[1];
            if ($m[2] !== '') {
                $end = min((int)$m[2], $size - 1);
            }
            $partial = true;
        }

        if ($partial && ($start > $end || $start >= $size)) {
            http_response_code(416);
            header('Content-Range: bytes */' . $size);
            header('Content-Length: 0');
            return;
        }
    }

    $length = $end - $start + 1;
    if ($partial) {
        http_response_code(206);
        header("Content-Range: bytes $start-$end/$size");
    }
    header('Content-Length: ' . $length);

    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'HEAD') {
        return;
    }

    $fh = fopen($path, 'rb');
    if ($fh === false) {
        http_response_code(500);
        return;
    }
    if ($start > 0) {
        fseek($fh, $start);
    }
    // 64 KiB chunks: bounded memory on a Pi even for a long recording.
    $remaining = $length;
    while ($remaining > 0 && !feof($fh)) {
        $chunk = fread($fh, (int)min(65536, $remaining));
        if ($chunk === false || $chunk === '') {
            break;
        }
        echo $chunk;
        $remaining -= strlen($chunk);
        if (connection_aborted()) {
            break;
        }
    }
    fclose($fh);
}

}
