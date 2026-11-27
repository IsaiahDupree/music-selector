from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

from djlab.evidence import CAPTURE, Invalid, digest, import_catalog
from djlab.library import Library
from djlab.server import Server, prepare_launch

STUDIO=Path(os.environ.get('DJLAB_REAL_STUDIO_ROOT',str(Path.home()/'Documents/Software/sour-sides-studio')))


class EvidenceTests(unittest.TestCase):
    def test_actual_91_tracks_and_refinement_join(self):
        catalog=import_catalog(CAPTURE)
        self.assertEqual(len(catalog['tracks']),91)
        soundcloud=[r for r in catalog['tracks'].values() if r['source']['kind']=='soundcloud']
        self.assertEqual(len(soundcloud),66)
        self.assertEqual(sum(len(r['analysis_history'])==2 for r in catalog['tracks'].values()),19)
        self.assertTrue(all(r['source']['rights_status']=='unknown' and r['waveform'] is None and r['energy'] is None for r in catalog['tracks'].values()))
        self.assertEqual(len({r['sha256'] for r in catalog['tracks'].values()}),91)
        self.assertTrue(all(r['source']['url'].startswith('https://soundcloud.com/') for r in soundcloud))

    def test_changed_actual_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            dst=Path(temp).resolve()/'evidence';shutil.copytree(CAPTURE,dst)
            path=dst/'reports/orion-soundcloud-staging-receipt.json'
            raw=path.read_bytes();path.write_bytes(raw.replace(b'832c56',b'932c56',1))
            with self.assertRaisesRegex(Invalid,'Evidence hash changed'):import_catalog(dst)

    def test_private_journal_edits_and_parent_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp).resolve();catalog=import_catalog(CAPTURE);lib=Library(catalog,state)
            ident=next(iter(catalog['tracks']))
            changed=lib.patch_track(ident,{'key':'8a','bpm':128,'tags':['Warm','Warm'],
                                         'cues':[{'name':'Entry','seconds':1.25,'slot':0,'kind':'hotcue'}],
                                         'loops':[{'name':'Loop','start_seconds':4,'end_seconds':8}],'reviewed':True})
            self.assertEqual(changed['key'],'8A');self.assertEqual(changed['tags'],['Warm'])
            again=Library(catalog,state);self.assertEqual(again.track(ident)['cues'][0]['seconds'],1.25)
            self.assertEqual(again.track(ident)['analysis'],catalog['tracks'][ident]['analysis'])
            reset=again.patch_track(ident,{'key':None,'bpm':None})
            self.assertEqual(reset['key'],catalog['tracks'][ident]['key'])
            self.assertEqual(reset['key_source'],'analysis')
            parent=again.playlist_put({'name':'Folder'});child=again.playlist_put({'name':'Child','parent_id':parent['id'],'track_ids':[ident]})
            with self.assertRaisesRegex(Invalid,'cyclic'):again.playlist_put({'parent_id':child['id']},parent['id'])
            self.assertEqual((state/'manual-events.jsonl').stat().st_mode & 0o777,0o600)
            raw=(state/'manual-events.jsonl').read_bytes();(state/'manual-events.jsonl').write_bytes(raw.replace(b'Warm',b'Cold',1))
            with self.assertRaisesRegex(Invalid,'integrity'):Library(catalog,state)

    def test_bad_edit_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            lib=Library(import_catalog(CAPTURE),Path(temp).resolve());ident=next(iter(lib.catalog['tracks']))
            for patch in [{'bpm':float('nan')},{'bpm':True},{'key':'13A'}, {'path':'/etc/passwd'},
                          {'cues':[{'name':'A','seconds':1,'slot':0},{'name':'B','seconds':2,'slot':0}]},
                          {'loops':[{'name':'Bad','start_seconds':10,'end_seconds':2}]},
                          {'reviewed':'true'}]:
                with self.subTest(patch=patch),self.assertRaises(Invalid):lib.patch_track(ident,patch)


class RealHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This positive byte-stream test requires the actual recovered catalog.
        # It fails clearly if the owner's source is not mounted; no synthetic
        # track, fake media or skipped positive is substituted.
        cls.catalog=import_catalog(STUDIO)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.state=Path(self.temp.name).resolve()
        self.lib=Library(self.catalog,self.state);self.server=Server(self.lib,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.key=(self.state/'auth-key').read_text().strip()
        self.ident=next(iter(self.catalog['tracks']))
        self.request_observations=[]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        started=time.monotonic();status=None;size=None;error=None
        try:
            conn.request(method,path,body=body,headers=headers or {})
            res=conn.getresponse();status=res.status;raw=res.read();size=len(raw)
            return status,dict(res.getheaders()),raw
        except TimeoutError as exc:
            error='timeout'
            raise TimeoutError(f'Actual HTTP {method} {path.split("?")[0]} exceeded the unchanged five-second client deadline') from exc
        finally:
            conn.close()
            self.request_observations.append({'method':method,'path':path.split('?')[0],
                'status':status,'response_bytes':size,'elapsed_seconds':round(time.monotonic()-started,6),
                'error':error,'connection_closed':True})

    def bearer(self):return {'Authorization':'Bearer '+self.key}

    def cookie_session(self):
        prepare_launch(self.state,self.server.server_port)
        nonce=json.loads((self.state/'launch-nonce.json').read_text())['nonce']
        body=urlencode({'nonce':nonce})
        status,headers,_=self.request('POST','/session',body,{'Content-Type':'application/x-www-form-urlencoded','Origin':'null'})
        self.assertEqual(status,303);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        cookie=headers['Set-Cookie'].split(';')[0]
        status,_,raw=self.request('GET','/api/session',headers={'Cookie':cookie})
        self.assertEqual(status,200)
        return cookie,json.loads(raw)['csrf_token'],body

    def test_auth_host_origin_and_real_catalog(self):
        status,_,raw=self.request('GET','/api/health');self.assertEqual(status,200);self.assertEqual(json.loads(raw)['service'],'djlab')
        self.assertEqual(self.request('GET','/api/tracks')[0],401)
        self.assertEqual(self.request('GET','/api/tracks',headers={**self.bearer(),'Host':'attacker.example'})[0],403)
        self.assertEqual(self.request('GET','/api/tracks',headers={**self.bearer(),'Origin':'https://attacker.example'})[0],403)
        status,headers,raw=self.request('GET','/api/tracks',headers=self.bearer())
        self.assertEqual(status,200);data=json.loads(raw);self.assertEqual(data['total'],91)
        self.assertNotIn('Access-Control-Allow-Origin',headers)
        self.assertNotIn(self.key,raw.decode())

    def test_controlled_loopback_restart_preserves_auth(self):
        self.assertEqual(self.request('GET','/api/health')[0],200)
        port=self.server.server_port
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.server=Server(self.lib,port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.assertEqual(self.server.server_address,('127.0.0.1',port))
        self.assertEqual(self.request('GET','/api/tracks')[0],401)
        self.assertEqual(self.request('GET','/api/tracks',headers=self.bearer())[0],200)

    def test_actual_nonce_one_use_and_csrf(self):
        cookie,csrf,body=self.cookie_session()
        self.assertEqual(self.request('POST','/session',body,{'Content-Type':'application/x-www-form-urlencoded','Origin':'null'})[0],401)
        route='/api/tracks/'+self.ident;body=json.dumps({'tags':['HTTP reviewed']})
        headers={'Cookie':cookie,'Content-Type':'application/json'}
        self.assertEqual(self.request('PATCH',route,body,headers)[0],403)
        self.assertEqual(self.request('PATCH',route,body,{**headers,'Origin':'https://attacker.example','X-CSRF-Token':csrf})[0],403)
        self.assertEqual(self.request('PATCH',route,body,{**headers,'Origin':self.server.origin,'X-CSRF-Token':csrf})[0],200)
        self.assertEqual(Library(self.catalog,self.state).track(self.ident)['tags'],['HTTP reviewed'])

    def test_real_audio_range_and_unsafe_paths(self):
        tracks=self.lib.tracks();track=next((r for r in tracks if r['source']['kind']=='owner-production' and r['media']['available']),None)
        self.assertIsNotNone(track,'Actual recovered original audio must be present for HTTP byte integration')
        ident=track['id'];source=Path(self.catalog['media'][ident]['path'])
        with source.open('rb') as stream:stream.seek(11);expected=stream.read(257)
        status,headers,raw=self.request('GET','/api/media/'+ident,headers={**self.bearer(),'Range':'bytes=11-267'})
        self.assertEqual(status,206);self.assertEqual(raw,expected);self.assertEqual(int(headers['Content-Length']),257)
        self.assertEqual(self.request('GET','/api/media/'+ident,headers={**self.bearer(),'Range':'bytes=0-1,3-4'})[0],416)
        self.assertEqual(self.request('GET','/api/media/../../etc/passwd',headers=self.bearer())[0],404)
        self.assertEqual(self.request('GET','/api/media/'+ident+'?path=/etc/passwd',headers=self.bearer())[0],400)

    def test_malformed_and_oversized_requests(self):
        headers={**self.bearer(),'Content-Type':'application/json'};route='/api/tracks/'+self.ident
        self.assertEqual(self.request('PATCH',route,'{"bpm":NaN}',headers)[0],400)
        self.assertEqual(self.request('PATCH',route,'{"key":"8A","key":"9A"}',headers)[0],400)
        self.assertEqual(self.request('PATCH',route,'x'*65537,headers)[0],413)
        self.assertEqual(self.request('POST','/api/playlists',json.dumps({'name':'Set','track_ids':[self.ident]}),headers)[0],201)
        self.assertEqual(self.request('GET','/api/tracks?bpm_min=nan',headers=self.bearer())[0],400)

    def test_real_planning_and_exports_over_http(self):
        headers={**self.bearer(),'Content-Type':'application/json'}
        status,_,raw=self.request('GET','/api/recommendations?track_id='+self.ident+'&limit=5',headers=self.bearer())
        self.assertEqual(status,200);recommendations=json.loads(raw)['recommendations']
        self.assertEqual(len(recommendations),5);self.assertTrue(all(r['reasons'] for r in recommendations))
        ids=[self.ident,recommendations[0]['track']['id']]
        status,_,raw=self.request('POST','/api/plans',json.dumps({'track_ids':ids,'crossfade_beats':32}),headers)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['plan']['track_ids'],ids)
        available=[r['id'] for r in self.lib.tracks() if r['media']['available']][:2]
        self.assertEqual(len(available),2)
        status,_,raw=self.request('POST','/api/playlists',json.dumps({'name':'Actual source export','track_ids':available}),headers)
        self.assertEqual(status,201);playlist=json.loads(raw)['playlist']
        for format in ('json','csv','m3u8','xspf','rekordbox'):
            status,headers,raw=self.request('GET',f'/api/exports/{format}?playlist_id='+playlist['id'],headers=self.bearer())
            self.assertEqual(status,200,format);self.assertIn('attachment',headers['Content-Disposition']);self.assertTrue(raw)

    def test_real_research_cache_and_http_privacy_boundary(self):
        from djlab.library import private_directory, private_write
        from djlab.research import _binding, _cache_file
        from djlab.tests.test_research import CAPTURE_SHA, IDENT
        raw=(CAPTURE/'musicbrainz-preach-20261015.json').read_bytes()
        self.assertEqual(digest(raw),CAPTURE_SHA)
        private_directory(self.state/'research')
        path=_cache_file(_binding(self.catalog['tracks'][IDENT]),self.state)
        private_write(path,raw)
        route='/api/research/'+IDENT
        self.assertEqual(self.request('GET',route)[0],401)
        status,_,body=self.request('GET',route,headers=self.bearer())
        self.assertEqual(status,200)
        result=json.loads(body)['research']
        if result is not None:  # Exact historical response may expire; GET never refreshes it.
            self.assertTrue(result['cached']);self.assertFalse(result['verified_match'])
            self.assertEqual(result['raw_response_sha256'],json.loads(raw)['raw_response_sha256'])
        self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(list(path.parent.iterdir()),[path])
        cookie,csrf,_=self.cookie_session()
        headers={'Cookie':cookie,'Content-Type':'application/json'}
        self.assertEqual(self.request('POST',route,'{}',headers)[0],403)
        headers.update(Origin=self.server.origin,**{'X-CSRF-Token':csrf})
        for payload in ({'refresh':1},{'url':'https://example.com'},{'query':'private'}):
            self.assertEqual(self.request('POST',route,json.dumps(payload),headers)[0],400)
        owner=next(r for r in self.catalog['tracks'].values() if r['source']['kind']=='owner-production')
        self.assertEqual(self.request('POST','/api/research/'+owner['id'],'{}',headers)[0],400)
        self.assertEqual(self.request('GET',route+'?refresh=true',headers=self.bearer())[0],400)
        self.assertEqual(list(path.parent.iterdir()),[path])

    def test_changed_real_audio_copy_and_symlink_refused(self):
        catalog=deepcopy(self.catalog)
        candidates=[r for r in self.lib.tracks() if r['source']['kind']=='owner-production' and r['media']['available']]
        ident=min(candidates,key=lambda r:catalog['media'][r['id']]['bytes'])['id']
        original=Path(catalog['media'][ident]['path']);copy=self.state/'actual-audio-copy.mp3'
        shutil.copyfile(original,copy);catalog['media'][ident]['path']=str(copy)
        lib=Library(catalog,self.state/'media-check')
        self.assertTrue(lib.media_info(ident)['available'])
        os.utime(copy,ns=(copy.stat().st_atime_ns,copy.stat().st_mtime_ns+1000000))
        self.assertFalse(lib.media_info(ident)['available'])
        copy.unlink();copy.symlink_to(original)
        self.assertFalse(lib.media_info(ident)['available'])


if __name__=='__main__':unittest.main()
