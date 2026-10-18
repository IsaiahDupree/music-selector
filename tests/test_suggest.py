"""
Tests for MusicLibrary/suggest.py
Run: python3 -m pytest tests/ -v
 or: python3 tests/test_suggest.py
"""

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))
import suggest


# ─── Fixtures ────────────────────────────────────────────────────────────────

TRACK_ENERGETIC = {
    "id": "test-energetic",
    "title": "Test Energetic",
    "artist": "Test Artist",
    "mood": "energetic",
    "moods": ["energetic", "uplifting", "upbeat"],
    "energy_level": 0.85,
    "genre": "hip_hop",
    "bpm": 160,
    "tempo": "fast",
    "duration_sec": 90,
    "local_path": "/tmp/test.mp3",
    "is_trending": False,
    "platforms_trending": [],
    "suitable_for": ["viral_short", "reels", "shorts"],
}

TRACK_CALM = {
    "id": "test-calm",
    "title": "Test Calm",
    "artist": "Test Artist 2",
    "mood": "calm",
    "moods": ["calm", "relaxed", "peaceful"],
    "energy_level": 0.3,
    "genre": "lofi",
    "bpm": 80,
    "tempo": "slow",
    "duration_sec": 180,
    "local_path": "/tmp/test2.mp3",
    "is_trending": False,
    "platforms_trending": [],
    "suitable_for": ["tutorial", "background"],
}

TRACK_TRENDING = {
    "id": "test-trending",
    "title": "Test Trending",
    "artist": "Test Artist 3",
    "mood": "happy",
    "moods": ["happy", "uplifting"],
    "energy_level": 0.7,
    "genre": "pop",
    "bpm": 120,
    "tempo": "medium",
    "duration_sec": 60,
    "local_path": "/tmp/test3.mp3",
    "is_trending": True,
    "platforms_trending": ["instagram", "tiktok"],
    "suitable_for": ["reels", "viral_short"],
}

MOCK_LIBRARY = {
    "version": "2.0",
    "tracks": [TRACK_ENERGETIC, TRACK_CALM, TRACK_TRENDING],
    "content_type_map": {
        "viral_short":  {"preferred_genres": ["hip_hop", "electronic", "pop"], "energy_range": [0.7, 1.0], "moods": ["energetic"]},
        "tutorial":     {"preferred_genres": ["lofi", "ambient"], "energy_range": [0.2, 0.5], "moods": ["calm"]},
        "reels":        {"preferred_genres": ["pop", "hip_hop"], "energy_range": [0.6, 1.0], "moods": ["energetic"]},
    },
    "platform_map": {
        "instagram": ["reels", "viral_short"],
        "tiktok":    ["viral_short", "shorts"],
        "youtube":   ["tutorial"],
    },
    "mood_compatibility": {
        "energetic": ["uplifting", "upbeat", "happy"],
        "calm":      ["relaxed", "peaceful", "focused"],
        "happy":     ["upbeat", "positive", "uplifting"],
    },
}


# ─── Unit tests: individual scoring functions ─────────────────────────────────

class TestScoreMood(unittest.TestCase):
    def setUp(self):
        self.compat = MOCK_LIBRARY["mood_compatibility"]

    def test_exact_match(self):
        score = suggest._score_mood(TRACK_ENERGETIC, "energetic", self.compat)
        self.assertEqual(score, 1.0)

    def test_in_moods_list(self):
        score = suggest._score_mood(TRACK_ENERGETIC, "uplifting", self.compat)
        self.assertEqual(score, 0.9)

    def test_compatible_mood(self):
        score = suggest._score_mood(TRACK_ENERGETIC, "happy", self.compat)
        self.assertGreaterEqual(score, 0.6)
        self.assertLess(score, 0.9)

    def test_incompatible_mood(self):
        score = suggest._score_mood(TRACK_CALM, "energetic", self.compat)
        self.assertLess(score, 0.5)

    def test_no_mood_returns_neutral(self):
        score = suggest._score_mood(TRACK_ENERGETIC, None, self.compat)
        self.assertEqual(score, 0.5)


class TestScoreEnergy(unittest.TestCase):
    def test_exact_match(self):
        score = suggest._score_energy(TRACK_ENERGETIC, 0.85)
        self.assertAlmostEqual(score, 1.0)

    def test_close_match(self):
        score = suggest._score_energy(TRACK_ENERGETIC, 0.75)
        self.assertGreater(score, 0.8)

    def test_far_mismatch(self):
        score = suggest._score_energy(TRACK_ENERGETIC, 0.1)
        self.assertLess(score, 0.3)

    def test_no_energy_returns_neutral(self):
        score = suggest._score_energy(TRACK_ENERGETIC, None)
        self.assertEqual(score, 0.5)

    def test_energy_clamps_at_zero(self):
        score = suggest._score_energy({"energy_level": 0.0}, 1.0)
        self.assertGreaterEqual(score, 0.0)


class TestScoreDuration(unittest.TestCase):
    def test_ideal_ratio(self):
        score = suggest._score_duration(TRACK_ENERGETIC, 90)  # ratio=1.0
        self.assertEqual(score, 1.0)

    def test_acceptable_ratio(self):
        score = suggest._score_duration(TRACK_ENERGETIC, 60)  # ratio=1.5
        self.assertEqual(score, 1.0)

    def test_too_short_track(self):
        score = suggest._score_duration(TRACK_ENERGETIC, 300)  # ratio=0.3
        self.assertLess(score, 0.5)

    def test_no_duration_returns_neutral(self):
        score = suggest._score_duration(TRACK_ENERGETIC, None)
        self.assertEqual(score, 0.5)

    def test_no_track_duration_returns_neutral(self):
        track = {**TRACK_ENERGETIC, "duration_sec": None}
        score = suggest._score_duration(track, 60)
        self.assertEqual(score, 0.5)


class TestScorePacing(unittest.TestCase):
    def test_fast_bpm_matches_fast_pacing(self):
        score = suggest._score_pacing(TRACK_ENERGETIC, "fast")  # bpm=160
        self.assertEqual(score, 1.0)

    def test_slow_bpm_mismatches_fast(self):
        score = suggest._score_pacing(TRACK_CALM, "fast")  # bpm=80
        self.assertLess(score, 0.5)

    def test_tempo_string_fallback(self):
        track_no_bpm = {**TRACK_ENERGETIC, "bpm": None, "tempo": "fast"}
        score = suggest._score_pacing(track_no_bpm, "fast")
        self.assertGreater(score, 0.5)

    def test_no_pacing_returns_neutral(self):
        score = suggest._score_pacing(TRACK_ENERGETIC, None)
        self.assertEqual(score, 0.5)


class TestScoreContentType(unittest.TestCase):
    def setUp(self):
        self.ct_map = MOCK_LIBRARY["content_type_map"]

    def test_exact_suitable_for(self):
        score = suggest._score_content_type(TRACK_ENERGETIC, "viral_short", self.ct_map)
        self.assertEqual(score, 1.0)

    def test_genre_match(self):
        # TRACK_ENERGETIC is hip_hop, viral_short prefers hip_hop
        score = suggest._score_content_type(TRACK_ENERGETIC, "viral_short", self.ct_map)
        self.assertGreaterEqual(score, 0.75)

    def test_no_match(self):
        score = suggest._score_content_type(TRACK_CALM, "viral_short", self.ct_map)
        self.assertLessEqual(score, 0.5)

    def test_no_content_type_returns_neutral(self):
        score = suggest._score_content_type(TRACK_ENERGETIC, None, self.ct_map)
        self.assertEqual(score, 0.5)


# ─── Transcript inference ─────────────────────────────────────────────────────

class TestInferFromTranscript(unittest.TestCase):
    def test_energetic_transcript(self):
        result = suggest._infer_from_transcript("this is amazing and so exciting wow incredible")
        self.assertEqual(result["mood"], "energetic")
        self.assertGreater(result["energy"], 0.6)

    def test_calm_transcript(self):
        result = suggest._infer_from_transcript("peaceful relaxing calm slow gentle soft")
        self.assertEqual(result["mood"], "calm")
        self.assertLess(result["energy"], 0.55)

    def test_inspiring_transcript(self):
        result = suggest._infer_from_transcript("I inspire and transform and build and grow and achieve")
        self.assertEqual(result["mood"], "inspiring")

    def test_empty_transcript(self):
        result = suggest._infer_from_transcript("")
        self.assertIn("mood", result)
        self.assertIn("energy", result)
        self.assertIsInstance(result["energy"], float)

    def test_energy_clamped(self):
        result = suggest._infer_from_transcript("amazing " * 50)
        self.assertLessEqual(result["energy"], 0.95)
        self.assertGreaterEqual(result["energy"], 0.2)


# ─── suggest_music() integration ─────────────────────────────────────────────

class TestSuggestMusic(unittest.TestCase):
    def _patched_suggest(self, **kwargs):
        with patch("suggest.load_library", return_value=MOCK_LIBRARY):
            return suggest.suggest_music(**kwargs)

    def test_returns_list(self):
        results = self._patched_suggest()
        self.assertIsInstance(results, list)

    def test_sorted_by_score_descending(self):
        results = self._patched_suggest()
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_n_respected(self):
        results = self._patched_suggest(top_n=2)
        self.assertLessEqual(len(results), 2)

    def test_score_field_present(self):
        results = self._patched_suggest()
        for r in results:
            self.assertIn("score", r)
            self.assertIn("score_breakdown", r)

    def test_score_in_valid_range(self):
        results = self._patched_suggest(mood="energetic", energy=0.8)
        for r in results:
            self.assertGreaterEqual(r["score"], 0.0)
            self.assertLessEqual(r["score"], 1.05)  # trending bonus can push slightly above 1.0

    def test_energetic_mood_ranks_energetic_track_first(self):
        results = self._patched_suggest(mood="energetic", energy=0.85, top_n=3)
        self.assertEqual(results[0]["id"], "test-energetic")

    def test_calm_mood_ranks_calm_track_first(self):
        results = self._patched_suggest(mood="calm", energy=0.2, top_n=3)
        self.assertEqual(results[0]["id"], "test-calm")

    def test_trending_only_filter(self):
        results = self._patched_suggest(trending_only=True)
        for r in results:
            self.assertTrue(r["is_trending"])

    def test_platform_infers_content_type(self):
        results_with = self._patched_suggest(platform="instagram")
        results_without = self._patched_suggest()
        # With platform, scores should differ (content_type inferred)
        # Both should return results
        self.assertGreater(len(results_with), 0)
        self.assertGreater(len(results_without), 0)

    def test_transcript_auto_infers_mood(self):
        results = self._patched_suggest(transcript="amazing exciting energetic wow incredible")
        self.assertGreater(len(results), 0)
        self.assertGreater(results[0]["score"], 0.3)

    def test_empty_library_returns_empty(self):
        empty_lib = {**MOCK_LIBRARY, "tracks": []}
        with patch("suggest.load_library", return_value=empty_lib):
            results = suggest.suggest_music(mood="energetic")
        self.assertEqual(results, [])


# ─── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling(unittest.TestCase):
    def test_load_library_missing_file_raises_clear_error(self):
        original = suggest.LIBRARY_PATH
        try:
            suggest.LIBRARY_PATH = Path("/tmp/does_not_exist_musiclib.json")
            with self.assertRaises(FileNotFoundError) as ctx:
                suggest.load_library()
            self.assertIn("library.json", str(ctx.exception).lower())
        finally:
            suggest.LIBRARY_PATH = original

    def test_load_library_malformed_json_raises_clear_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            bad_path = Path(f.name)
        original = suggest.LIBRARY_PATH
        try:
            suggest.LIBRARY_PATH = bad_path
            with self.assertRaises(ValueError) as ctx:
                suggest.load_library()
            self.assertIn("library.json", str(ctx.exception).lower())
        finally:
            suggest.LIBRARY_PATH = original
            bad_path.unlink(missing_ok=True)

    def test_invalid_energy_raises_value_error(self):
        with patch("suggest.load_library", return_value=MOCK_LIBRARY):
            with self.assertRaises(ValueError):
                suggest.suggest_music(energy=1.5)
            with self.assertRaises(ValueError):
                suggest.suggest_music(energy=-0.1)

    def test_invalid_top_n_raises_value_error(self):
        with patch("suggest.load_library", return_value=MOCK_LIBRARY):
            with self.assertRaises(ValueError):
                suggest.suggest_music(top_n=0)

    def test_track_missing_local_path_doesnt_crash(self):
        track_no_path = {**TRACK_ENERGETIC}
        del track_no_path["local_path"]
        lib = {**MOCK_LIBRARY, "tracks": [track_no_path]}
        with patch("suggest.load_library", return_value=lib):
            results = suggest.suggest_music()
        self.assertEqual(len(results), 1)

    def test_track_missing_energy_level_doesnt_crash(self):
        track = {**TRACK_ENERGETIC}
        del track["energy_level"]
        lib = {**MOCK_LIBRARY, "tracks": [track]}
        with patch("suggest.load_library", return_value=lib):
            results = suggest.suggest_music(energy=0.8)
        self.assertEqual(len(results), 1)

    def test_track_missing_duration_doesnt_crash(self):
        track = {**TRACK_ENERGETIC, "duration_sec": None}
        lib = {**MOCK_LIBRARY, "tracks": [track]}
        with patch("suggest.load_library", return_value=lib):
            results = suggest.suggest_music(duration=60)
        self.assertEqual(len(results), 1)


# ─── Real library file ────────────────────────────────────────────────────────

class TestRealLibrary(unittest.TestCase):
    """Integration tests against the real library.json."""

    def test_library_loads(self):
        lib = suggest.load_library()
        self.assertIn("tracks", lib)
        self.assertGreater(len(lib["tracks"]), 0)

    def test_all_tracks_have_required_fields(self):
        lib = suggest.load_library()
        required = ["id", "title", "artist", "mood", "moods", "energy_level", "genre"]
        for track in lib["tracks"]:
            for field in required:
                self.assertIn(field, track, f"Track '{track.get('id')}' missing field '{field}'")

    def test_energy_levels_in_range(self):
        lib = suggest.load_library()
        for track in lib["tracks"]:
            energy = track.get("energy_level", 0.5)
            self.assertGreaterEqual(energy, 0.0, f"Track {track['id']} energy below 0")
            self.assertLessEqual(energy, 1.0, f"Track {track['id']} energy above 1")

    def test_real_suggest_returns_results(self):
        results = suggest.suggest_music(mood="energetic", energy=0.8, top_n=3)
        self.assertGreater(len(results), 0)

    def test_real_suggest_tiktok(self):
        results = suggest.suggest_music(platform="tiktok", duration=30, top_n=5)
        self.assertGreater(len(results), 0)

    def test_real_suggest_transcript(self):
        results = suggest.suggest_music(
            transcript="I built an AI automation system that grows my Instagram while I sleep",
            platform="instagram"
        )
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
