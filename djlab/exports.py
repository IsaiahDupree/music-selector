"""Open playlist exports; never mutate source audio or proprietary DJ databases."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path, PureWindowsPath
import re
import unicodedata
from urllib.parse import quote
from xml.etree import ElementTree as ET

from .planning import normalize_key


def _text(value):
    return ' '.join(''.join(c for c in str(value or '')
                            if unicodedata.category(c) not in {'Cc', 'Cf'}).split())


def _finite(value, default=None):
    return float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) else default


def _key(track):
    value = track.get('key')
    if isinstance(value, dict):
        value = value.get('camelot') or value.get('name')
    try:
        return normalize_key(value or track.get('musical_key', ''))
    except ValueError:
        return {'name': '', 'camelot': ''}


def _uri(track, paths):
    value = paths.get(track['id'])
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError('Every exported playlist track needs its available local media path')
    windows = PureWindowsPath(value)
    if windows.is_absolute() and windows.drive and not windows.drive.startswith('\\'):
        path = '/'+windows.as_posix()
    elif Path(value).is_absolute() and not value.startswith('//'):
        path = Path(value).as_posix()
    else:
        raise ValueError('Only absolute local file paths can be exported')
    return 'file://localhost'+quote(path, safe='/:')


def _csv_cell(value):
    value = _text(value)
    return "'"+value if value.startswith(('=', '+', '-', '@')) else value


def _xml(root):
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)+b'\n'


def export_library(format: str, tracks: list[dict], *, title='Sour Sides DJ Lab',
                   playlist=None, media_paths: dict[str, str] | None = None) -> tuple[bytes, str, str]:
    if format not in {'json', 'csv', 'm3u8', 'xspf', 'rekordbox'}:
        raise ValueError('Unsupported export format')
    if len(tracks) > 10000 or len({r['id'] for r in tracks}) != len(tracks):
        raise ValueError('Export requires unique track identities and at most 10,000 tracks')
    by_id = {row['id']: row for row in tracks}
    if playlist is not None:
        ids = playlist.get('track_ids')
        if not isinstance(ids, list) or len(ids) > 10000 or any(x not in by_id for x in ids):
            raise ValueError('Playlist references unknown tracks')
        rows = [by_id[x] for x in ids]
        title = playlist.get('name') or title
    else:
        rows = list(tracks)
    title = _text(title)[:160] or 'Sour Sides DJ Lab'
    filename = re.sub(r'[^A-Za-z0-9_-]+', '-', unicodedata.normalize('NFKD', title)).strip('-')[:80] or 'djlab'
    paths = media_paths or {}
    warnings = ['Generated from measured/edited library metadata; destination application import is not yet certified.',
                'Source media and existing DJ databases were not modified.',
                'An inferred beatgrid is never exported as a verified grid.']
    if format == 'json':
        body = {'contract': 'sour_sides_dj_library_export_v1', 'title': title,
                'exported_at': datetime.now(timezone.utc).isoformat(), 'playlist': playlist,
                'tracks': rows, 'warnings': warnings}
        return (json.dumps(body, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode(), 'application/json; charset=utf-8', filename+'.json'
    if format == 'csv':
        output = io.StringIO(newline=''); writer = csv.writer(output)
        writer.writerow(['id', 'title', 'artist', 'duration_seconds', 'bpm', 'musical_key',
                         'camelot', 'energy', 'tags', 'reviewed', 'source_url', 'rights_status', 'sha256'])
        for row in rows:
            key = _key(row); source = row.get('source') or {}; energy = row.get('energy')
            if isinstance(energy, dict): energy = energy.get('value')
            writer.writerow([_csv_cell(row.get('id')), _csv_cell(row.get('title')), _csv_cell(row.get('artist')),
                             _finite(row.get('duration_seconds'), ''), _finite(row.get('bpm'), ''),
                             key['name'], key['camelot'], _finite(energy, ''),
                             _csv_cell(' | '.join(row.get('tags') or [])), bool(row.get('reviewed')),
                             _csv_cell(source.get('url')), _csv_cell(source.get('rights_status')), row.get('sha256', '')])
        return output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', filename+'.csv'
    locations = {row['id']: _uri(row, paths) for row in rows}
    if format == 'm3u8':
        lines = ['#EXTM3U', '#PLAYLIST:'+title]
        for row in rows:
            duration = int(_finite(row.get('duration_seconds'), -1))
            lines.extend([f"#EXTINF:{duration},{_text(row.get('artist'))} - {_text(row.get('title'))}", locations[row['id']]])
        return ('\n'.join(lines)+'\n').encode(), 'application/vnd.apple.mpegurl; charset=utf-8', filename+'.m3u8'
    if format == 'xspf':
        ns = 'http://xspf.org/ns/0/'; ET.register_namespace('', ns)
        root = ET.Element('{'+ns+'}playlist', {'version': '1'})
        ET.SubElement(root, '{'+ns+'}title').text = title
        ET.SubElement(root, '{'+ns+'}creator').text = 'Sour Sides DJ Lab'
        listing = ET.SubElement(root, '{'+ns+'}trackList')
        for row in rows:
            track = ET.SubElement(listing, '{'+ns+'}track')
            for field, value in [('location', locations[row['id']]), ('identifier', 'urn:sha256:'+row['sha256']),
                                 ('title', _text(row.get('title'))), ('creator', _text(row.get('artist')))]:
                ET.SubElement(track, '{'+ns+'}'+field).text = value
            duration = _finite(row.get('duration_seconds'))
            if duration is not None:
                ET.SubElement(track, '{'+ns+'}duration').text = str(round(duration*1000))
            ET.SubElement(track, '{'+ns+'}annotation').text = f"{_key(row)['name']}; {row.get('bpm')} BPM; key estimate requires audition"
        return _xml(root), 'application/xspf+xml; charset=utf-8', filename+'.xspf'
    root = ET.Element('DJ_PLAYLISTS', {'Version': '1.0.0'})
    ET.SubElement(root, 'PRODUCT', {'Name': 'Sour Sides DJ Lab', 'Version': '0.1.0', 'Company': 'Sour Sides'})
    unique = {r['id']: r for r in rows}; ids = {key: str(i) for i, key in enumerate(unique, 1)}
    collection = ET.SubElement(root, 'COLLECTION', {'Entries': str(len(unique))})
    for row in unique.values():
        attrs = {'TrackID': ids[row['id']], 'Name': _text(row.get('title')),
                 'Artist': _text(row.get('artist')), 'Location': locations[row['id']],
                 'Tonality': _key(row)['name'],
                 'Comments': 'Sour Sides DJ Lab; key/BPM estimates require review; source audio unchanged'}
        bpm, duration = _finite(row.get('bpm')), _finite(row.get('duration_seconds'))
        if bpm is not None and bpm > 0: attrs['AverageBpm'] = f'{bpm:.6f}'
        if duration is not None and duration >= 0: attrs['TotalTime'] = str(int(duration))
        track = ET.SubElement(collection, 'TRACK', attrs)
        # Do not invent TEMPO/Battito=1 at time zero from an inferred BPM.
        # Destination software must establish its own beatgrid before cue import.
        for cue in row.get('cues') or []:
            seconds = _finite(cue.get('seconds'))
            slot = cue.get('slot')
            if seconds is None or seconds < 0 or (duration is not None and seconds > duration):
                raise ValueError('Cue is outside the measured track duration')
            if slot is not None and (isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 7):
                raise ValueError('Hot cue slot must be 0–7')
            ET.SubElement(track, 'POSITION_MARK', {'Name': _text(cue.get('name')),
                          'Type': '0', 'Start': f'{seconds:.6f}',
                          'Num': str(slot if slot is not None else -1)})
        for loop in row.get('loops') or []:
            start, end = _finite(loop.get('start_seconds')), _finite(loop.get('end_seconds'))
            if start is None or end is None or not 0 <= start < end or (duration is not None and end > duration):
                raise ValueError('Loop is outside the measured track duration')
            ET.SubElement(track, 'POSITION_MARK', {'Name': _text(loop.get('name')),
                          'Type': '4', 'Start': f'{start:.6f}', 'End': f'{end:.6f}', 'Num': '-1'})
    playlists = ET.SubElement(root, 'PLAYLISTS')
    folder = ET.SubElement(playlists, 'NODE', {'Type': '0', 'Name': 'ROOT', 'Count': '1'})
    node = ET.SubElement(folder, 'NODE', {'Type': '1', 'Name': title, 'Entries': str(len(rows)), 'KeyType': '0'})
    for row in rows: ET.SubElement(node, 'TRACK', {'Key': ids[row['id']]})
    return _xml(root), 'application/xml; charset=utf-8', filename+'-rekordbox.xml'
