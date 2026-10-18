"""
Tests for adapter utilities and env-var overrides added for GitHub packaging.

Run: python3 -m pytest tests/ -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import suggest


# ─── Fixtures ────────────────────────────────────────────────────────────────

MINIMAL_LIBRARY = {
    "version": "2.0",
    "tracks": [
        {
            "id": "test-track",
            "title": "Test Track",
            "artist": "Test Artist",
            "mood": "energetic",
            "moods": ["energetic", "uplifting"],
            "energy_level": 0.8,
            "genre": "hip_hop",
            "bpm": 140,
            "tempo": "fast",
            "duration_sec": 60,
            "local_path": "tracks/test-track.mp3",
            "is_trending": True,
            "platforms_trending": ["tiktok"],
            "suitable_for": ["viral_short", "reels"],
        }
    ],
    "content_type_map": {},
    "platform_map": {"tiktok": ["viral_short"]},
    "mood_compatibility": {"energetic": ["uplifting"]},
}


# ─── MUSIC_INDEX_PATH env var ─────────────────────────────────────────────────

class TestEnvVarOverride(unittest.TestCase):
    """MUSIC_INDEX_PATH should redirect load_library() to an alternate file."""

    def _write_temp_library(self, data: dict) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(data, f)
        f.close()
        return f.name

    def test_env_var_points_to_alternate_library(self):
        tmp = self._write_temp_library(MINIMAL_LIBRARY)
        original = suggest.LIBRARY_PATH
        try:
            # Simulate what happens when MUSIC_INDEX_PATH is set at import time
            suggest.LIBRARY_PATH = Path(tmp)
            lib = suggest.load_library()
            self.assertEqual(len(lib["tracks"]), 1)
            self.assertEqual(lib["tracks"][0]["id"], "test-track")
        finally:
            suggest.LIBRARY_PATH = original
            Path(tmp).unlink(missing_ok=True)

    def test_env_var_missing_file_raises_file_not_found(self):
        original = suggest.LIBRARY_PATH
        try:
            suggest.LIBRARY_PATH = Path("/tmp/nonexistent_music_selector_lib.json")
            with self.assertRaises(FileNotFoundError) as ctx:
                suggest.load_library()
            msg = str(ctx.exception)
            self.assertIn("library.json", msg.lower())
            # New message mentions the env var
            self.assertIn("MUSIC_INDEX_PATH", msg)
        finally:
            suggest.LIBRARY_PATH = original

    def test_suggest_music_works_against_alternate_library(self):
        tmp = self._write_temp_library(MINIMAL_LIBRARY)
        original = suggest.LIBRARY_PATH
        try:
            suggest.LIBRARY_PATH = Path(tmp)
            results = suggest.suggest_music(mood="energetic", top_n=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], "test-track")
        finally:
            suggest.LIBRARY_PATH = original
            Path(tmp).unlink(missing_ok=True)


# ─── library.json — relative paths ───────────────────────────────────────────

class TestRelativePaths(unittest.TestCase):
    """Verify the shipped library.json contains no absolute paths or personal URLs."""

    def setUp(self):
        with open(ROOT / "library.json", encoding="utf-8") as f:
            self.lib = json.load(f)

    def test_no_absolute_local_paths(self):
        for track in self.lib["tracks"]:
            lp = track.get("local_path", "")
            self.assertFalse(
                lp.startswith("/"),
                f"Track '{track['id']}' has absolute local_path: {lp}",
            )

    def test_no_supabase_urls(self):
        raw = json.dumps(self.lib)
        self.assertNotIn("supabase.co", raw,
                         "library.json must not contain supabase.co URLs")

    def test_no_personal_username_in_paths(self):
        raw = json.dumps(self.lib)
        # Catch common patterns like /Users/someuser or C:\Users\someuser
        import re
        matches = re.findall(r"/Users/\w+|C:\\Users\\\w+", raw)
        self.assertEqual(matches, [],
                         f"Personal paths found in library.json: {matches}")

    def test_tracks_use_tracks_prefix(self):
        for track in self.lib["tracks"]:
            lp = track.get("local_path", "")
            if lp:  # some tracks may have no local file yet
                self.assertTrue(
                    lp.startswith("tracks/"),
                    f"Track '{track['id']}' local_path should start with 'tracks/': {lp}",
                )

    def test_all_tracks_have_valid_energy(self):
        for track in self.lib["tracks"]:
            e = track.get("energy_level", 0.5)
            self.assertGreaterEqual(e, 0.0)
            self.assertLessEqual(e, 1.0)


# ─── library.template.json ────────────────────────────────────────────────────

class TestLibraryTemplate(unittest.TestCase):
    """Template must be valid JSON with the right schema keys."""

    def setUp(self):
        with open(ROOT / "library.template.json", encoding="utf-8") as f:
            self.tmpl = json.load(f)

    def test_template_is_valid_json(self):
        self.assertIn("tracks", self.tmpl)

    def test_template_has_required_top_level_keys(self):
        for key in ("version", "tracks", "content_type_map", "platform_map", "mood_compatibility"):
            self.assertIn(key, self.tmpl, f"Template missing key: {key}")

    def test_template_example_track_has_schema_fields(self):
        self.assertGreater(len(self.tmpl["tracks"]), 0)
        track = self.tmpl["tracks"][0]
        for field in ("id", "title", "artist", "local_path", "genre", "mood", "energy_level"):
            self.assertIn(field, track, f"Template track missing field: {field}")

    def test_template_local_path_is_relative(self):
        for track in self.tmpl["tracks"]:
            lp = track.get("local_path", "")
            self.assertFalse(lp.startswith("/"),
                             f"Template local_path must be relative: {lp}")


# ─── CLI smoke tests ──────────────────────────────────────────────────────────

class TestCLIIntegration(unittest.TestCase):
    """End-to-end CLI invocations via subprocess."""

    SUGGEST = str(ROOT / "suggest.py")

    def _run(self, *args, env=None):
        result = subprocess.run(
            [sys.executable, self.SUGGEST, *args],
            capture_output=True, text=True,
            env={**os.environ, **(env or {})},
        )
        return result

    def test_cli_list(self):
        r = self._run("--list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Music Library", r.stdout)

    def test_cli_json_output(self):
        r = self._run("--mood", "energetic", "--json", "--top", "1")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("score", data[0])
        self.assertIn("title", data[0])

    def test_cli_transcript(self):
        r = self._run("--transcript", "amazing AI automation tool", "--json", "--top", "1")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertGreater(len(data), 0)

    def test_cli_platform_tiktok(self):
        r = self._run("--platform", "tiktok", "--duration", "30", "--json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertGreater(len(data), 0)

    def test_cli_trending_flag(self):
        r = self._run("--trending", "--json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        for track in data:
            self.assertTrue(track["is_trending"])

    def test_cli_env_var_custom_library(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(MINIMAL_LIBRARY, tmp)
        tmp.close()
        try:
            r = self._run("--json", "--top", "1", env={"MUSIC_INDEX_PATH": tmp.name})
            self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
            data = json.loads(r.stdout)
            self.assertEqual(data[0]["id"], "test-track")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_cli_invalid_energy_exits_nonzero(self):
        r = self._run("--energy", "2.0")
        self.assertNotEqual(r.returncode, 0)

    def test_cli_no_args_returns_results(self):
        r = self._run("--json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertGreater(len(data), 0)


# ─── .gitignore coverage ─────────────────────────────────────────────────────

class TestGitignore(unittest.TestCase):
    """Verify .gitignore exists and covers audio extensions."""

    def setUp(self):
        with open(ROOT / ".gitignore", encoding="utf-8") as f:
            self.content = f.read()

    def test_gitignore_exists(self):
        self.assertTrue((ROOT / ".gitignore").exists())

    def test_audio_extensions_ignored(self):
        for ext in ("mp3", "aac", "wav", "flac", "m4a"):
            self.assertIn(f"*.{ext}", self.content,
                          f".gitignore missing *.{ext}")

    def test_env_files_ignored(self):
        self.assertIn(".env", self.content)

    def test_pycache_ignored(self):
        self.assertIn("__pycache__", self.content)

    def test_gitkeep_not_ignored(self):
        self.assertIn("!tracks/.gitkeep", self.content)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
