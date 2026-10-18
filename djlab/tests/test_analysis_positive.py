"""Replay the two actual successful Orion jobs, never synthesized DSP output."""
from pathlib import Path
import tempfile
import unittest

from djlab.analysis_import import validate_bundle
from djlab.evidence import CAPTURE, import_catalog
from djlab.library import Library, track_summary

PINS = {'runner':'88c8a26cf25cbd429cd5edec4e962a390be78b33c3669481ba747f93ad87bb54',
        'legacy_analyzer':'60b4db28d1228abe9278acc4628bd1bd1e1d59280ba0d24f111cc18382056334',
        'process_guard':'fe67d2b55581e543b7b5c381ae344f24fc2a42920494da4b037fee7d9776ab97'}
RECEIPTS = {'prefix':'9a61acd039418bf79d77adc69b96a098ce61b5e44f77880fb0b51b7cfed4ab01',
            'full':'d20e4a8a832a9b6918587a97141090edd142dcb0edfee9721042841795d6eb54'}
TRACK = 'trk_6881dabe87a539f675268509'

class ActualOrionPositive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = import_catalog(CAPTURE)

    def test_actual_partial_and_full_measurements_keep_distinct_coverage(self):
        results = {}
        for kind in RECEIPTS:
            checked = validate_bundle(CAPTURE/('orion-v2-'+kind), receipt_sha256=RECEIPTS[kind],
                                      source_pins=PINS, catalog=self.catalog)
            results[kind] = checked['tracks'][0]['record']
            self.assertEqual(checked['tracks'][0]['track_id'], TRACK)
            self.assertFalse(checked['rights_verified'])
            self.assertFalse(checked['listening_verified'])
        self.assertFalse(results['prefix']['coverage']['full_track'])
        self.assertEqual(results['prefix']['coverage']['analyzed_seconds'], 60)
        self.assertEqual(len(results['prefix']['waveform']['frames']), 1200)
        self.assertTrue(results['full']['coverage']['full_track'])
        self.assertAlmostEqual(results['full']['coverage']['analyzed_seconds'], 158.427302)
        self.assertEqual(len(results['full']['waveform']['frames']), 3169)
        self.assertEqual(len(results['full']['cue_suggestions']), 8)

    def test_import_replay_preserves_manual_edits_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp).resolve()/'state'; lib = Library(self.catalog, state)
            original = lib.track(TRACK)['analysis']
            lib.patch_track(TRACK, {'bpm':70,'tags':['Preparation review'],
                                  'cues':[{'name':'Opening audition','seconds':0,'kind':'memory','slot':None}]})
            for kind in RECEIPTS:
                response = lib.import_analysis(CAPTURE/('orion-v2-'+kind),
                          receipt_sha256=RECEIPTS[kind], source_pins=PINS)
                self.assertTrue(response['imported'])
            row = lib.track(TRACK)
            self.assertEqual(row['bpm'],70)
            self.assertEqual(row['bpm_source'],'manual')
            self.assertEqual(row['tags'],['Preparation review'])
            self.assertEqual(len(row['cues']),1)
            self.assertEqual(len(row['cue_suggestions']),8)
            self.assertIn(original,[h['record'] for h in row['analysis_history']])
            self.assertEqual(row['energy']['range'],[0,100])
            self.assertEqual(row['energy']['method'],'djlab_energy_v1')
            before = lib.journal.read_bytes()
            again = lib.import_analysis(CAPTURE/'orion-v2-full',receipt_sha256=RECEIPTS['full'],source_pins=PINS)
            self.assertTrue(again['already_imported']); self.assertEqual(lib.journal.read_bytes(),before)
            reopened = Library(self.catalog,state).track(TRACK)
            self.assertEqual(row,reopened)
            summary = track_summary(row)
            self.assertNotIn('frames',summary['waveform'])
            self.assertEqual(summary['waveform']['frame_count'],3169)
            self.assertEqual(len(row['waveform']['frames']),3169)

if __name__ == '__main__': unittest.main()
