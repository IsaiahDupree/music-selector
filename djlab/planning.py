"""Explainable DJ preparation from measured or manually reviewed metadata.

These are original ranking rules, not calibrated compatibility probabilities.
Plans are metadata proposals: no audio is decoded, rendered or beatgrid verified.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone


_MINOR = ['Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#']
_MAJOR = ['B', 'F#', 'Db', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E']
_PITCH = {'C': 0, 'B#': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
          'E': 4, 'Fb': 4, 'F': 5, 'E#': 5, 'F#': 6, 'Gb': 6, 'G': 7,
          'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11}
_KNOWN = {f'{i}{letter}': (pitch, mode) for letter, pitches, mode in
          [('A', _MINOR, 'minor'), ('B', _MAJOR, 'major')]
          for i, pitch in enumerate(pitches, 1)}


def normalize_key(value: str) -> dict:
    if not isinstance(value, str) or len(value) > 48:
        raise ValueError('Key must be a musical key or Camelot code')
    value = value.strip().replace('♯', '#').replace('♭', 'b')
    camelot = value.upper()
    if camelot in _KNOWN:
        pitch, mode = _KNOWN[camelot]
        return {'name': f'{pitch} {mode}', 'camelot': camelot}
    match = re.fullmatch(r'([A-Ga-g])([#b]?)(?:\s*(major|minor|maj|min|m))?', value)
    if not match:
        raise ValueError('Unrecognized key; use a musical key or 1A–12B')
    pitch = match[1].upper() + match[2]
    if pitch not in _PITCH:
        raise ValueError('Unrecognized pitch')
    mode = 'minor' if match[3] in {'minor', 'min', 'm'} else 'major'
    code = next(c for c, (p, m) in _KNOWN.items()
                if m == mode and _PITCH[p] == _PITCH[pitch])
    canonical, _ = _KNOWN[code]
    return {'name': f'{canonical} {mode}', 'camelot': code}


def _number(value, *, minimum=0.0, maximum=float('inf')):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        return None
    return float(value)


def _key(track):
    value = track.get('key')
    if isinstance(value, dict):
        value = value.get('camelot') or value.get('name')
    try:
        return normalize_key(value or track.get('musical_key', ''))['camelot']
    except ValueError:
        return None


def _energy(track):
    value = track.get('energy')
    if isinstance(value, dict):
        bounds = value.get('range')
        method = value.get('method') or value.get('id')
        if not isinstance(bounds, list) or len(bounds) != 2 or not isinstance(method, str):
            return None
        low, high = (_number(x, minimum=-1000, maximum=1000) for x in bounds)
        if low is None or high is None or high <= low:
            return None
        measured = _number(value.get('value', value.get('score')), minimum=low, maximum=high)
        return None if measured is None else ((measured-low)/(high-low), method)
    measured = _number(value, minimum=1, maximum=10)
    return None if measured is None else ((measured-1)/9, 'unspecified_1_to_10')


def harmonic_relation(first: str | None, second: str | None) -> dict:
    if not first or not second:
        return {'name': 'unknown', 'score': None, 'compatible': False}
    a, b = int(first[:-1]), int(second[:-1])
    distance = min((a-b) % 12, (b-a) % 12)
    if first == second:
        return {'name': 'same key', 'score': 1.0, 'compatible': True}
    if a == b:
        return {'name': 'relative major/minor', 'score': 0.94, 'compatible': True}
    if first[-1] == second[-1] and distance == 1:
        return {'name': 'adjacent fifth', 'score': 0.88, 'compatible': True}
    return {'name': 'different key; audition required', 'score': max(0, 0.45-distance*0.07),
            'compatible': False}


def tempo_match(source_bpm, target_bpm) -> dict:
    source = _number(source_bpm, minimum=20, maximum=400)
    target = _number(target_bpm, minimum=20, maximum=400)
    if source is None or target is None:
        return {'effective_source_bpm': source, 'tempo_ratio': None,
                'octave_factor': 1, 'score': None, 'within_ten_percent': False}
    factor = min((1.0, 0.5, 2.0), key=lambda x: abs(math.log(target/(source*x))))
    ratio = target/(source*factor)
    difference = abs(ratio-1)
    return {'effective_source_bpm': round(source*factor, 6), 'tempo_ratio': round(ratio, 8),
            'octave_factor': factor, 'score': max(0.0, 1-difference/0.20),
            'within_ten_percent': 0.9 <= ratio <= 1.1}


def _pair(anchor, candidate, target_bpm=None):
    harmonic = harmonic_relation(_key(anchor), _key(candidate))
    tempo = tempo_match(candidate.get('bpm'), target_bpm or anchor.get('bpm'))
    first_energy, second_energy = _energy(anchor), _energy(candidate)
    energy = (None if first_energy is None or second_energy is None or
              first_energy[1] != second_energy[1] else max(0, 1-abs(first_energy[0]-second_energy[0])))
    parts = [('harmonic', harmonic['score'], .55), ('tempo', tempo['score'], .35),
             ('energy', energy, .10)]
    present = [(v, w) for _, v, w in parts if v is not None]
    score = sum(v*w for v, w in present)/sum(w for _, w in present) if present else 0
    reasons = [harmonic['name']]
    warnings = ['Metadata compatibility is a preparation aid; audition the transition.']
    if tempo['tempo_ratio'] is not None:
        reasons.append(f"Tempo change {(tempo['tempo_ratio']-1)*100:+.1f}%")
        if not tempo['within_ten_percent']:
            warnings.append('Tempo change is outside the existing mix worker’s ±10% limit.')
        if tempo['octave_factor'] != 1:
            warnings.append('Half/double-time beat interpretation is assumed, not verified.')
    else:
        warnings.append('A usable BPM is missing.')
    if energy is None:
        warnings.append('No comparable measured energy score; energy is excluded from ranking.')
    for row in (anchor, candidate):
        separation = (row.get('analysis') or {}).get('key_separation')
        if _number(separation) is not None and separation < .08 and not row.get('reviewed'):
            warnings.append('At least one key estimate has a small uncalibrated profile gap.')
            break
    return {'track': candidate, 'score': round(score, 6), 'reasons': reasons,
            'components': {k: None if v is None else round(v, 6) for k, v, _ in parts},
            'harmonic_relation': harmonic['name'], 'tempo': tempo,
            'compatible': harmonic['compatible'] and tempo['within_ten_percent'],
            'warnings': warnings, 'ranking_method': 'djlab_explainable_metadata_v1'}


def recommend_tracks(tracks: list[dict], track_id: str, limit: int = 12) -> list[dict]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('Recommendation limit must be 1–100')
    by_id = {r['id']: r for r in tracks}
    if len(by_id) != len(tracks):
        raise ValueError('Duplicate track identity')
    if not isinstance(track_id, str) or track_id not in by_id:
        raise ValueError('Unknown seed track')
    rows = [_pair(by_id[track_id], t) for t in tracks if t['id'] != track_id]
    return sorted(rows, key=lambda r: (-int(r['compatible']), -r['score'], r['track']['id']))[:limit]


def build_plan(tracks: list[dict], *, track_ids=None, seed_track_id=None,
               target_duration_seconds=None, target_bpm=None, crossfade_beats=32) -> dict:
    by_id = {r['id']: r for r in tracks}
    if not tracks or len(by_id) != len(tracks):
        raise ValueError('A nonempty library with unique identities is required')
    if target_duration_seconds is not None and _number(
            target_duration_seconds, minimum=30, maximum=43200) is None:
        raise ValueError('Target duration must be 30 seconds–12 hours')
    if target_bpm is not None and _number(target_bpm, minimum=20, maximum=400) is None:
        raise ValueError('Target BPM must be 20–400')
    if _number(crossfade_beats, minimum=0, maximum=128) is None:
        raise ValueError('Crossfade must be 0–128 beats')
    explicit = track_ids is not None
    if explicit:
        if not isinstance(track_ids, list) or not 1 <= len(track_ids) <= 100:
            raise ValueError('Choose 1–100 track IDs')
        if any(not isinstance(x, str) or x not in by_id for x in track_ids):
            raise ValueError('Unknown plan track')
        if len(set(track_ids)) != len(track_ids):
            raise ValueError('A track may appear only once in this plan')
        ordered = [by_id[x] for x in track_ids]
    else:
        if seed_track_id is not None and (not isinstance(seed_track_id, str) or seed_track_id not in by_id):
            raise ValueError('Unknown seed track')
        seed = by_id[seed_track_id] if seed_track_id else min(tracks, key=lambda t: t['id'])
        ordered = [seed]
    tempo = float(target_bpm or ordered[0].get('bpm') or 0)
    if _number(tempo, minimum=20, maximum=400) is None:
        raise ValueError('Select a valid target BPM or a seed with a measured BPM')
    if not explicit:
        available = [r for r in tracks if r['id'] != ordered[0]['id']]
        estimate = _number(ordered[0].get('duration_seconds'), minimum=.001) or 0
        while available and len(ordered) < 100 and (target_duration_seconds is None or
                                                     estimate < target_duration_seconds):
            ranked = sorted((_pair(ordered[-1], x, tempo) for x in available),
                            key=lambda p: (-int(p['compatible']), -p['score'], p['track']['id']))
            choice = ranked[0]['track']; ordered.append(choice); available.remove(choice)
            estimate += max(0, (choice.get('duration_seconds') or 0)-crossfade_beats*60/tempo)
            if target_duration_seconds is None and len(ordered) >= 10:
                break
    entries, transitions = [], []
    end = 0.0
    for track in ordered:
        duration = _number(track.get('duration_seconds'), minimum=.001, maximum=43200)
        if duration is None:
            raise ValueError('Track has no usable measured duration')
        match = tempo_match(track.get('bpm'), tempo)
        if match['tempo_ratio'] is None:
            raise ValueError('Track has no usable BPM')
        # A half-time notation changes the beat unit, not playback by 2x.
        ratio = match['tempo_ratio']; full = duration/ratio
        overlap = min(crossfade_beats*60/tempo, full/2, entries[-1]['duration_seconds']/2) if entries else 0
        start = end-overlap
        used = min(full, max(0, target_duration_seconds-start)) if target_duration_seconds else full
        if used <= overlap and entries:
            break
        pair = _pair(entries[-1]['track'], track, tempo) if entries else None
        entry = {'track_id': track['id'], 'track': track, 'mix_start_seconds': round(start, 6),
                 'start_seconds': round(start, 6), 'source_start_seconds': 0.0,
                 'duration_seconds': round(used, 6), 'source_duration_seconds': round(used*ratio, 6),
                 'tempo_ratio': ratio, 'effective_source_bpm': match['effective_source_bpm'],
                 'tempo_octave_factor': match['octave_factor'],
                 'within_existing_mix_worker_tempo_limit': match['within_ten_percent']}
        if pair:
            transitions.append({'from_id': entries[-1]['track_id'], 'to_id': track['id'],
                                'mix_start_seconds': round(start, 6), 'crossfade_seconds': round(overlap, 6),
                                'score': pair['score'], 'compatible': pair['compatible'],
                                'reasons': pair['reasons'], 'warnings': pair['warnings'],
                                'phrase_alignment_verified': False})
        entries.append(entry); end = start+used
        if target_duration_seconds and end >= target_duration_seconds-1e-6:
            break
    source_bindings = [{'track_id': r['track_id'], 'sha256': r['track'].get('sha256'),
                        'revision': r['track'].get('revision'), 'key': r['track'].get('key'),
                        'bpm': r['track'].get('bpm'), 'energy': r['track'].get('energy'),
                        'analysis': [{k: h[k] for k in ('path', 'version', 'job_id', 'sha256',
                                       'collection_receipt_sha256') if k in h}
                                     for h in r['track'].get('analysis_history', [])]}
                       for r in entries]
    identity = {'track_ids': [r['track_id'] for r in entries], 'entries':
                [{k: v for k, v in r.items() if k != 'track'} for r in entries],
                'target_bpm': tempo, 'crossfade_beats': crossfade_beats,
                'requested_duration_seconds': target_duration_seconds,
                'source_bindings': source_bindings}
    plan_id = 'plan_'+hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
    short = target_duration_seconds is not None and end < target_duration_seconds-1e-4
    warnings = ['Preparation proposal only; audio has not been rendered.',
                'Cue/phrase alignment and half-time interpretation require review.',
                'Existing worker accepts tempo changes only within ±10%; other entries require adjustment.']
    if short:
        warnings.append('The selected material does not fill the requested set duration.')
    return {'id': plan_id, 'contract': 'sour_sides_dj_plan_v1',
            'created_at': datetime.now(timezone.utc).isoformat(), 'track_ids': identity['track_ids'],
            'source_bindings': source_bindings,
            'tracks': entries, 'transitions': transitions, 'target_bpm': tempo,
            'crossfade_beats': crossfade_beats, 'estimated_duration_seconds': round(end, 6),
            'requested_duration_seconds': target_duration_seconds, 'source_order_preserved': explicit,
            'target_duration_met': None if target_duration_seconds is None else not short,
            'rendered': False, 'phrase_alignment_verified': False,
            'warnings': warnings}
