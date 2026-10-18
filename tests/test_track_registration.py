"""
Tests for automatic track registration / unregistered file detection.

Covers scan_unregistered():
  - Returns files in tracks/ that are NOT in library.json
  - Returns empty list when all files are registered
  - Ignores .gitkeep and non-audio files
  - Ignores files already registered (by filename)
  - Works with nested subdirectories
  - Works when tracks_dir doesn't exist
  - Supports all audio extensions

Covers CLI --scan flag:
  - Prints unregistered files to stdout
  - --scan --json outputs valid JSON
  - Reports "all registered" message when nothing new

Covers the library contract:
  - Every registered local_path filename must match an existing key pattern
  - No duplicate IDs in library.json
  - No duplicate local_path values in library.json

Run: python3 -m pytest tests/test_track_registration.py -v
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


AUDIO_EXTENSIONS = suggest.AUDIO_EXTENSIONS

MINIMAL_LIBRARY = {
    "version": "2.0",
    "tracks_dir": "tracks",
    "tracks": [
        {
            "id": "registered-track",
            "title": "Registered",
            "artist": "Artist",
            "local_path": "tracks/registered-track.mp3",
            "mood": "energetic", "moods": ["energetic"],
            "energy_level": 0.8, "genre": "electronic",
            "is_trending": False, "platforms_trending": [],
            "suitable_for": [],
        }
    ],
    "content_type_map": {}, "platform_map": {}, "mood_compatibility": {},
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

class TempTracksEnv:
    """Context manager: temp directory with a fake library.json + tracks/ subdir."""

    def __init__(self, library=None):
        self.library = library or MINIMAL_LIBRARY
        self._tmpdir = None

    def __enter__(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.tracks = self.root / "tracks"
        self.tracks.mkdir()
        self.lib_path = self.root / "library.json"
        with open(self.lib_path, "w") as f:
            json.dump(self.library, f)
        return self

    def __exit__(self, *args):
        self._tmpdir.cleanup()

    def add_track_file(self, filename: str) -> Path:
        p = self.tracks / filename
        p.write_bytes(b"FAKE AUDIO DATA")
        return p

    def patch_library(self):
        """Return a patch context for suggest.LIBRARY_PATH."""
        return patch.object(suggest, "LIBRARY_PATH", self.lib_path)


# ─── scan_unregistered() ─────────────────────────────────────────────────────

class TestScanUnregistered(unittest.TestCase):

    def test_new_file_detected_as_unregistered(self):
        with TempTracksEnv() as env:
            env.add_track_file("new-song.mp3")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertIn("new-song.mp3", filenames)

    def test_registered_file_not_in_results(self):
        with TempTracksEnv() as env:
            env.add_track_file("registered-track.mp3")  # name matches library
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertNotIn("registered-track.mp3", filenames)

    def test_empty_tracks_dir_returns_empty_list(self):
        with TempTracksEnv() as env:
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        self.assertEqual(results, [])

    def test_all_registered_returns_empty_list(self):
        with TempTracksEnv() as env:
            env.add_track_file("registered-track.mp3")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        self.assertEqual(results, [])

    def test_gitkeep_is_ignored(self):
        with TempTracksEnv() as env:
            (env.tracks / ".gitkeep").touch()
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertNotIn(".gitkeep", filenames)

    def test_non_audio_files_ignored(self):
        with TempTracksEnv() as env:
            env.add_track_file("readme.txt")
            env.add_track_file("image.jpg")
            env.add_track_file("data.json")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertNotIn("readme.txt", filenames)
        self.assertNotIn("image.jpg", filenames)
        self.assertNotIn("data.json", filenames)

    def test_all_audio_extensions_detected(self):
        with TempTracksEnv() as env:
            for ext in AUDIO_EXTENSIONS:
                env.add_track_file(f"newsong{ext}")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        found_exts = {r["suffix"] for r in results}
        self.assertEqual(found_exts, AUDIO_EXTENSIONS)

    def test_result_has_required_fields(self):
        with TempTracksEnv() as env:
            env.add_track_file("my-new-track.mp3")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIn("path", r)
        self.assertIn("filename", r)
        self.assertIn("stem", r)
        self.assertIn("suffix", r)

    def test_result_stem_is_filename_without_extension(self):
        with TempTracksEnv() as env:
            env.add_track_file("cool-track.aac")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        r = results[0]
        self.assertEqual(r["stem"], "cool-track")
        self.assertEqual(r["suffix"], ".aac")
        self.assertEqual(r["filename"], "cool-track.aac")

    def test_result_path_is_absolute(self):
        with TempTracksEnv() as env:
            env.add_track_file("track.mp3")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        self.assertTrue(Path(results[0]["path"]).is_absolute())

    def test_nonexistent_tracks_dir_returns_empty(self):
        with TempTracksEnv() as env:
            nonexistent = env.root / "does_not_exist"
            with env.patch_library():
                results = suggest.scan_unregistered(nonexistent)
        self.assertEqual(results, [])

    def test_multiple_unregistered_files_all_returned(self):
        with TempTracksEnv() as env:
            env.add_track_file("song-a.mp3")
            env.add_track_file("song-b.aac")
            env.add_track_file("song-c.wav")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        self.assertEqual(len(results), 3)

    def test_mix_of_registered_and_unregistered(self):
        with TempTracksEnv() as env:
            env.add_track_file("registered-track.mp3")   # in library
            env.add_track_file("new-track.mp3")           # NOT in library
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertIn("new-track.mp3", filenames)
        self.assertNotIn("registered-track.mp3", filenames)

    def test_nested_subdirectory_files_detected(self):
        with TempTracksEnv() as env:
            subdir = env.tracks / "downloads"
            subdir.mkdir()
            (subdir / "downloaded.mp3").write_bytes(b"data")
            with env.patch_library():
                results = suggest.scan_unregistered(env.tracks)
        filenames = [r["filename"] for r in results]
        self.assertIn("downloaded.mp3", filenames)

    def test_uses_default_tracks_dir_from_library(self):
        """When tracks_dir=None, should find tracks/ relative to library.json."""
        with TempTracksEnv() as env:
            env.add_track_file("auto-detected.mp3")
            with env.patch_library():
                # Pass None to use default resolution
                results = suggest.scan_unregistered(None)
        filenames = [r["filename"] for r in results]
        self.assertIn("auto-detected.mp3", filenames)


# ─── CLI --scan flag ─────────────────────────────────────────────────────────

class TestScanCLI(unittest.TestCase):

    SUGGEST = str(ROOT / "suggest.py")

    def _run_scan(self, env_path, extra_args=()):
        result = subprocess.run(
            [sys.executable, self.SUGGEST, "--scan", *extra_args],
            capture_output=True, text=True,
            env={**os.environ, "MUSIC_INDEX_PATH": str(env_path)},
        )
        return result

    def test_scan_flag_exits_zero(self):
        with TempTracksEnv() as env:
            r = self._run_scan(env.lib_path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_scan_reports_unregistered_filename(self):
        with TempTracksEnv() as env:
            env.add_track_file("surprise.mp3")
            r = self._run_scan(env.lib_path)
        self.assertIn("surprise.mp3", r.stdout)

    def test_scan_all_clean_prints_registered_message(self):
        with TempTracksEnv() as env:
            r = self._run_scan(env.lib_path)
        self.assertIn("registered", r.stdout.lower())

    def test_scan_json_output_is_valid_json(self):
        with TempTracksEnv() as env:
            env.add_track_file("new.mp3")
            r = self._run_scan(env.lib_path, ["--json"])
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertIsInstance(data, list)

    def test_scan_json_has_expected_fields(self):
        with TempTracksEnv() as env:
            env.add_track_file("new-track.mp3")
            r = self._run_scan(env.lib_path, ["--json"])
        data = json.loads(r.stdout)
        self.assertEqual(len(data), 1)
        self.assertIn("filename", data[0])
        self.assertIn("stem", data[0])
        self.assertIn("suffix", data[0])
        self.assertIn("path", data[0])

    def test_scan_json_empty_when_all_registered(self):
        with TempTracksEnv() as env:
            r = self._run_scan(env.lib_path, ["--json"])
        data = json.loads(r.stdout)
        self.assertEqual(data, [])

    def test_scan_reports_suggested_id(self):
        with TempTracksEnv() as env:
            env.add_track_file("cool-new-song.mp3")
            r = self._run_scan(env.lib_path)
        self.assertIn("cool-new-song", r.stdout)


# ─── Library integrity contract ───────────────────────────────────────────────

class TestLibraryIntegrity(unittest.TestCase):
    """The real library.json must have no duplicates and valid structure."""

    def setUp(self):
        with open(ROOT / "library.json", encoding="utf-8") as f:
            self.lib = json.load(f)

    def test_no_duplicate_track_ids(self):
        ids = [t["id"] for t in self.lib["tracks"]]
        self.assertEqual(len(ids), len(set(ids)),
                         f"Duplicate IDs found: {[i for i in ids if ids.count(i) > 1]}")

    def test_no_duplicate_local_paths(self):
        paths = [t.get("local_path", "") for t in self.lib["tracks"] if t.get("local_path")]
        self.assertEqual(len(paths), len(set(paths)),
                         f"Duplicate local_paths found: {[p for p in paths if paths.count(p) > 1]}")

    def test_all_local_paths_use_audio_extension(self):
        for track in self.lib["tracks"]:
            lp = track.get("local_path", "")
            if lp:
                ext = Path(lp).suffix.lower()
                self.assertIn(ext, AUDIO_EXTENSIONS,
                              f"Track '{track['id']}' has non-audio extension: {ext}")

    def test_local_paths_point_to_tracks_subdir(self):
        for track in self.lib["tracks"]:
            lp = track.get("local_path", "")
            if lp:
                self.assertTrue(
                    lp.startswith("tracks/"),
                    f"Track '{track['id']}' local_path should start with 'tracks/': {lp}",
                )

    def test_track_ids_match_local_path_stems(self):
        """ID should match the filename stem to make file management obvious."""
        for track in self.lib["tracks"]:
            lp = track.get("local_path", "")
            if not lp:
                continue
            stem = Path(lp).stem
            self.assertEqual(
                track["id"], stem,
                f"Track id '{track['id']}' doesn't match local_path stem '{stem}'"
            )


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
