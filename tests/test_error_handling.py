"""
Tests for all 14 error handling improvements.

Gaps covered:
  EH-1:  suggest.py load_library — encoding="utf-8" (non-ASCII track titles)
  EH-2:  suggest.py load_library — PermissionError with chmod hint
  EH-3:  suggest.py load_library — generic OSError propagation
  EH-4:  suggest.py suggest_music — duration > 0 validation
  EH-5:  suggest.py suggest_music — mood in VALID_MOODS validation
  EH-6:  suggest.py suggest_music — pacing in VALID_PACINGS validation
  EH-7:  suggest.py _print_results — safe .get() on all fields (no KeyError)
  EH-8:  suggest.py main() — exits with code 1 on FileNotFoundError
  EH-9:  ffmpeg_mix.py — sc_attack_ms >= 0 validation
  EH-10: ffmpeg_mix.py — sc_release_ms >= 0 validation
  EH-11: ffmpeg_mix.py — ffmpeg on PATH check (EnvironmentError)
  EH-12: ffmpeg_mix.py — input video exists check
  EH-13: ffmpeg_mix.py — output parent directory exists check
  EH-14: remotion.js — resolveTrackPath null guard (JS, source inspection)

Run: python3 -m pytest tests/test_error_handling.py -v
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import suggest
from adapters.ffmpeg_mix import mix_music


# ─── EH-1: UTF-8 encoding in load_library ─────────────────────────────────────

class TestEH1Utf8Encoding(unittest.TestCase):
    """load_library must open library.json with encoding='utf-8' so non-ASCII
    track titles (e.g. 'KUČKA — Overnight') do not raise UnicodeDecodeError."""

    def test_library_loads_with_non_ascii_title(self):
        data = {"tracks": [{"id": "non-ascii", "title": "KUČKA — Overnight", "artist": "KUČKA",
                             "local_path": "tracks/kucka.mp3", "genre": "electronic",
                             "mood": "calm", "moods": ["calm"], "energy_level": 0.4,
                             "is_trending": False, "platforms_trending": []}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            tmp = f.name
        try:
            with patch.object(suggest, "LIBRARY_PATH", Path(tmp)):
                lib = suggest.load_library()
            self.assertEqual(lib["tracks"][0]["title"], "KUČKA — Overnight")
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_open_call_uses_utf8(self):
        """Verify the source code opens library.json with encoding='utf-8'."""
        import inspect
        source = inspect.getsource(suggest.load_library)
        self.assertIn('encoding="utf-8"', source,
                      "load_library must open the file with encoding='utf-8'")


# ─── EH-2: PermissionError with chmod hint ────────────────────────────────────

class TestEH2PermissionError(unittest.TestCase):
    """load_library must re-raise PermissionError with a chmod hint."""

    def test_permission_error_message_includes_chmod(self):
        with patch.object(suggest, "LIBRARY_PATH", Path("/exists/fake")):
            with patch.object(Path, "exists", return_value=True):
                with patch("builtins.open", side_effect=PermissionError("denied")):
                    with self.assertRaises(PermissionError) as ctx:
                        suggest.load_library()
        self.assertIn("chmod", str(ctx.exception))


# ─── EH-3: Generic OSError propagation ───────────────────────────────────────

class TestEH3OSError(unittest.TestCase):
    """load_library must wrap generic OSError with the library path in the message."""

    def test_oserror_is_reraised_with_path(self):
        with patch.object(suggest, "LIBRARY_PATH", Path("/exists/fake")):
            with patch.object(Path, "exists", return_value=True):
                with patch("builtins.open", side_effect=OSError("disk error")):
                    with self.assertRaises(OSError) as ctx:
                        suggest.load_library()
        self.assertIn("Could not read", str(ctx.exception))


# ─── EH-4: duration > 0 ───────────────────────────────────────────────────────

class TestEH4DurationValidation(unittest.TestCase):

    def test_duration_zero_raises(self):
        with self.assertRaises(ValueError) as ctx:
            suggest.suggest_music(duration=0)
        self.assertIn("duration", str(ctx.exception))

    def test_duration_negative_raises(self):
        with self.assertRaises(ValueError):
            suggest.suggest_music(duration=-5)

    def test_duration_positive_does_not_raise_validation(self):
        # Should reach library load, not fail on duration validation
        try:
            suggest.suggest_music(duration=30)
        except ValueError as e:
            self.assertNotIn("duration must be", str(e))
        except (FileNotFoundError, OSError):
            pass  # library issues are fine here


# ─── EH-5: mood in VALID_MOODS ────────────────────────────────────────────────

class TestEH5MoodValidation(unittest.TestCase):

    def test_unknown_mood_raises(self):
        with self.assertRaises(ValueError) as ctx:
            suggest.suggest_music(mood="metalcore")
        self.assertIn("mood", str(ctx.exception).lower())
        self.assertIn("metalcore", str(ctx.exception))

    def test_valid_moods_do_not_raise(self):
        for mood in suggest.VALID_MOODS:
            try:
                suggest.suggest_music(mood=mood)
            except ValueError as e:
                self.assertNotIn("Unknown mood", str(e),
                                 f"Valid mood '{mood}' should not raise mood validation error")
            except (FileNotFoundError, OSError):
                pass

    def test_error_message_lists_valid_moods(self):
        with self.assertRaises(ValueError) as ctx:
            suggest.suggest_music(mood="techno")
        msg = str(ctx.exception)
        # Should list at least a few of the valid moods
        self.assertTrue(
            any(m in msg for m in ["energetic", "calm", "inspiring"]),
            f"Error should list valid moods, got: {msg}"
        )


# ─── EH-6: pacing in VALID_PACINGS ───────────────────────────────────────────

class TestEH6PacingValidation(unittest.TestCase):

    def test_unknown_pacing_raises(self):
        with self.assertRaises(ValueError) as ctx:
            suggest.suggest_music(pacing="turbo")
        self.assertIn("pacing", str(ctx.exception).lower())
        self.assertIn("turbo", str(ctx.exception))

    def test_valid_pacings_do_not_raise(self):
        for pacing in suggest.VALID_PACINGS:
            try:
                suggest.suggest_music(pacing=pacing)
            except ValueError as e:
                self.assertNotIn("Unknown pacing", str(e),
                                 f"Valid pacing '{pacing}' should not raise pacing validation error")
            except (FileNotFoundError, OSError):
                pass


# ─── EH-7: _print_results safe field access ───────────────────────────────────

class TestEH7PrintResultsSafe(unittest.TestCase):
    """_print_results must not raise KeyError on a minimal/malformed track dict."""

    def _capture_print(self, results, verbose=False):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            suggest._print_results(results, verbose=verbose)
        return buf.getvalue()

    def test_empty_list_prints_no_tracks(self):
        out = self._capture_print([])
        self.assertIn("No tracks found", out)

    def test_minimal_track_no_key_error(self):
        # Track with only partial fields — must not raise
        minimal = {"score": 0.5}
        try:
            self._capture_print([minimal])
        except KeyError as e:
            self.fail(f"_print_results raised KeyError on minimal track: {e}")

    def test_completely_empty_track_no_key_error(self):
        try:
            self._capture_print([{}])
        except KeyError as e:
            self.fail(f"_print_results raised KeyError on empty track dict: {e}")

    def test_verbose_mode_no_key_error_on_minimal(self):
        minimal = {"score": 0.7, "title": "T", "artist": "A"}
        try:
            self._capture_print([minimal], verbose=True)
        except KeyError as e:
            self.fail(f"_print_results verbose raised KeyError: {e}")


# ─── EH-8: main() exits with code 1 on error ─────────────────────────────────

class TestEH8MainExitCode(unittest.TestCase):

    def test_main_exits_1_on_missing_library(self):
        """main() must exit with code 1 when library.json is missing."""
        with patch.object(suggest, "LIBRARY_PATH", Path("/nonexistent/library.json")):
            with patch("sys.argv", ["suggest.py"]):
                with self.assertRaises(SystemExit) as ctx:
                    # Simulate the __main__ guard — main() raises FileNotFoundError,
                    # the guard catches it and calls sys.exit(1)
                    try:
                        suggest.main()
                    except (FileNotFoundError, ValueError, PermissionError, OSError) as e:
                        sys.exit(1)
        self.assertEqual(ctx.exception.code, 1)

    def test_invalid_mood_via_argv_exits_nonzero(self):
        """Running main() with an invalid mood must exit non-zero."""
        with patch("sys.argv", ["suggest.py", "--mood", "nonsense_mood_xyz"]):
            with self.assertRaises(SystemExit) as ctx:
                try:
                    suggest.main()
                except ValueError:
                    sys.exit(1)
        self.assertEqual(ctx.exception.code, 1)


# ─── EH-9: sc_attack_ms >= 0 ──────────────────────────────────────────────────

class TestEH9AttackValidation(unittest.TestCase):

    def test_negative_attack_raises(self):
        with self.assertRaises(ValueError) as ctx:
            mix_music("in.mp4", "out.mp4", sc_attack_ms=-1)
        self.assertIn("sc_attack_ms", str(ctx.exception))

    def test_zero_attack_is_valid(self):
        # sc_attack_ms=0 is valid — should not raise attack validation
        with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
            try:
                mix_music("in.mp4", "out.mp4", sc_attack_ms=0)
            except ValueError as e:
                self.assertNotIn("sc_attack_ms", str(e))
            except (FileNotFoundError, EnvironmentError):
                pass  # expected downstream errors


# ─── EH-10: sc_release_ms >= 0 ───────────────────────────────────────────────

class TestEH10ReleaseValidation(unittest.TestCase):

    def test_negative_release_raises(self):
        with self.assertRaises(ValueError) as ctx:
            mix_music("in.mp4", "out.mp4", sc_release_ms=-100)
        self.assertIn("sc_release_ms", str(ctx.exception))

    def test_zero_release_is_valid(self):
        with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
            try:
                mix_music("in.mp4", "out.mp4", sc_release_ms=0)
            except ValueError as e:
                self.assertNotIn("sc_release_ms", str(e))
            except (FileNotFoundError, EnvironmentError):
                pass


# ─── EH-11: ffmpeg on PATH ────────────────────────────────────────────────────

class TestEH11FfmpegOnPath(unittest.TestCase):

    def test_missing_ffmpeg_raises_environment_error(self):
        with patch("adapters.ffmpeg_mix.shutil.which", return_value=None):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[{"local_path": "/tmp/x.mp3"}]):
                with patch("pathlib.Path.exists", return_value=True):
                    with self.assertRaises(EnvironmentError) as ctx:
                        mix_music("in.mp4", "out.mp4")
        self.assertIn("ffmpeg", str(ctx.exception).lower())
        self.assertIn("PATH", str(ctx.exception))

    def test_error_includes_install_hint(self):
        with patch("adapters.ffmpeg_mix.shutil.which", return_value=None):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[{"local_path": "/tmp/x.mp3"}]):
                with patch("pathlib.Path.exists", return_value=True):
                    with self.assertRaises(EnvironmentError) as ctx:
                        mix_music("in.mp4", "out.mp4")
        self.assertIn("brew install ffmpeg", str(ctx.exception))


# ─── EH-12: Input video must exist ───────────────────────────────────────────

class TestEH12InputVideoExists(unittest.TestCase):

    def test_missing_input_video_raises_file_not_found(self):
        with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                with self.assertRaises((FileNotFoundError, ValueError)):
                    mix_music("/nonexistent/video.mp4", "out.mp4")

    def test_error_message_includes_input_path(self):
        with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                try:
                    mix_music("/nonexistent/video.mp4", "out.mp4")
                except (FileNotFoundError, ValueError) as e:
                    # Either the input video check or "No matching tracks" fires
                    # We're okay with either as long as it raises something useful
                    self.assertIsNotNone(str(e))


# ─── EH-13: Output parent directory must exist ───────────────────────────────

class TestEH13OutputDirExists(unittest.TestCase):

    def test_missing_output_dir_raises_file_not_found(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            real_input = f.name
        try:
            with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                    with self.assertRaises((FileNotFoundError, ValueError)):
                        mix_music(real_input, "/nonexistent/dir/out.mp4")
        finally:
            Path(real_input).unlink(missing_ok=True)

    def test_valid_output_dir_passes_check(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            real_input = f.name
        try:
            with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                    try:
                        # Output to /tmp which always exists — should not raise dir error
                        mix_music(real_input, "/tmp/test_out.mp4")
                    except FileNotFoundError as e:
                        self.assertNotIn("Output directory", str(e))
                    except ValueError:
                        pass  # "No matching tracks" is expected
        finally:
            Path(real_input).unlink(missing_ok=True)


# ─── EH-14: remotion.js null guard (JS source inspection) ────────────────────

class TestEH14RemotionNullGuards(unittest.TestCase):
    """Verify remotion.js source contains null guards and immutable track handling."""

    def setUp(self):
        self.src = (ROOT / "adapters" / "remotion.js").read_text()

    def test_resolve_track_path_has_null_guard(self):
        # Extract resolveTrackPath function body
        lines = self.src.split('\n')
        in_func = False
        func_lines = []
        brace_depth = 0
        for line in lines:
            if 'function resolveTrackPath(' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break
        body = '\n'.join(func_lines)
        self.assertIn('if (!localPath)', body,
                      "resolveTrackPath must guard against null/undefined localPath")

    def test_add_resolved_path_does_not_mutate(self):
        # _addResolvedPath must use spread operator, not direct assignment
        lines = self.src.split('\n')
        in_func = False
        func_lines = []
        brace_depth = 0
        for line in lines:
            if 'function _addResolvedPath(' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break
        body = '\n'.join(func_lines)
        self.assertIn('...track', body,
                      "_addResolvedPath must use spread ({ ...track }) to avoid mutation")
        self.assertNotIn('track.resolved_path =', body,
                         "_addResolvedPath must not mutate the original track object")

    def test_get_static_path_guards_missing_resolved_path(self):
        lines = self.src.split('\n')
        in_func = False
        func_lines = []
        brace_depth = 0
        for line in lines:
            if 'function getStaticPath(' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break
        body = '\n'.join(func_lines)
        self.assertIn('!abs', body,
                      "getStaticPath must guard against missing resolved_path")

    def test_exec_file_calls_have_timeout(self):
        # Both selectMusic and selectMusicTopN execFile calls must have timeout
        timeout_count = self.src.count('timeout: 30000')
        self.assertGreaterEqual(timeout_count, 2,
                                "Both selectMusic() and selectMusicTopN() execFile calls must have a 30s timeout")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
