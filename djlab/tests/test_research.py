"""Replay one genuine MusicBrainz response; no network calls or fake providers."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit

from djlab.evidence import CAPTURE, Invalid, canonical, digest, import_catalog, parse
from djlab.library import private_directory, private_write
from djlab.research import (_binding, _cache_file, _provider_lock, _result, _url,
                            cached_research, research_track, TTL_SECONDS)

CAPTURE_SHA = '31aa84c5be3f1621892cb719fee8caf4c837c226c1c32c91c1eff5ddd3ac3129'
IDENT = 'trk_94c9be58415240bc6ab5b6b2'


class RealRecordingResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = import_catalog(CAPTURE)
        cls.track = cls.catalog['tracks'][IDENT]
        cls.raw = (CAPTURE / 'musicbrainz-preach-20261015.json').read_bytes()
        assert digest(cls.raw) == CAPTURE_SHA, 'Actual recording evidence changed'
        cls.evidence = parse(cls.raw)

    def test_actual_provider_response_and_public_source_binding(self):
        binding = _binding(self.track)
        result = _result(binding, self.evidence, cached=True)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['raw_response_bytes'], 1709)
        self.assertEqual(result['raw_response_sha256'], '38d86e6c7040cf0fc66f02911b82db6f134e233c432e1e4a1d6efc1e0491ba2e')
        self.assertFalse(result['verified_match']); self.assertFalse(result['audio_uploaded'])
        self.assertTrue(all(not c['verified_match'] for c in result['candidates']))
        self.assertTrue(all(not link['verified_results'] for link in result['search_links']))
        self.assertEqual(parse_qs(urlsplit(result['request_url']).query),
                         {'query': ['recording:"Preach" AND artist:"Leotrix"'], 'fmt': ['json'], 'limit': ['5']})

    def test_exact_private_cache_read_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp).resolve(); private_directory(state / 'research')
            path = _cache_file(_binding(self.track), state)
            private_write(path, self.raw)
            result = cached_research(self.track, state)
            if time.time() - self.evidence['retrieved_epoch'] < TTL_SECONDS:
                self.assertTrue(result['cached'])
                self.assertEqual(result['raw_response_sha256'], self.evidence['raw_response_sha256'])
            else:
                self.assertIsNone(result)  # Historical evidence is never refreshed by GET.
            self.assertEqual(path.read_bytes(), self.raw)
            self.assertEqual(list((state / 'research').iterdir()), [path])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_private_and_nonpublic_sources_rejected_before_state_creation(self):
        owner = next(t for t in self.catalog['tracks'].values() if t['source']['kind'] == 'owner-production')
        variants = [owner]
        for suffix in ('/s-secret', '?secret_token=private', '#private'):
            track = deepcopy(self.track); track['source']['url'] += suffix; variants.append(track)
        for track in variants:
            with self.subTest(source=track['source']['kind']), tempfile.TemporaryDirectory() as temp:
                state = Path(temp).resolve() / 'untouched'
                with self.assertRaises(Invalid): research_track(track, state)
                self.assertFalse(state.exists())

    def test_changed_evidence_and_source_binding_rejected(self):
        mutations = []
        changed = deepcopy(self.evidence); changed['binding']['title'] += ' changed'; mutations.append(changed)
        changed = deepcopy(self.evidence); changed['raw_response_base64'] = base64.b64encode(b'changed').decode(); mutations.append(changed)
        changed = deepcopy(self.evidence); changed['user_agent'] = 'different'; mutations.append(changed)
        changed = deepcopy(self.evidence); changed['retrieved_at'] = '2000-01-01'; mutations.append(changed)
        for changed in mutations:
            with self.subTest(fields=list(changed)), self.assertRaises(Invalid):
                _result(_binding(self.track), changed, cached=True)

    def test_expired_actual_response_not_returned_as_fresh(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp).resolve(); private_directory(state / 'research')
            changed = deepcopy(self.evidence)
            changed['retrieved_epoch'] = time.time() - TTL_SECONDS - 1
            changed['retrieved_at'] = datetime.fromtimestamp(changed['retrieved_epoch'], timezone.utc).isoformat()
            private_write(_cache_file(_binding(self.track), state), canonical(changed))
            self.assertIsNone(cached_research(self.track, state))

    def test_cache_permissions_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp).resolve(); private_directory(state / 'research')
            path = _cache_file(_binding(self.track), state)
            private_write(path, self.raw); path.chmod(0o644)
            with self.assertRaisesRegex(Invalid, 'owner-only'): cached_research(self.track, state)
            path.unlink(); source = state / 'actual.json'; source.write_bytes(self.raw); path.symlink_to(source)
            with self.assertRaisesRegex(Invalid, 'Symlink'): cached_research(self.track, state)

    def test_actual_special_title_lucene_escaped_and_all_66_public_urls_admitted(self):
        public = [t for t in self.catalog['tracks'].values() if t['source']['kind'] == 'soundcloud']
        self.assertEqual(len(public), 66)
        for track in public: _binding(track)
        special = next(t for t in public if t['title'] == 'RQUNY - COME SELEKTA (AENSO REMIX)')
        query = parse_qs(urlsplit(_url(_binding(special))).query)['query'][0]
        self.assertIn(r'RQUNY \- COME SELEKTA \(AENSO REMIX\)', query)

    def test_real_inflight_lock_rejects_second_attempt_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp).resolve()
            with _provider_lock(state):
                with self.assertRaisesRegex(Invalid, 'already in flight'):
                    with _provider_lock(state): self.fail('A second request acquired the lock')
            with _provider_lock(state): pass


if __name__ == '__main__': unittest.main()
