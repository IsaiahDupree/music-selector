"""Offline owner-reviewed import of actual bounded Orion v2 audio evidence.

This verifies retained metadata and provenance, never decodes audio. Explicit
reviewed hashes are trust anchors; a self-authored receipt is not authentication.
"""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil

from .evidence import Invalid, canonical, digest, finite, parse, regular, require

TYPE = 'audio.harmonic_analyze_v2'
CONTRACT = 'orion_harmonic_analysis_result_v2'
PIN_FILES = {'runner': 'harmonic_audio_v2.py', 'legacy_analyzer': 'harmonic_audio.py',
             'process_guard': 'audio_process_guard.py'}
MAX_FILE = 32 * 1024**2
MAX_TOTAL = 256 * 1024**2
ENERGY_FORMULA = '100*(0.50*clip((rms_dbfs+45)/40,0,1)+0.30*clip(onsets_per_second/6,0,1)+0.20*clip(spectral_centroid_hz/4000,0,1))'


def sha_value(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid evidence SHA256')
    return value


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Evidence file must be a relative POSIX path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
            'Unsafe evidence path')
    return value


def number(value, low, high, label):
    return finite(value, low, high, label)


def close(actual, expected, tolerance, label):
    number(actual, -1e12, 1e12, label)
    require(abs(actual - expected) <= tolerance, label + ' mismatch')


def remote_path(root, relative_name):
    relative(relative_name)
    return str(PureWindowsPath(root) / PurePosixPath(relative_name))


def envelope(value):
    require(isinstance(value, dict) and value.get('ok') is True and isinstance(value.get('result'), dict),
            'Expected an actual successful authenticated API readback envelope')
    return value['result']


class Bundle:
    def __init__(self, root, receipt_sha256):
        self.root = Path(root).expanduser().absolute()
        self.cache = {}
        raw = self.raw('collection-receipt.json')
        require(digest(raw) == sha_value(receipt_sha256), 'Reviewed collection receipt hash changed')
        self.receipt = parse(raw)
        rows = self.receipt.get('files')
        require(isinstance(rows, list) and 1 <= len(rows) <= 2500, 'Missing bounded collection file inventory')
        self.files = {}
        total = 0
        for row in rows:
            require(isinstance(row, dict) and {'path','bytes','sha256'} <= set(row), 'Invalid collection file row')
            name = relative(row['path'])
            require(name != 'collection-receipt.json' and name not in self.files, 'Duplicate/self inventory entry')
            require(type(row['bytes']) is int and 0 <= row['bytes'] <= MAX_FILE, 'Oversized evidence file')
            sha_value(row['sha256']); total += row['bytes']
            require(total <= MAX_TOTAL, 'Analysis metadata exceeds bounded import size')
            data = self.raw(name)
            require(len(data) == row['bytes'] and digest(data) == row['sha256'], 'Collection file changed: ' + name)
            self.files[name] = row
        actual = set()
        for count, path in enumerate(self.root.rglob('*'), 1):
            require(count <= 3000, 'Unbounded collection directory inventory')
            require(not path.is_symlink(), 'Linked evidence is forbidden')
            if path.is_file():
                regular(path); actual.add(path.relative_to(self.root).as_posix())
        require(actual == set(self.files) | {'collection-receipt.json'}, 'Collection has missing or unreviewed files')

    def raw(self, name):
        name = relative(name)
        if name not in self.cache:
            path = self.root / name
            require(regular(path).st_size <= MAX_FILE, 'Oversized evidence file')
            self.cache[name] = path.read_bytes()
        return self.cache[name]

    def json(self, name):
        require(name in self.files, 'Required evidence is not inventoried: ' + name)
        return parse(self.raw(name))

    def artifact(self, name, row=None):
        key = 'out/' + relative(name)
        require(key in self.files, 'Missing artifact: ' + name)
        if row is not None:
            require(self.files[key]['bytes'] == row['bytes'] and self.files[key]['sha256'] == row['sha256'],
                    'Artifact inventory disagreement: ' + name)
        return self.raw(key)


def validate_bundle(root, *, receipt_sha256, source_pins, catalog):
    """Return actual rows only after all retained provenance joins pass."""
    require(set(source_pins) == set(PIN_FILES), 'Require three explicitly reviewed source pins')
    for value in source_pins.values(): sha_value(value)
    b = Bundle(root, receipt_sha256)
    job = b.json('job.json')
    ident = job.get('job_id')
    require(isinstance(ident, str) and re.fullmatch('wrk_[0-9a-f]{32}', ident), 'Invalid actual job identity')
    require(b.receipt.get('job_id') == ident and job.get('job_type') == TYPE and job.get('status') == 'succeeded'
            and job.get('exit_code') == 0 and job.get('error') is None and job.get('started_at') and job.get('completed_at'),
            'A successful actual typed v2 job is required')
    require(job.get('placement', {}).get('device') == 'orion' and job['placement'].get('resource_profile') == 'cpu-heavy',
            'Orion bounded CPU placement is required')
    status = dict(envelope(b.json('status-api.json')))
    actual_logs = {name+'_tail':b.raw(name+'.log')[-4000:].decode('utf-8',errors='replace')
                   for name in ('stdout','stderr')}
    require(all(name+'.log' in b.files for name in ('stdout','stderr'))
            and status.pop('logs', None) == actual_logs and status == job,
            'Status readback or raw log tails differ from retained job')
    api = envelope(b.json('artifacts-api.json'))
    require(api.get('job_id') == ident and api.get('status') == 'succeeded' and api.get('artifacts') == job.get('artifacts'),
            'Artifacts readback differs from actual job')
    artifacts = job['artifacts']; require(isinstance(artifacts, list) and artifacts, 'No job artifacts')
    indexed = {}
    for row in artifacts:
        require(isinstance(row, dict) and set(row) == {'name','bytes','sha256'}, 'Invalid artifact entry')
        name = relative(row['name']); require(name not in indexed, 'Duplicate job artifact')
        sha_value(row['sha256']); b.artifact(name, row); indexed[name] = row
    require(set(indexed) == {p[4:] for p in b.files if p.startswith('out/')}, 'Incomplete raw output inventory')
    manifest = b.json('out/manifest.json')
    require(manifest.get('artifacts') == [r for r in artifacts if r['name'] != 'manifest.json'], 'Output manifest artifact mismatch')
    for key in ('job_id','job_type','source_revision','input_sha256','placement','runtime'):
        require(manifest.get(key) == job.get(key), 'Output manifest job/runtime mismatch: ' + key)
    config = b.json('audio-v2-config.json'); params = job['params']
    require(config.get('job_id') == ident and config.get('job_type') == TYPE and config.get('params') == params,
            'Raw executed configuration differs from admitted job')
    require(PureWindowsPath(config['input_root']).is_absolute()
            and PureWindowsPath(config['output_root']).name == 'out'
            and PureWindowsPath(config['output_root']).parent.name == ident,
            'Executed input/output roots are not the owned Orion job paths')
    require(set(params) == {'manifest_input_id','manifest_sha256','output_name','timeout_sec','manifest','runtime'},
            'Unsupported v2 parameter fields')
    relative(params['manifest_input_id']); relative(params['output_name'])
    require(type(params['timeout_sec']) is int and 120 <= params['timeout_sec'] <= 3600, 'Invalid admitted deadline')
    input_manifest = b.json('input-manifest.json')
    require(digest(b.raw('input-manifest.json')) == params['manifest_sha256'] == job['input_sha256']
            and input_manifest == params['manifest'], 'Staged manifest bytes or admitted manifest disagree')
    require(set(input_manifest) == {'contract','tracks','coverage_mode','max_seconds'}
            and input_manifest['contract'] == 'orion_harmonic_analysis_v2', 'Wrong input manifest contract')
    mode = input_manifest['coverage_mode']; require(mode in ('prefix','full'), 'Unknown coverage mode')
    limit = number(input_manifest['max_seconds'],20,240 if mode == 'prefix' else 7200,'Coverage limit')
    inputs = input_manifest['tracks']
    require(isinstance(inputs,list) and 1 <= len(inputs) <= 8 and len(inputs)*limit <= 7200, 'Invalid requested workload')
    runtime = params['runtime']; require(job['runtime'] == runtime, 'Admitted/executed runtime mismatch')
    require(runtime.get('engine') == 'djlab_segmented_stft_v2' and runtime.get('threads') == 2
            and runtime.get('downloads_allowed') is False and runtime.get('external_dll_closure_pinned') is False,
            'Runtime safeguards or uncertainty flags changed')
    require(runtime.get('platform') == 'win32', 'Expected the registered Windows Orion runtime')
    files = runtime['files']
    require(set(files) == {'python','ffmpeg','ffprobe',*PIN_FILES}, 'Unexpected runtime files')
    for name, row in files.items():
        sha_value(row['sha256']); require(type(row['bytes']) is int and row['bytes'] > 0 and PureWindowsPath(row['path']).is_absolute(), 'Invalid runtime file pin')
        if name in PIN_FILES:
            captured = b.raw('source-evidence/' + PIN_FILES[name])
            require('source-evidence/' + PIN_FILES[name] in b.files and digest(captured) == row['sha256'] == source_pins[name]
                    and len(captured) == row['bytes'], 'Reviewed source pin mismatch: ' + name)
    packages = b.json('out/runtime-files.json')
    require(set(packages) == set(runtime['packages']) == {'numpy','scipy'}, 'Incomplete dependency inventory')
    for name, rows in packages.items():
        pin = runtime['packages'][name]
        require(isinstance(rows,list) and 0 < len(rows) <= 10000 and len({r['name'] for r in rows}) == len(rows), 'Invalid package inventory')
        for row in rows:
            sha_value(row['sha256']); require(type(row['bytes']) is int and row['bytes'] >= 0, 'Invalid dependency size')
        require(pin['file_count'] == len(rows) and pin['bytes'] == sum(r['bytes'] for r in rows) <= 512*1024**2
                and pin['tree_sha256'] == digest(canonical(rows)) and isinstance(pin['version'],str), 'Dependency tree pin mismatch')
    result = b.json('out/' + params['output_name'])
    require(result.get('contract') == CONTRACT and result.get('job_id') == ident and result.get('passed') is True
            and result.get('runtime') == runtime and result.get('manifest_sha256') == params['manifest_sha256']
            and result.get('source_hashes_verified_after') is True and result.get('runtime_verified_after') is True
            and result.get('rights_verified') is False and result.get('listening_verified') is False and 'error' not in result,
            'Actual successful analysis result and honest flags required')
    require(b.json('out/execution-result.json') == {k:v for k,v in result.items() if k != 'tracks'}, 'Execution receipt mismatch')
    number(result['elapsed_seconds'],0,params['timeout_sec'],'Actual elapsed job seconds')
    commands = b.json('out/commands.json')
    require(result.get('commands_sha256') == digest(b.raw('out/commands.json')) and isinstance(commands,list), 'Command log hash mismatch')
    known = {r['input_id']:r for r in catalog['tracks'].values()}
    require(len(result['tracks']) == len(inputs) and len({t['input_id'] for t in inputs}) == len(inputs), 'Incomplete/duplicate measured tracks')
    expected = [('ffmpeg-version',[files['ffmpeg']['path'],'-version'],None),
                ('ffprobe-version',[files['ffprobe']['path'],'-version'],None)]
    imported = []
    for index, (item,row) in enumerate(zip(inputs,result['tracks']),1):
        require(set(item) <= {'input_id','sha256','label'} and {'input_id','sha256'} <= set(item), 'Unknown staged track fields')
        source = known.get(item['input_id'])
        require(source is not None and source['sha256'] == item['sha256'] == row.get('sha256')
                and row.get('input_id') == item['input_id'], 'Analysis is not for a known catalog source SHA')
        for key,value in item.items():require(row.get(key) == value, 'Track manifest fields changed')
        prefix = f'track-{index:02d}'
        require(b.json('out/'+prefix+'-result.json') == row, 'Per-track immutable result mismatch')
        probe = b.json('out/'+prefix+'-probe.stdout')
        streams = [s for s in probe.get('streams',[]) if s.get('codec_type') == 'audio']
        require(len(streams) == 1, 'One actual audio stream required')
        duration = number(float(probe['format']['duration']),5,7200,'Probed source duration')
        close(row['duration_seconds'],duration,1e-6,'Result/probe duration')
        close(duration,source['duration_seconds'],.15,'Known source duration')
        require(mode != 'full' or duration <= limit+.001, 'Full analysis truncated its source')
        path = remote_path(config['input_root'],item['input_id'])
        expected.append((prefix+'-probe',[files['ffprobe']['path'],'-v','error','-show_format','-show_streams','-of','json',path],None))
        sections = row['sections']; target = min(duration,limit)
        require(isinstance(sections,list) and len(sections) == math.ceil(target/30), 'Missing measured windows')
        for n, section in enumerate(sections):
            start = n*30; length = min(30,target-start)
            close(section['start_seconds'],start,1e-8,'Section start')
            measured = number(section['duration_seconds'],0,30.05,'Measured window duration')
            close(section['end_seconds'],start+measured,1e-6,'Section end')
            close(measured,length,.05 if n==len(sections)-1 else 1/11025,'Decoded/requested window duration')
            require(section['section_kind'] == 'analysis_window_not_named_musical_section'
                    and {'not_listening_verified','scores_are_not_probabilities','downbeat_phase_unverified'} <= set(section['uncertainty']), 'Measured window uncertainty missing')
            db = number(section['rms_dbfs'],-240,60,'RMS'); centroid = number(section['spectral_centroid_hz'],0,5512.5,'Centroid')
            density = number(section['onsets_per_second'],0,100,'Onset density')
            clip = lambda v: min(1,max(0,v))
            score = 100*(.5*clip((db+45)/40)+.3*clip(density/6)+.2*clip(centroid/4000))
            close(section['energy_score'],score,.002,'Measured energy formula')
            expected.append((f'{prefix}-window-{n+1:03d}',[files['ffmpeg']['path'],'-nostdin','-v','error','-threads','2','-ss',f'{start:.9f}','-i',path,'-t',f'{length:.9f}','-map','0:a:0','-vn','-ac','1','-ar','11025','-f','f32le','pipe:1'],measured))
        covered = sections[-1]['end_seconds']; coverage = row['coverage']
        require(coverage['intervals_seconds'] == [[0,round(covered,6)]] and coverage['source_duration_seconds'] == duration
                and coverage['full_track'] is (abs(duration-covered)<=.05)
                and coverage['container_duration_tolerance_seconds'] == .05
                and coverage['method'] == 'contiguous_bounded_decoding_30_second_windows', 'False coverage claim')
        close(coverage['analyzed_seconds'],covered,1e-6,'Covered duration')
        energy = row['energy']; require(energy['id'] == 'djlab_energy_v1' and energy['range'] == [0,100]
                and energy['formula'] == ENERGY_FORMULA, 'Unknown energy definition')
        close(energy['score'],sum(s['energy_score']*s['duration_seconds'] for s in sections)/covered,.001,'Aggregated energy')
        waveform = row['waveform']; require(waveform['channels'] == ['time_seconds','minimum','maximum','rms']
                and waveform['sample_rate'] == 11025 and waveform['nominal_hz'] == 20
                and waveform['normalization'] == 'absolute_mono_downmix_float_pcm_full_scale_no_peak_normalization', 'Unknown waveform units')
        frames = waveform['frames']; require(isinstance(frames,list) and len(frames) == sum(math.ceil(round(s['duration_seconds']*11025)*20/11025) for s in sections), 'Waveform count mismatch')
        previous = -1
        for frame in frames:
            require(isinstance(frame,list) and len(frame)==4, 'Invalid waveform row')
            t,lo,hi,rms = frame
            number(t,0,covered,'Waveform time'); number(lo,-64,64,'Waveform minimum'); number(hi,-64,64,'Waveform maximum'); number(rms,0,64,'Waveform RMS')
            require(t>previous and lo<=hi and rms<=max(abs(lo),abs(hi))+.000002,'Invalid measured waveform values'); previous=t
        require(row['decoded_audio'] == {'sample_rate':11025,'channels':1,'format':'f32le','no_source_mutation':True}
                and row['manual_review_required'] is True, 'Decoded source or uncertainty changed')
        require(isinstance(row['cue_suggestions'],list) and len(row['cue_suggestions'])<=8,'Too many inferred cues')
        for cue in row['cue_suggestions']:
            number(cue['seconds'],0,covered,'Inferred cue'); number(cue['confidence'],0,1,'Cue heuristic score')
            require(cue['inferred'] is True and cue['confidence_is_probability'] is False and cue['listening_verified'] is False and cue['editable'] is True,'Inferred cue falsely verified')
        if row['bpm_estimate'] is not None:number(row['bpm_estimate'],20,380,'BPM estimate')
        if row['key_estimate'] is not None:
            from .planning import normalize_key
            normalize_key(row['key_estimate'])
        imported.append({'track_id':source['id'],'record':deepcopy(row)})
    require(len(commands) == len(expected), 'Unexpected or missing decoder commands')
    allowed_artifacts = {'manifest.json',params['output_name'],'execution-result.json','commands.json','runtime-files.json','analysis-progress.json'}
    for n in range(1,len(inputs)+1):allowed_artifacts.update({f'track-{n:02d}-result.json',f'track-{n:02d}-progress.json'})
    for command,(name,argv,measured) in zip(commands,expected):
        require(command.get('name') == name and command.get('argv') == argv and type(command.get('pid')) is int and command['pid']>0
                and command.get('exit_code') == 0 and command.get('started_at') and command.get('completed_at'), 'Unattested or altered fixed command')
        require(command['stdout'] == name+'.stdout' and command['stderr'] == name+'.stderr.txt', 'Command file identity changed')
        sha_value(command['stdout_sha256']);sha_value(command['stderr_sha256'])
        stderr=b.artifact(command['stderr']);require(digest(stderr)==command['stderr_sha256'],'Raw command stderr hash mismatch')
        allowed_artifacts.add(command['stderr'])
        if measured is None:
            require(command['stdout_retention']=='retained','Expected retained probe/version bytes')
            stdout=b.artifact(command['stdout']);require(digest(stdout)==command['stdout_sha256'] and len(stdout)==command['stdout_bytes'],'Raw stdout mismatch')
            allowed_artifacts.add(command['stdout'])
        else:
            require(command['stdout_retention']=='digest_only_ephemeral_decoded_pcm' and command['stdout'] not in indexed
                    and type(command['stdout_bytes']) is int and command['stdout_bytes'] == round(measured*11025)*4,
                    'PCM retention or measured byte count mismatch')
    require(set(indexed)==allowed_artifacts,'Unexpected retained output outside the fixed analysis contract')
    return {'job_id':ident,'receipt_sha256':receipt_sha256,'source_pins':dict(source_pins),
            'result_sha256':digest(b.raw('out/'+params['output_name'])),'result_name':params['output_name'],
            'tracks':imported,'files':deepcopy(b.receipt['files']),
            'rights_verified':False,'listening_verified':False,'fresh_submission_available':False}


def preserve_bundle(root, destination, *, receipt_sha256, source_pins, catalog):
    """Copy a validated metadata-only bundle exclusively; replay after copying."""
    checked=validate_bundle(root,receipt_sha256=receipt_sha256,source_pins=source_pins,catalog=catalog)
    destination=Path(destination)
    require(not destination.exists(),'Refusing to overwrite a private analysis bundle')
    destination.mkdir(mode=0o700)
    try:
        for name in ['collection-receipt.json',*[r['path'] for r in checked['files']]]:
            source=Path(root)/name;target=destination/name
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with source.open('rb') as inp, target.open('xb') as out:shutil.copyfileobj(inp,out,1024*1024)
            target.chmod(0o600)
        return validate_bundle(destination,receipt_sha256=receipt_sha256,source_pins=source_pins,catalog=catalog)
    except BaseException:
        # Preserve partial evidence for inspection; no journal event admits it.
        raise
