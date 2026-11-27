"""Actual v1 evidence cannot be promoted to a v2 success; no synthetic jobs."""
from pathlib import Path
import tempfile
import unittest

from djlab.analysis_import import Bundle, validate_bundle
from djlab.evidence import CAPTURE, Invalid, canonical, digest, import_catalog, parse
from djlab.library import Library


class ActualAnalysisRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = import_catalog(CAPTURE)
        cls.actual = parse((CAPTURE/'reports/audio-analysis-submissions-live.json').read_bytes())[0]['response']['result']
        # These are the actual v1 runtime/source identities. They deliberately
        # cannot authorize the new v2 contract, even with an honest file inventory.
        cls.pins = {'runner':cls.actual['runtime']['audio_worker_sha256'],
                    'legacy_analyzer':cls.actual['runtime']['audio_worker_sha256'],
                    'process_guard':cls.actual['worker_code_sha256']}

    def prepare(self, root):
        raw = canonical(self.actual)
        (root/'job.json').write_bytes(raw)
        receipt = {'job_id':self.actual['job_id'], 'test_provenance':'Actual retained v1 admission readback; not a successful v2 job',
                   'files':[{'path':'job.json','bytes':len(raw),'sha256':digest(raw)}]}
        encoded=canonical(receipt); (root/'collection-receipt.json').write_bytes(encoded)
        return digest(encoded)

    def test_real_nonterminal_v1_job_cannot_import_or_mutate_manual_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve(); evidence=root/'evidence';evidence.mkdir()
            receipt_sha=self.prepare(evidence);lib=Library(self.catalog,root/'state')
            ident=next(iter(self.catalog['tracks']))
            lib.patch_track(ident,{'tags':['Preserved manual edit']})
            before=lib.journal.read_bytes()
            with self.assertRaisesRegex(Invalid,'successful actual typed v2 job'):
                lib.import_analysis(evidence,receipt_sha256=receipt_sha,source_pins=self.pins)
            self.assertEqual(lib.journal.read_bytes(),before)
            self.assertFalse((lib.state/'analysis-imports').exists())
            self.assertEqual(lib.track(ident)['tags'],['Preserved manual edit'])
            self.assertIsNone(lib.track(ident)['waveform'])

    def test_actual_inventory_changed_or_extra_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();receipt_sha=self.prepare(root)
            actual=(root/'job.json').read_bytes()
            (root/'job.json').write_bytes(actual+b'\n')
            with self.assertRaisesRegex(Invalid,'Collection file changed'):Bundle(root,receipt_sha)
            (root/'job.json').write_bytes(actual)
            (root/'extra-source.json').write_bytes(actual)
            with self.assertRaisesRegex(Invalid,'unreviewed files'):Bundle(root,receipt_sha)

    def test_actual_receipt_wrong_pin_and_link_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp).resolve();root=parent/'evidence';root.mkdir()
            receipt_sha=self.prepare(root)
            with self.assertRaisesRegex(Invalid,'receipt hash changed'):
                Bundle(root,digest((root/'job.json').read_bytes()))
            raw=(root/'job.json').read_bytes();(root/'job.json').unlink()
            (parent/'actual-job.json').write_bytes(raw);(root/'job.json').symlink_to(parent/'actual-job.json')
            with self.assertRaisesRegex(Invalid,'Symlink'):Bundle(root,receipt_sha)


if __name__=='__main__':unittest.main()
