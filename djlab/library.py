"""Private append-only manual metadata and explainable, non-rendering set plans."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import threading

from .evidence import Invalid, canonical, clean, digest, finite, parse, regular, require


def now():
    return datetime.now(timezone.utc).isoformat()


def private_directory(path):
    path = Path(path).expanduser().absolute()
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "Private state may not use symlink ancestors")
        require(not (parent / ".git").exists(), "Private state must be outside every Git checkout")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(path.stat().st_uid == os.getuid(), "Private state belongs to another owner")
    os.chmod(path, 0o700)
    return path


def private_write(path, raw):
    path = Path(path)
    require(not path.is_symlink(), "Private output cannot be a symlink")
    temporary = path.with_name('.' + path.name + '.' + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def track_summary(track):
    """Keep measured arrays on the authenticated detail endpoint only."""
    row = deepcopy(track)
    def compact(record):
        if not isinstance(record, dict): return
        waveform = record.get('waveform')
        if isinstance(waveform, dict) and 'frames' in waveform:
            waveform['frame_count'] = len(waveform.pop('frames'))
            waveform['detail_available'] = True
        if isinstance(record.get('sections'), list):
            record['section_count'] = len(record.pop('sections'))
            record['detail_available'] = True
    compact(row); compact(row.get('analysis'))
    for history in row.get('analysis_history', []): compact(history.get('record'))
    return row


class Library:
    def __init__(self, catalog, state_dir):
        self.catalog = catalog
        self.state = private_directory(state_dir)
        self.lock = threading.RLock()
        self.journal = self.state / 'manual-events.jsonl'
        self.lockfile = self.state / 'manual-events.lock'
        self.overrides, self.playlists, self.events = {}, {}, []
        self.analysis_imports = []
        self.analysis_cache = {}
        self.media_signatures = {}
        for ident, row in catalog['media'].items():
            try:
                info = regular(row['path'])
                if info.st_size == row['bytes']:
                    self.media_signatures[ident] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            except (OSError, Invalid):
                pass
        with self.locked():
            self.reload()

    @contextmanager
    def locked(self):
        with self.lock:
            fd = os.open(self.lockfile, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)

    def reload(self):
        self.overrides, self.playlists, self.events, self.analysis_imports = {}, {}, [], []
        if not self.journal.exists():
            return
        require(regular(self.journal).st_size <= 16_000_000, 'Manual journal exceeds its bounded size')
        prior = None
        for line in self.journal.read_bytes().splitlines():
            event = parse(line)
            claimed = event.pop('sha256')
            require(digest(canonical(event)) == claimed and event['prev_sha256'] == prior
                    and event['sequence'] == len(self.events) + 1, 'Manual journal integrity failure')
            event['sha256'] = claimed
            if event['kind'] == 'track_patch':
                ident = event['id']
                require(ident in self.catalog['tracks'] and event['source_sha256'] == self.catalog['tracks'][ident]['sha256'],
                        'Manual changes refer to another source')
                self.overrides.setdefault(ident, {}).update(event['value'])
                self.overrides[ident]['revision'] = event['sequence']
            elif event['kind'] == 'playlist_put':
                self.playlists[event['id']] = event['value']
            elif event['kind'] == 'analysis_import':
                from .analysis_import import validate_bundle
                ident = event['id']; value = event['value']
                require(re.fullmatch(r'wrk_[a-f0-9]{32}', ident), 'Invalid imported job identity')
                root = self.state / 'analysis-imports' / ident
                # Every retained file signature is checked on each journal replay.
                # Changed bytes are revalidated against the reviewed hashes.
                signatures = []
                for path in sorted(root.rglob('*')):
                    require(not path.is_symlink(), 'Linked private analysis evidence')
                    if path.is_file():
                        info = regular(path)
                        signatures.append((str(path.relative_to(root)), info.st_dev, info.st_ino,
                                           info.st_size, info.st_mtime_ns, info.st_ctime_ns))
                cache_key = (digest(canonical(value)), tuple(signatures))
                cached = self.analysis_cache.get(ident)
                if cached is None or cached[0] != cache_key:
                    checked = validate_bundle(root, catalog=self.catalog, **value)
                    require(checked['job_id'] == ident, 'Private analysis job identity changed')
                    self.analysis_cache[ident] = (cache_key, checked)
                self.analysis_imports.append(self.analysis_cache[ident][1])
            else:
                raise Invalid('Unknown manual journal event')
            self.events.append(event); prior = claimed

    def append(self, kind, ident, value):
        event = {'sequence': len(self.events) + 1, 'prev_sha256': self.events[-1]['sha256'] if self.events else None,
                 'observed_at': now(), 'kind': kind, 'id': ident, 'value': value}
        if kind == 'track_patch':
            event['source_sha256'] = self.catalog['tracks'][ident]['sha256']
        event['sha256'] = digest(canonical(event))
        raw = canonical(event) + b'\n'
        require((self.journal.stat().st_size if self.journal.exists() else 0) + len(raw) <= 16_000_000,
                'Manual journal exceeds its bounded size')
        fd = os.open(self.journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'ab') as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        self.reload()

    def media_info(self, ident):
        source = self.catalog['media'][ident]
        try:
            info = regular(source['path'])
            signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            require(signature == self.media_signatures.get(ident), 'Media changed or was unavailable at import')
            return {'available': True, 'url': '/api/media/' + ident,
                    'verification': 'historical_sha_and_current_size', 'reason': None}
        except (OSError, Invalid):
            return {'available': False, 'url': None, 'verification': 'unavailable',
                    'reason': 'Known source file missing, unsafe, or changed; re-import after verifying it on Orion.'}

    def track(self, ident):
        require(ident in self.catalog['tracks'], 'Track not found')
        row = deepcopy(self.catalog['tracks'][ident])
        for imported in self.analysis_imports:
            measured = next((r['record'] for r in imported['tracks'] if r['track_id'] == ident), None)
            if measured is None: continue
            from .planning import normalize_key
            key = normalize_key(measured['key_estimate']) if measured['key_estimate'] is not None else None
            row.update(analysis=deepcopy(measured), analysis_version=2,
                       bpm=measured['bpm_estimate'], bpm_source='analysis_v2',
                       key=key['camelot'] if key else None,
                       musical_key=key['name'] if key else None, key_source='analysis_v2',
                       waveform={**deepcopy(measured['waveform']), 'measured': True},
                       energy={'value':measured['energy']['score'], 'range':[0,100],
                               'method':'djlab_energy_v1', 'verified':False},
                       coverage=deepcopy(measured['coverage']), sections=deepcopy(measured['sections']),
                       cue_suggestions=deepcopy(measured['cue_suggestions']))
            row['analysis_history'].append({'version':2, 'job_id':imported['job_id'],
                'sha256':imported['result_sha256'], 'collection_receipt_sha256':imported['receipt_sha256'],
                'source_pins':imported['source_pins'], 'record':deepcopy(measured)})
        patch = self.overrides.get(ident, {})
        row.update({k: v for k, v in patch.items() if v is not None})
        if patch.get('bpm') is not None: row['bpm_source'] = 'manual'
        if patch.get('key') is not None:
            from .planning import normalize_key
            row['key_source'] = 'manual'; row['musical_key'] = normalize_key(patch['key'])['name']
        row['media'] = self.media_info(ident)
        return row

    def tracks(self, *, query='', key='', bpm_min=None, bpm_max=None):
        with self.locked():
            self.reload()
            rows = [self.track(ident) for ident in self.catalog['tracks']]
        if query:
            words = clean(query).casefold().split()
            rows = [r for r in rows if all(w in ' '.join([r['title'], r['artist'], *r['tags'], r['source']['kind']]).casefold() for w in words)]
        if key: rows = [r for r in rows if r['key'] == key.upper()]
        if bpm_min is not None: rows = [r for r in rows if r['bpm'] is not None and r['bpm'] >= float(bpm_min)]
        if bpm_max is not None: rows = [r for r in rows if r['bpm'] is not None and r['bpm'] <= float(bpm_max)]
        return sorted(rows, key=lambda r: (r['title'].casefold(), r['id']))

    def import_analysis(self, evidence_dir, *, receipt_sha256, source_pins):
        from .analysis_import import preserve_bundle, validate_bundle
        with self.locked():
            self.reload()
            checked = validate_bundle(evidence_dir, receipt_sha256=receipt_sha256,
                                      source_pins=source_pins, catalog=self.catalog)
            ident = checked['job_id']
            prior = next((r for r in self.analysis_imports if r['job_id'] == ident), None)
            if prior is not None:
                require(prior['receipt_sha256'] == receipt_sha256 and prior['source_pins'] == source_pins,
                        'Existing job was imported with different reviewed evidence')
                return {'imported':False,'already_imported':True,'job_id':ident,'track_count':len(prior['tracks'])}
            parent = private_directory(self.state/'analysis-imports')
            preserve_bundle(evidence_dir, parent/ident, receipt_sha256=receipt_sha256,
                            source_pins=source_pins, catalog=self.catalog)
            self.append('analysis_import',ident,{'receipt_sha256':receipt_sha256,'source_pins':source_pins})
            return {'imported':True,'job_id':ident,'track_count':len(checked['tracks']),
                    'receipt_sha256':receipt_sha256,'fresh_submission_available':False}

    def patch_track(self, ident, patch):
        require(isinstance(patch, dict) and patch and set(patch) <= {'key','bpm','tags','cues','loops','reviewed'}, 'Unsupported track patch')
        with self.locked():
            self.reload(); track = self.track(ident); checked = {}
            if 'key' in patch:
                from .planning import normalize_key
                key = patch['key']
                try: checked['key'] = normalize_key(key)['camelot'] if key is not None else None
                except ValueError as exc: raise Invalid(str(exc)) from exc
            if 'bpm' in patch: checked['bpm'] = None if patch['bpm'] is None else finite(patch['bpm'],20,300,'BPM')
            if 'reviewed' in patch:
                require(type(patch['reviewed']) is bool, 'Reviewed must be boolean'); checked['reviewed'] = patch['reviewed']
            if 'tags' in patch:
                require(isinstance(patch['tags'],list) and len(patch['tags']) <= 30 and all(isinstance(t,str) and 0<len(clean(t))<=60 for t in patch['tags']), 'Tags must contain up to 30 short strings')
                checked['tags'] = list(dict.fromkeys(clean(t) for t in patch['tags']))
            for field in ('cues','loops'):
                if field not in patch: continue
                rows = patch[field]; require(isinstance(rows,list) and len(rows) <= (64 if field=='cues' else 32), 'Too many cues or loops')
                checked[field] = []; slots = set()
                for row in rows:
                    allowed = {'name','seconds','slot','kind'} if field=='cues' else {'name','start_seconds','end_seconds'}
                    require(isinstance(row,dict) and set(row)<=allowed and isinstance(row.get('name'),str) and len(clean(row['name']))<=100, 'Invalid cue/loop fields')
                    value = {'name':clean(row['name'])}
                    if field == 'cues':
                        value['seconds'] = finite(row.get('seconds'),0,track['duration_seconds'],'Cue position')
                        slot=row.get('slot');kind=row.get('kind','hotcue' if slot is not None else 'memory')
                        require(kind in ('memory','hotcue') and (slot is None or type(slot) is int and 0<=slot<=7 and slot not in slots), 'Use distinct hot-cue slots 0–7')
                        require((kind=='hotcue') == (slot is not None), 'Hot cues need a slot; memory cues do not')
                        if slot is not None: slots.add(slot)
                        value.update(slot=slot,kind=kind)
                    else:
                        start=finite(row.get('start_seconds'),0,track['duration_seconds'],'Loop start')
                        end=finite(row.get('end_seconds'),0,track['duration_seconds'],'Loop end'); require(end>start,'Loop end must follow start')
                        value.update(start_seconds=start,end_seconds=end)
                    checked[field].append(value)
            self.append('track_patch',ident,checked)
            return self.track(ident)

    def playlist_list(self):
        with self.locked(): self.reload(); return deepcopy(list(self.playlists.values()))

    def playlist_put(self, payload, ident=None):
        require(isinstance(payload,dict) and set(payload)<= {'name','parent_id','track_ids'}, 'Unknown playlist fields')
        with self.locked():
            self.reload()
            if ident is not None: require(ident in self.playlists,'Playlist not found')
            ident=ident or 'pl_'+secrets.token_hex(12)
            prior=self.playlists.get(ident,{})
            row={**prior,**payload,'id':ident,'updated_at':now()}
            require(isinstance(row.get('name'),str) and 0<len(clean(row['name']))<=100,'Playlist needs a short name')
            row['name']=clean(row['name']);row.setdefault('parent_id',None);row.setdefault('track_ids',[])
            require(isinstance(row['track_ids'],list) and len(row['track_ids'])<=1000 and len(set(row['track_ids']))==len(row['track_ids']) and all(t in self.catalog['tracks'] for t in row['track_ids']),'Playlist track IDs must be distinct known tracks')
            parent=row['parent_id'];seen={ident}
            while parent is not None:
                require(isinstance(parent,str) and parent in self.playlists and parent not in seen,'Invalid or cyclic playlist parent')
                seen.add(parent);parent=self.playlists[parent].get('parent_id')
            self.append('playlist_put',ident,row);return row

