"""Bounded loopback HTTP; no DSP or arbitrary file API. Research is explicit."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .evidence import Invalid, canonical, finite, parse, regular, require
from .library import private_directory, private_write, track_summary

MAX_BODY = 65536
STATIC = Path(__file__).parent / 'static'


def capabilities(library=None):
    imported = []
    if library is not None:
        with library.locked(): library.reload(); imported = library.analysis_imports
    measured = {t['track_id'] for item in imported for t in item['tracks']}
    return {'browse': True, 'manual_edits': True, 'playback': True,
            'exports': ['json','csv','m3u8','xspf','rekordbox'],
            'plans': {'supported': True, 'execution': False},
            'fresh_analysis': {'supported': False, 'available': False,
                               'reason': 'The saved v1 evidence is available. A verified live Orion v2 adapter has not been connected.'},
            'audio_render': {'supported': False, 'available': False,
                             'reason': 'Set plans are metadata only; no currently connected typed Orion render capability.'},
            'waveform': {'available': bool(measured), 'measured_track_count':len(measured),
                         'reason': 'Actual imported Orion measurements only; inspect coverage in track detail.' if measured else 'No individual-track waveform in the imported v1 receipts.'},
            'analysis_import': {'supported':True, 'owner_cli_only':True, 'verified_job_count':len(imported)},
            'research': {'supported':True, 'provider':'MusicBrainz', 'explicit_post_only':True,
                         'public_soundcloud_only':True, 'audio_uploaded':False},
            'limits': {'body_bytes': MAX_BODY, 'hotcue_slots': 8},
            'analysis_disclaimer': 'Heuristic key and tempo estimates, not calibrated probabilities or verified downbeats.'}


def secret_file(path):
    info = regular(path)
    require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0 and info.st_size < 4096,
            'Private credential permissions are unsafe')
    return Path(path).read_text().strip()


def prepare_launch(state_dir, port):
    state = private_directory(state_dir)
    require(type(port) is int and 1024 <= port <= 65535, 'Use a non-privileged loopback port')
    origin = f'http://127.0.0.1:{port}'
    nonce = secrets.token_urlsafe(32)
    private_write(state/'launch-nonce.json', canonical({'nonce':nonce,'origin':origin,'expires_at':time.time()+600}))
    markup = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Open DJ Lab</title>'
              '<meta name="referrer" content="no-referrer"><h1>Open your local DJ Lab</h1>'
              '<p>This private sign-in link expires in ten minutes and works once.</p>'
              f'<form method="post" action="{origin}/session"><input type="hidden" name="nonce" value="{html.escape(nonce)}">'
              '<button type="submit">Open DJ Lab</button></form></html>')
    private_write(state/'launch.html', markup.encode())
    return state/'launch.html'


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Permit an orderly restart while this endpoint's closed connections remain
    # in TIME_WAIT. This is not SO_REUSEPORT and cannot share a live listener.
    allow_reuse_address = True
    request_queue_size = 8

    def __init__(self, library, port=5572):
        self.library = library
        self.state = library.state
        keyfile=self.state/'auth-key'
        if not keyfile.exists():private_write(keyfile,(secrets.token_urlsafe(48)+'\n').encode())
        self.key=secret_file(keyfile)
        require(len(self.key)>=32,'Authentication key is invalid')
        self.sessions={};self.auth_lock=threading.Lock();self.slots=threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1',port),Handler)
        self.origin=f'http://127.0.0.1:{self.server_port}'
        self.host=f'127.0.0.1:{self.server_port}'

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise

    def process_request_thread(self, request, address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()


class HTTPError(Exception):
    def __init__(self,status,code,message):self.status,self.code,self.message=status,code,message


class Handler(BaseHTTPRequestHandler):
    server_version='DJLab/1'
    sys_version=''
    protocol_version='HTTP/1.1'

    def setup(self):
        super().setup();self.connection.settimeout(15)

    def log_message(self, *_):
        # Do not log request headers, nonce forms, cookie values or query strings.
        pass

    def response(self,status,body=b'',mime='application/json; charset=utf-8',headers=None):
        self.send_response(status)
        self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD' and body:self.wfile.write(body)

    def json(self,status,payload,headers=None):self.response(status,canonical(payload),headers=headers)

    def body(self,form=False):
        if self.headers.get('Transfer-Encoding'):raise HTTPError(400,'transfer_encoding','Chunked request bodies are not accepted')
        sizes=self.headers.get_all('Content-Length') or []
        if len(sizes)!=1 or not re.fullmatch(r'\d+',sizes[0]):raise HTTPError(411,'length_required','One Content-Length is required')
        size=int(sizes[0])
        if size>MAX_BODY:raise HTTPError(413,'body_too_large','Request body is too large')
        mime=self.headers.get('Content-Type','').split(';')[0].strip().lower()
        if mime!=('application/x-www-form-urlencoded' if form else 'application/json'):
            raise HTTPError(415,'content_type','Unexpected request content type')
        raw=self.rfile.read(size)
        if len(raw)!=size:raise HTTPError(400,'incomplete_body','Incomplete request body')
        return parse_qs(raw.decode(),strict_parsing=True,max_num_fields=2) if form else parse(raw)

    def auth(self,write=False):
        origin=self.headers.get('Origin')
        if origin is not None and origin!=self.server.origin:raise HTTPError(403,'origin','Cross-origin API requests are not accepted')
        authorization=self.headers.get('Authorization','')
        if authorization.startswith('Bearer ') and hmac.compare_digest(authorization[7:],self.server.key):return None
        try:
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie.get('djlab_session')
            token=token.value if token else ''
        except Exception:token=''
        with self.server.auth_lock:
            self.server.sessions={k:v for k,v in self.server.sessions.items() if v['expires']>time.time()}
            session=self.server.sessions.get(token)
        if session is None:raise HTTPError(401,'authentication_required','Open the private DJ Lab launch page or send your local bearer key.')
        if write and (origin!=self.server.origin or not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf'])):
            raise HTTPError(403,'csrf','Same-origin CSRF token is required')
        return session

    def session(self):
        # file:// launch forms have Origin:null; the one-time private nonce is the
        # credential here. No cookies or bearer token can replace this nonce.
        if self.headers.get('Origin') not in (None,'null',self.server.origin):raise HTTPError(403,'origin','Invalid launch origin')
        payload=self.body(form=True)
        require(set(payload)=={'nonce'} and len(payload['nonce'])==1,'Expected one launch nonce')
        with self.server.auth_lock:
            path=self.server.state/'launch-nonce.json'
            try:nonce=parse(secret_file(path))
            except (OSError,Invalid,ValueError):raise HTTPError(401,'launch_expired','Create a fresh private launch page')
            if nonce['expires_at']<time.time() or nonce['origin']!=self.server.origin or not hmac.compare_digest(payload['nonce'][0],nonce['nonce']):
                raise HTTPError(401,'launch_expired','Create a fresh private launch page')
            path.unlink();token=secrets.token_urlsafe(32)
            self.server.sessions[token]={'csrf':secrets.token_urlsafe(32),'expires':time.time()+8*3600}
        self.response(303,headers={'Location':'/','Set-Cookie':f'djlab_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})

    def media(self,ident):
        lib=self.server.library
        if ident not in lib.catalog['tracks']:raise HTTPError(404,'not_found','Track not found')
        if not lib.media_info(ident)['available']:raise HTTPError(409,'media_unavailable','Known media is missing or changed')
        row=lib.catalog['media'][ident];path=Path(row['path'])
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as stream:
            st=os.fstat(stream.fileno())
            if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)!=lib.media_signatures[ident]:raise HTTPError(409,'media_changed','Known media changed')
            start,end,status=0,st.st_size-1,200
            ranges=self.headers.get_all('Range') or []
            if ranges:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',ranges[0]) if len(ranges)==1 else None
                if not match or not any(match.groups()):
                    self.response(416,headers={'Content-Range':f'bytes */{st.st_size}'});return
                a,b=match.groups()
                if a:start=int(a);end=min(int(b) if b else end,end)
                else:start=max(0,st.st_size-int(b))
                if start>end or start>=st.st_size:
                    self.response(416,headers={'Content-Range':f'bytes */{st.st_size}'});return
                status=206
            length=end-start+1
            self.send_response(status);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(length));self.send_header('Accept-Ranges','bytes')
            self.send_header('Cache-Control','private, no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cross-Origin-Resource-Policy','same-origin')
            if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{st.st_size}')
            self.end_headers()
            if self.command=='HEAD':return
            stream.seek(start)
            while length:
                block=stream.read(min(length,256*1024))
                if not block:break
                self.wfile.write(block);length-=len(block)

    def handle_route(self):
        if len(self.path)>4096:raise HTTPError(414,'uri_too_long','Request path too long')
        if self.headers.get_all('Host') != [self.server.host]:raise HTTPError(403,'host','Use the exact loopback host and port')
        url=urlsplit(self.path)
        if url.scheme or url.netloc or url.fragment:raise HTTPError(400,'request_target','Invalid request target')
        path=url.path;read=self.command in ('GET','HEAD')
        if read and path=='/api/health':
            self.json(200,{'ok':True,'service':'djlab','version':1});return
        if read and path in ('/','/index.html','/styles.css','/app.js','/logo.png'):
            name='index.html' if path=='/' else path[1:];file=STATIC/name
            if not file.is_file():raise HTTPError(503,'ui_unavailable','The static interface has not been installed')
            regular(file);self.response(200,file.read_bytes(),mimetypes.guess_type(name)[0] or 'text/plain');return
        if self.command=='POST' and path=='/session':self.session();return
        session=self.auth(write=not read)
        params=parse_qs(url.query,max_num_fields=12)
        require(all(len(v)==1 for v in params.values()),'Repeated query fields are not supported')
        query={k:v[0] for k,v in params.items()};lib=self.server.library
        if read and path=='/api/session':self.json(200,{'csrf_token':session['csrf'] if session else None});return
        if read and path=='/api/capabilities':self.json(200,capabilities(lib));return
        if read and path=='/api/tracks':
            require(set(query)<= {'query','key','bpm_min','bpm_max'},'Unknown track filter')
            for field in ('bpm_min','bpm_max'):
                if field in query:query[field]=finite(float(query[field]),0,1000,field)
            rows=lib.tracks(**query);self.json(200,{'tracks':[track_summary(r) for r in rows],'total':len(rows)});return
        match=re.fullmatch(r'/api/tracks/(trk_[a-f0-9]{24})',path)
        if match:
            ident=match[1]
            if ident not in lib.catalog['tracks']:raise HTTPError(404,'not_found','Track not found')
            if read:
                with lib.locked():lib.reload();row=lib.track(ident)
                self.json(200,{'track':row});return
            if self.command=='PATCH':self.json(200,{'track':lib.patch_track(ident,self.body())});return
        match=re.fullmatch(r'/api/research/(trk_[a-f0-9]{24})',path)
        if match and (read or self.command=='POST'):
            from .research import research_track, cached_research
            require(not query,'Research routes do not accept query parameters')
            if match[1] not in lib.catalog['tracks']:raise HTTPError(404,'not_found','Track not found')
            with lib.locked():lib.reload();track=lib.track(match[1])
            if read:
                self.json(200,{'research':cached_research(track,lib.state)});return
            payload=self.body()
            require(isinstance(payload,dict) and set(payload)<= {'refresh'}
                    and type(payload.get('refresh',False)) is bool,'Research accepts only an optional boolean refresh')
            self.json(200,{'research':research_track(track,lib.state,refresh=payload.get('refresh',False))});return
        if path=='/api/playlists':
            if read:self.json(200,{'playlists':lib.playlist_list()});return
            if self.command=='POST':self.json(201,{'playlist':lib.playlist_put(self.body())});return
        match=re.fullmatch(r'/api/playlists/(pl_[a-f0-9]{24})',path)
        if match and self.command=='PUT':self.json(200,{'playlist':lib.playlist_put(self.body(),match[1])});return
        if read and path=='/api/recommendations':
            from .planning import recommend_tracks
            require(set(query)<={'track_id','limit'},'Unknown recommendation field')
            limit=int(query.get('limit',12));require(1<=limit<=91,'Limit must be 1–91')
            rows=lib.tracks();require(query.get('track_id') in lib.catalog['tracks'],'Track not found')
            self.json(200,{'recommendations':recommend_tracks(rows,query['track_id'],limit)});return
        if path=='/api/plans' and self.command=='POST':
            from .planning import build_plan
            payload=self.body();require(isinstance(payload,dict) and set(payload)<= {'track_ids','seed_track_id','target_duration_seconds','target_bpm','crossfade_beats'},'Unknown plan field')
            self.json(200,{'plan':build_plan(lib.tracks(),**payload)});return
        match=re.fullmatch(r'/api/exports/(json|csv|m3u8|xspf|rekordbox)',path)
        if read and match:
            from .exports import export_library
            require(set(query)<={'playlist_id'},'Unknown export field')
            playlist=None;rows=lib.tracks()
            if query.get('playlist_id'):
                playlist=next((p for p in lib.playlist_list() if p['id']==query['playlist_id']),None)
                if playlist is None:raise HTTPError(404,'not_found','Playlist not found')
                index={r['id']:r for r in rows};rows=[index[x] for x in playlist['track_ids']]
            media={r['id']:lib.catalog['media'][r['id']]['path'] for r in rows if r['media']['available']}
            body,mime,name=export_library(match[1],rows,playlist=playlist,media_paths=media)
            require(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name),'Unsafe export filename')
            self.response(200,body,mime,{'Content-Disposition':f'attachment; filename="{name}"'});return
        match=re.fullmatch(r'/api/media/(trk_[a-f0-9]{24})',path)
        if read and match:
            require(not query,'Media routes do not accept paths or query parameters')
            self.media(match[1]);return
        raise HTTPError(404,'not_found','No such API route')

    def run(self):
        try:self.handle_route()
        except HTTPError as e:
            self.close_connection=True;self.json(e.status,{'error':{'code':e.code,'message':e.message}})
        except (Invalid,ValueError,TypeError,KeyError) as e:
            self.close_connection=True;self.json(400,{'error':{'code':'invalid_request','message':str(e)[:250]}})
        except (BrokenPipeError,ConnectionResetError,TimeoutError):self.close_connection=True
        except OSError:
            self.close_connection=True;self.json(503,{'error':{'code':'local_io_unavailable','message':'A required local file is unavailable'}})

    do_GET=do_HEAD=do_POST=do_PATCH=do_PUT=run
