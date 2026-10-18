"""Format and planning checks over the captured, real 91-track Orion catalog.

No synthesised track catalog, API mocks, audio decoding or media transforms.
XML checks validate our documented serialization, not a native DJ-app import.
"""
from copy import deepcopy
import csv
import io
import json
import math
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from djlab.evidence import CAPTURE, import_catalog
from djlab.exports import export_library
from djlab.planning import build_plan, normalize_key, recommend_tracks, tempo_match


class ActualCatalogPlanningExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = import_catalog(CAPTURE)
        cls.tracks = list(cls.catalog['tracks'].values())
        # These are the actual recorded media locations. Serialization tests
        # do not claim that fixture-relative original audio is present in CI.
        cls.paths = {k: v['path'] for k, v in cls.catalog['media'].items()}

    def test_all_actual_keys_normalize_to_their_recorded_camelot_codes(self):
        self.assertEqual(len(self.tracks), 91)
        for track in self.tracks:
            self.assertEqual(normalize_key(track['musical_key'])['camelot'], track['key'])
            self.assertIsNone(track['energy'])
            self.assertIsNone(track['waveform'])

    def test_explained_recommendations_do_not_invent_energy_or_calibrated_probability(self):
        before = json.dumps(self.tracks, sort_keys=True)
        seed = self.tracks[0]
        rows = recommend_tracks(self.tracks, seed['id'], 25)
        self.assertEqual(len(rows), 25)
        self.assertEqual(len({r['track']['id'] for r in rows}), 25)
        self.assertNotIn(seed['id'], {r['track']['id'] for r in rows})
        for row in rows:
            self.assertTrue(math.isfinite(row['score']) and 0 <= row['score'] <= 1)
            self.assertIsNone(row['components']['energy'])
            self.assertTrue(any('energy is excluded' in w for w in row['warnings']))
        self.assertEqual(before, json.dumps(self.tracks, sort_keys=True))
        self.assertEqual(rows, recommend_tracks(self.tracks, seed['id'], 25))

    def test_explicit_order_duration_and_overlap_use_actual_track_lengths(self):
        chosen = [r['id'] for r in self.tracks[:8]]
        plan = build_plan(self.tracks, track_ids=chosen, target_duration_seconds=900,
                          target_bpm=140, crossfade_beats=32)
        self.assertEqual(plan['track_ids'], chosen[:len(plan['track_ids'])])
        self.assertAlmostEqual(plan['estimated_duration_seconds'], 900, places=5)
        self.assertFalse(plan['rendered'])
        self.assertFalse(plan['phrase_alignment_verified'])
        for entry in plan['tracks']:
            self.assertLessEqual(entry['source_duration_seconds'],
                                 entry['track']['duration_seconds']+.0001)
            self.assertGreater(entry['duration_seconds'], 0)
        for previous, current, transition in zip(plan['tracks'], plan['tracks'][1:], plan['transitions']):
            self.assertAlmostEqual(current['mix_start_seconds'],
                                   previous['mix_start_seconds']+previous['duration_seconds']-
                                   transition['crossfade_seconds'], places=4)
        changed = deepcopy(self.tracks)
        changed[0]['revision'] = 1
        self.assertNotEqual(plan['id'], build_plan(changed, track_ids=chosen,
                            target_duration_seconds=900, target_bpm=140)['id'])

    def test_bad_inputs_and_half_time_are_explicit(self):
        bpm = self.tracks[0]['bpm']
        half = tempo_match(bpm, bpm*2)
        self.assertEqual(half['octave_factor'], 2)
        self.assertEqual(half['tempo_ratio'], 1)
        for value in (float('nan'), True, -1, 9999):
            with self.assertRaises(ValueError):
                build_plan(self.tracks, target_bpm=value)
        with self.assertRaises(ValueError):
            build_plan(self.tracks, track_ids=[self.tracks[0]['id']]*2)
        with self.assertRaises(ValueError):
            recommend_tracks(self.tracks, self.tracks[0]['id'], 1000)
        with self.assertRaises(ValueError):
            build_plan(self.tracks, seed_track_id=[])
        short = build_plan(self.tracks, track_ids=[self.tracks[0]['id']],
                           target_duration_seconds=900, target_bpm=140)
        self.assertFalse(short['target_duration_met'])
        self.assertTrue(any('does not fill' in warning for warning in short['warnings']))
        longer = build_plan(self.tracks, track_ids=[self.tracks[0]['id']],
                            target_duration_seconds=1800, target_bpm=140)
        self.assertNotEqual(short['id'], longer['id'])
        self.assertEqual(short['source_bindings'][0]['sha256'], self.tracks[0]['sha256'])
        # A corrected analysis key must change plan identity even when neither
        # source duration nor the manual-edit revision has changed.
        corrected = deepcopy(self.tracks)
        corrected[0]['key'] = self.tracks[1]['key'] if self.tracks[1]['key'] != corrected[0]['key'] else '1A'
        self.assertNotEqual(short['id'], build_plan(corrected,
                            track_ids=[corrected[0]['id']], target_duration_seconds=900,
                            target_bpm=140)['id'])

    def test_json_csv_retain_real_metadata_and_source_provenance(self):
        body, kind, filename = export_library('json', self.tracks)
        value = json.loads(body)
        self.assertIn('json', kind); self.assertTrue(filename.endswith('.json'))
        self.assertEqual(value['tracks'], self.tracks)
        csv_body, _, _ = export_library('csv', self.tracks)
        rows = list(csv.DictReader(io.StringIO(csv_body.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 91)
        self.assertEqual([r['sha256'] for r in rows], [r['sha256'] for r in self.tracks])
        self.assertTrue(all(r['energy'] == '' for r in rows))

    def test_playlist_formats_preserve_order_and_actual_locations(self):
        selected = self.tracks[3:9]
        playlist = {'id': 'format-validation', 'name': 'Actual recorded source subset',
                    'track_ids': [r['id'] for r in reversed(selected)]}
        expected = list(reversed(selected))
        m3u, _, _ = export_library('m3u8', self.tracks, playlist=playlist, media_paths=self.paths)
        locations = [line for line in m3u.decode().splitlines() if line and not line.startswith('#')]
        self.assertEqual(len(locations), len(expected))
        self.assertTrue(all(urlsplit(v).scheme == 'file' and urlsplit(v).netloc == 'localhost'
                            for v in locations))
        xspf, _, _ = export_library('xspf', self.tracks, playlist=playlist, media_paths=self.paths)
        tree = ET.fromstring(xspf)
        self.assertEqual([r.text for r in tree.findall('.//{http://xspf.org/ns/0/}location')], locations)
        xml, _, _ = export_library('rekordbox', self.tracks, playlist=playlist, media_paths=self.paths)
        tree = ET.fromstring(xml)
        collection = tree.find('COLLECTION')
        self.assertEqual(int(collection.attrib['Entries']), len(expected))
        self.assertEqual([r.attrib['Location'] for r in collection], locations)
        self.assertEqual(len(tree.findall('.//TEMPO')), 0)
        self.assertEqual([r.attrib['Tonality'] for r in collection],
                         [normalize_key(r['key'])['name'] for r in expected])
        with self.assertRaises(ValueError):
            export_library('rekordbox', self.tracks, playlist=playlist, media_paths={})

    def test_user_cue_loop_xml_boundaries_and_csv_formula_defense(self):
        # Real catalog records with deliberate user-edit payloads exercise the
        # export boundary; these edits are not attributed to the source analyzer.
        rows = deepcopy(self.tracks[:1]); row = rows[0]
        row['cues'] = [{'name': 'Reviewed intro', 'seconds': 4.5, 'slot': 0, 'kind': 'hotcue'}]
        row['loops'] = [{'name': 'Audition', 'start_seconds': 10.0, 'end_seconds': 15.0}]
        row['title'] = '=1+1'; row['tags'] = ['@unsafe spreadsheet expression']
        output, _, _ = export_library('rekordbox', rows, media_paths=self.paths)
        marks = ET.fromstring(output).findall('.//POSITION_MARK')
        self.assertEqual([(m.attrib['Type'], m.attrib['Num']) for m in marks], [('0','0'), ('4','-1')])
        output, _, _ = export_library('csv', rows)
        csv_row = next(csv.DictReader(io.StringIO(output.decode('utf-8-sig'))))
        self.assertEqual(csv_row['title'], "'=1+1")
        self.assertTrue(csv_row['tags'].startswith("'@"))
        row['cues'][0]['seconds'] = row['duration_seconds']+1
        with self.assertRaises(ValueError):
            export_library('rekordbox', rows, media_paths=self.paths)


if __name__ == '__main__':
    unittest.main()
