"""Explicit public-track metadata research. Never uploads or identifies audio."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import http.client
import ipaddress
import math
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode, urlsplit

from .evidence import Invalid, canonical, clean, digest, parse, regular, require
from .library import private_directory, private_write

HOST = 'musicbrainz.org'
ENDPOINT = 'https://musicbrainz.org/ws/2/recording'
USER_AGENT = 'SourSidesDJLab/1.0 ( https://github.com/IsaiahDupree/music-selector )'
MAX_RESPONSE = 256 * 1024
CACHE_LIMIT = 512 * 1024
TTL_SECONDS = 24 * 3600
REQUEST_TIMEOUT = 10
_INFLIGHT = threading.Lock()
_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/|&])')
_UUID = re.compile(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}')


def _phrase(value):
    # Escaping Lucene syntax is separate from URL percent encoding.
    return '"' + _SPECIAL.sub(r'\\\1', value) + '"'


def _binding(track):
    require(isinstance(track, dict), 'A real library track is required')
    source = track.get('source') or {}
    require(isinstance(source, dict) and isinstance(source.get('url'), str), 'A public source URL is required')
    try:
        url = urlsplit(source['url']); port = url.port
    except ValueError as exc:
        raise Invalid('Source URL is invalid') from exc
    require(source.get('kind') == 'soundcloud' and url.scheme == 'https'
            and url.hostname == 'soundcloud.com' and port in (None, 443)
            and not url.username and not url.password and not url.query and not url.fragment
            and re.fullmatch(r'/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/?', url.path),
            'External research is limited to public SoundCloud track metadata; private productions are not sent')
    require(isinstance(track.get('sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', track['sha256']),
            'A source SHA is required')
    require(track.get('id') == 'trk_' + track['sha256'][:24], 'Track identity does not match its source')
    title, artist = clean(track.get('title')), clean(track.get('artist'))
    require(0 < len(title) <= 500 and 0 < len(artist) <= 300,
            'Research needs a bounded actual title and artist')
    query = 'recording:' + _phrase(title) + ' AND artist:' + _phrase(artist)
    duration = track.get('duration_seconds')
    require(type(duration) in (int, float) and math.isfinite(duration) and 0 < duration <= 86400,
            'A measured source duration is required')
    return {'track_id': track['id'], 'source_sha256': track['sha256'], 'source_url': source['url'],
            'title': title, 'artist': artist, 'duration_seconds': duration, 'query': query}


def _url(binding):
    return ENDPOINT + '?' + urlencode({'query': binding['query'], 'fmt': 'json', 'limit': 5})


def _cache_file(binding, state_dir):
    return Path(state_dir).expanduser().absolute() / 'research' / (digest(canonical(binding)) + '.json')


def _read_private(path, maximum):
    info = regular(path)
    require(info.st_uid == os.getuid() and not info.st_mode & 0o077 and info.st_size <= maximum,
            'Research evidence must be a bounded owner-only file')
    return path.read_bytes()


def _candidates(raw, binding):
    data = parse(raw)
    require(isinstance(data, dict) and isinstance(data.get('recordings'), list),
            'MusicBrainz response did not contain a recording list')
    require(len(data['recordings']) <= 5, 'MusicBrainz exceeded the requested candidate limit')
    output = []
    for row in data['recordings']:
        require(isinstance(row, dict) and isinstance(row.get('id'), str) and _UUID.fullmatch(row['id']),
                'MusicBrainz returned an invalid recording identifier')
        require(isinstance(row.get('title'), str), 'MusicBrainz recording title is missing')
        credits = row.get('artist-credit') or []
        require(isinstance(credits, list), 'MusicBrainz artist credits are invalid')
        names = []
        for credit in credits:
            require(isinstance(credit, dict), 'MusicBrainz artist credit is invalid')
            name = credit.get('name') or (credit.get('artist') or {}).get('name')
            require(name is None or isinstance(name, str), 'MusicBrainz artist name is invalid')
            names.append((name or '') + str(credit.get('joinphrase') or ''))
        milliseconds = row.get('length')
        duration = milliseconds / 1000 if type(milliseconds) in (int, float) and math.isfinite(milliseconds) and milliseconds >= 0 else None
        output.append({'id': row['id'], 'title': clean(row['title']), 'artist': clean(''.join(names)),
                       'duration_seconds': duration,
                       'duration_delta_seconds': round(duration - binding['duration_seconds'], 3) if duration is not None else None,
                       'url': 'https://musicbrainz.org/recording/' + row['id'], 'verified_match': False})
    return output


def _result(binding, evidence, *, cached):
    require(isinstance(evidence, dict) and evidence.get('user_agent') == USER_AGENT, 'Research application binding differs')
    require(evidence.get('status') in {'ok', 'network_error', 'provider_error'}, 'Research status is invalid')
    require(type(evidence.get('response_truncated')) is bool, 'Research response completeness is invalid')
    http_status = evidence.get('http_status')
    require(http_status is None or type(http_status) is int and 100 <= http_status <= 599, 'Research HTTP status is invalid')
    raw = base64.b64decode(evidence['raw_response_base64'], validate=True)
    require(len(raw) <= MAX_RESPONSE and digest(raw) == evidence['raw_response_sha256'], 'Research raw evidence hash differs')
    require(evidence['binding'] == binding and evidence['request_url'] == _url(binding), 'Research evidence binding differs')
    received = evidence['retrieved_epoch']
    require(type(received) in (int, float) and math.isfinite(received) and 0 < received <= time.time() + 5,
            'Research retrieval time is invalid')
    require(evidence.get('retrieved_at') == datetime.fromtimestamp(received, timezone.utc).isoformat(), 'Research time binding differs')
    status, error, candidates = evidence['status'], evidence.get('error'), []
    if status == 'ok':
        try:
            require(evidence['http_status'] == 200 and not evidence['response_truncated'], 'A successful response must be complete HTTP 200')
            candidates = _candidates(raw, binding)
        except (Invalid, ValueError, TypeError, KeyError):
            status = 'invalid_provider_response'
            error = {'code': status, 'message': 'MusicBrainz returned a response that does not match the recording contract.'}
    plain = binding['title'] + ' ' + binding['artist']
    return {'contract': 'djlab_public_recording_research_v1', 'provider': 'MusicBrainz',
            'status': status, 'binding': binding, 'request_url': evidence['request_url'],
            'http_status': evidence['http_status'], 'retrieved_at': evidence['retrieved_at'],
            'expires_at': datetime.fromtimestamp(received + TTL_SECONDS, timezone.utc).isoformat(),
            'cached': cached, 'cache_age_seconds': max(0, round(time.time() - received, 3)),
            'audio_uploaded': False, 'verified_match': False, 'candidates': candidates, 'error': error,
            'raw_response_sha256': digest(raw), 'raw_response_bytes': len(raw),
            'response_truncated': evidence['response_truncated'], 'content_type': evidence.get('content_type'),
            'query_fields_sent': ['title', 'artist'], 'limit': 5,
            'search_links': [
                {'label': 'Search MusicBrainz manually', 'url': 'https://musicbrainz.org/search?' + urlencode({'query': binding['query'], 'type': 'recording', 'method': 'advanced'}), 'verified_results': False},
                {'label': 'Search SoundCloud manually', 'url': 'https://soundcloud.com/search/sounds?' + urlencode({'q': plain}), 'verified_results': False}],
            'note': 'Candidates and constructed search links are research leads, not audio identification or verified matches.'}


def cached_research(track: dict, state_dir: Path) -> dict | None:
    """Read valid, fresh evidence only. Never creates state or makes a request."""
    binding = _binding(track)
    path = _cache_file(binding, state_dir)
    if not path.exists():
        return None
    evidence = parse(_read_private(path, CACHE_LIMIT))
    result = _result(binding, evidence, cached=True)
    if time.time() - evidence['retrieved_epoch'] >= TTL_SECONDS:
        return None
    return result


@contextmanager
def _provider_lock(state_dir):
    require(_INFLIGHT.acquire(blocking=False), 'A MusicBrainz request is already in flight; try again after it completes')
    fd = None
    try:
        home = private_directory(Path(state_dir) / 'research')
        fd = os.open(home / 'provider.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Invalid('A MusicBrainz request is already in flight in this library') from exc
        yield home
    finally:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
        _INFLIGHT.release()


def _public_addresses():
    addresses = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
    require(addresses and len(addresses) <= 32, 'Provider DNS has no bounded address set')
    for _, _, _, _, address in addresses:
        require(ipaddress.ip_address(address[0]).is_global, 'Provider resolved to a non-public address')
    return addresses


class _PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to an already validated address, with TLS still verifying HOST."""
    def connect(self):
        addresses = _public_addresses()
        family, kind, protocol, _, address = addresses[0]
        raw = socket.socket(family, kind, protocol)
        raw.settimeout(REQUEST_TIMEOUT)
        try:
            raw.connect(address)
            self.sock = self._context.wrap_socket(raw, server_hostname=HOST)
        except BaseException:
            raw.close(); raise


def _provider_worker(query):
    # The caller supervises this one lightweight network process for ten seconds,
    # including DNS. No daemon, retry, proxy, redirect, or media processing.
    require(isinstance(query, str) and len(query) <= 1800, 'Bounded query required')
    connection = _PinnedHTTPS(HOST, 443, timeout=REQUEST_TIMEOUT, context=ssl.create_default_context())
    try:
        path = '/ws/2/recording?' + urlencode({'query': query, 'fmt': 'json', 'limit': 5})
        connection.request('GET', path, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        truncated = len(raw) > MAX_RESPONSE
        raw = raw[:MAX_RESPONSE]
        return {'http_status': response.status, 'content_type': response.getheader('Content-Type', '')[:120],
                'raw_response_base64': base64.b64encode(raw).decode(), 'response_truncated': truncated,
                'retry_after': response.getheader('Retry-After', '')[:100]}
    finally:
        connection.close()


def _fetch(query):
    command = [sys.executable, '-m', 'djlab.research', '--provider-worker']
    try:
        process = subprocess.run(command, input=canonical({'query': query}), stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=REQUEST_TIMEOUT,
                                 cwd=Path(__file__).resolve().parent.parent, check=False)
    except subprocess.TimeoutExpired:
        return {'status': 'network_error', 'http_status': None, 'raw_response_base64': '', 'response_truncated': False,
                'error': {'code': 'timeout', 'message': 'MusicBrainz lookup exceeded ten seconds; no retry was made.'}}
    if process.returncode or len(process.stdout) > CACHE_LIMIT:
        return {'status': 'network_error', 'http_status': None, 'raw_response_base64': '', 'response_truncated': False,
                'error': {'code': 'network_failure', 'message': 'The MusicBrainz connection failed; no retry or fallback request was made.'}}
    value = parse(process.stdout)
    status = value['http_status']
    value['status'] = 'ok' if status == 200 and not value['response_truncated'] else 'provider_error'
    if value['status'] != 'ok':
        code = 'response_too_large' if value['response_truncated'] else ('redirect_rejected' if 300 <= status < 400 else 'http_error')
        value['error'] = {'code': code, 'message': f'MusicBrainz returned HTTP {status}' + (' with a response over 256 KiB.' if value['response_truncated'] else '; no redirect or retry was followed.')}
    return value


def research_track(track: dict, state_dir: Path, *, refresh: bool = False) -> dict:
    """One explicit public-title/artist lookup, or its fresh source-bound cache."""
    require(type(refresh) is bool, 'Refresh must be a Boolean')
    binding = _binding(track)
    if not refresh:
        prior = cached_research(track, state_dir)
        if prior is not None:
            return prior
    with _provider_lock(state_dir) as home:
        # Recheck after acquiring the process lock; another caller may have just
        # populated the same cache. Explicit refresh remains one new request.
        if not refresh:
            prior = cached_research(track, state_dir)
            if prior is not None:
                return prior
        rate_path = home / 'provider-rate.json'
        if rate_path.exists():
            previous = parse(_read_private(rate_path, 1024))
            next_epoch = previous.get('next_request_epoch')
            require(type(next_epoch) in (int, float) and math.isfinite(next_epoch), 'Provider rate time is invalid')
            wait = next_epoch - time.time()
            require(wait <= 1.1, 'Provider rate state is in the future; check the clock before retrying')
            if wait > 0:
                time.sleep(wait)
        private_write(rate_path, canonical({'next_request_epoch': time.time() + 1.0}))
        response = _fetch(binding['query'])
        # Space the next request from completion as well as attempt start, so
        # child startup and DNS variability cannot compress provider requests.
        private_write(rate_path, canonical({'next_request_epoch': time.time() + 1.0}))
        received = time.time()
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        evidence = {**response, 'binding': binding, 'request_url': _url(binding), 'user_agent': USER_AGENT,
                    'retrieved_epoch': received, 'retrieved_at': datetime.fromtimestamp(received, timezone.utc).isoformat(),
                    'raw_response_sha256': digest(raw)}
        private_write(_cache_file(binding, state_dir), canonical(evidence))
        return _result(binding, evidence, cached=False)


if __name__ == '__main__':
    # Fixed internal entry used only by _fetch. It accepts no endpoint argument.
    try:
        require(sys.argv[1:] == ['--provider-worker'], 'Internal provider worker only')
        payload = parse(sys.stdin.buffer.read(4097))
        require(isinstance(payload, dict) and set(payload) == {'query'}, 'One query required')
        sys.stdout.buffer.write(canonical(_provider_worker(payload['query'])))
    except Exception:
        # No query, raw provider body, URL capabilities, or exception text logged.
        raise SystemExit(2)
