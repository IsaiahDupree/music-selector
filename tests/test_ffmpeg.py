"""
Tests for adapters/ffmpeg_mix.py

Covers:
  - build_filter_complex(): sidechain vs static filter graphs
  - Sidechain parameter values appear correctly in the filter string
  - mix_music(): argument validation, file-not-found, no-tracks errors
  - mix_music(): dry_run returns command without subprocess call
  - mix_music(): sidechain ON vs OFF produces different filter strings
  - resolve_music_path(): relative and absolute paths

Run: python3 -m pytest tests/test_ffmpeg.py -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

from adapters.ffmpeg_mix import (  # noqa: E402
    SC_ATTACK_MS,
    SC_RATIO,
    SC_RELEASE_MS,
    SC_THRESHOLD,
    build_filter_complex,
    mix_music,
    resolve_music_path,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_TRACK = {
    "id": "test-track",
    "title": "Test Track",
    "artist": "Test Artist",
    "local_path": "/tmp/test-track.mp3",
    "score": 0.85,
    "score_breakdown": {},
    "genre": "electronic",
    "mood": "energetic",
    "moods": ["energetic"],
    "energy_level": 0.8,
    "is_trending": False,
    "platforms_trending": [],
}


# ─── build_filter_complex ─────────────────────────────────────────────────────

class TestBuildFilterComplex(unittest.TestCase):

    def test_sidechain_mode_contains_sidechaincompress(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("sidechaincompress", fc)

    def test_sidechain_mode_splits_voice(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("asplit=2", fc)
        self.assertIn("voice_out", fc)
        self.assertIn("voice_sc", fc)

    def test_sidechain_signal_is_music_keyed_by_voice(self):
        # [music_in][voice_sc]sidechaincompress — music is signal, voice is key
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("[music_in][voice_sc]sidechaincompress", fc)

    def test_sidechain_threshold_in_filter(self):
        fc = build_filter_complex(0.15, True, 0.03, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("threshold=0.03", fc)

    def test_sidechain_ratio_in_filter(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, 12.0, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("ratio=12.0", fc)

    def test_sidechain_attack_in_filter(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, 200, SC_RELEASE_MS)
        self.assertIn("attack=200", fc)

    def test_sidechain_release_in_filter(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, 1500)
        self.assertIn("release=1500", fc)

    def test_sidechain_music_volume_in_filter(self):
        fc = build_filter_complex(0.12, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("volume=0.12", fc)

    def test_sidechain_has_peak_detection(self):
        # detection=peak is required for voice transient detection (not RMS average)
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("detection=peak", fc)

    def test_static_mode_has_no_detection_param(self):
        fc = build_filter_complex(0.15, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertNotIn("detection=", fc)

    def test_sidechain_final_amix_present(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("amix", fc)
        self.assertIn("[aout]", fc)

    def test_static_mode_has_no_sidechaincompress(self):
        fc = build_filter_complex(0.15, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertNotIn("sidechaincompress", fc)
        self.assertNotIn("asplit", fc)

    def test_static_mode_uses_amix(self):
        fc = build_filter_complex(0.15, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("amix", fc)

    def test_static_mode_music_volume_in_filter(self):
        fc = build_filter_complex(0.20, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("volume=0.2", fc)

    def test_sidechain_and_static_produce_different_filters(self):
        sc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        st = build_filter_complex(0.15, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertNotEqual(sc, st)

    def test_filter_is_string(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIsInstance(fc, str)
        self.assertGreater(len(fc), 0)

    def test_default_sidechain_params_are_sane(self):
        # Defaults should give clean ducking: ratio >= 4, threshold < 0.1, release >= 500
        self.assertGreaterEqual(SC_RATIO, 4.0)
        self.assertLess(SC_THRESHOLD, 0.1)
        self.assertGreaterEqual(SC_RELEASE_MS, 500)
        self.assertLessEqual(SC_ATTACK_MS, 300)


# ─── resolve_music_path ───────────────────────────────────────────────────────

class TestResolveMusicPath(unittest.TestCase):

    def test_absolute_path_returned_as_is(self):
        result = resolve_music_path("/absolute/path/to/track.mp3")
        self.assertEqual(result, Path("/absolute/path/to/track.mp3"))

    def test_relative_path_resolved_from_library_root(self):
        result = resolve_music_path("tracks/my-song.mp3")
        self.assertFalse(result == Path("tracks/my-song.mp3"))  # must be absolute
        self.assertTrue(result.is_absolute())
        self.assertTrue(str(result).endswith("tracks/my-song.mp3"))

    def test_result_is_path_object(self):
        result = resolve_music_path("tracks/test.mp3")
        self.assertIsInstance(result, Path)


# ─── mix_music() validation ───────────────────────────────────────────────────

class TestMixMusicValidation(unittest.TestCase):

    def test_invalid_volume_too_high(self):
        with self.assertRaises(ValueError) as ctx:
            mix_music("in.mp4", "out.mp4", volume=1.5)
        self.assertIn("volume", str(ctx.exception))

    def test_invalid_volume_negative(self):
        with self.assertRaises(ValueError):
            mix_music("in.mp4", "out.mp4", volume=-0.1)

    def test_invalid_sc_ratio_below_one(self):
        with self.assertRaises(ValueError) as ctx:
            mix_music("in.mp4", "out.mp4", sc_ratio=0.5)
        self.assertIn("sc_ratio", str(ctx.exception))

    def test_invalid_sc_threshold_zero(self):
        with self.assertRaises(ValueError):
            mix_music("in.mp4", "out.mp4", sc_threshold=0.0)

    def test_invalid_sc_threshold_one(self):
        with self.assertRaises(ValueError):
            mix_music("in.mp4", "out.mp4", sc_threshold=1.0)

    def test_no_tracks_found_raises_value_error(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_input = f.name
        try:
            with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                    with self.assertRaises(ValueError) as ctx:
                        mix_music(tmp_input, "/tmp/out_test.mp4")
                    self.assertIn("No matching tracks", str(ctx.exception))
        finally:
            Path(tmp_input).unlink(missing_ok=True)

    def test_missing_audio_file_raises_file_not_found(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_input = f.name
        try:
            with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("adapters.ffmpeg_mix.suggest_music", return_value=[MOCK_TRACK]):
                    with self.assertRaises(FileNotFoundError) as ctx:
                        mix_music(tmp_input, "/tmp/out_test.mp4")
                    self.assertIn("Audio file not found", str(ctx.exception))
        finally:
            Path(tmp_input).unlink(missing_ok=True)


# ─── mix_music() dry_run ─────────────────────────────────────────────────────

class TestMixMusicDryRun(unittest.TestCase):

    def _run_dry(self, **kwargs):
        """Run mix_music with dry_run=True against real temp files."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_music = f.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_input = f.name

        track = {**MOCK_TRACK, "local_path": tmp_music}
        with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[track]):
                result = mix_music(tmp_input, "/tmp/test_dry_out.mp4", dry_run=True, **kwargs)

        Path(tmp_music).unlink(missing_ok=True)
        Path(tmp_input).unlink(missing_ok=True)
        return result

    def test_dry_run_does_not_call_subprocess(self):
        with patch("adapters.ffmpeg_mix.subprocess.run") as mock_run:
            self._run_dry()
            mock_run.assert_not_called()

    def test_dry_run_returns_dict_with_filter_complex(self):
        result = self._run_dry()
        self.assertIn("filter_complex", result)
        self.assertIn("output_path", result)
        self.assertTrue(result.get("dry_run"))

    def test_dry_run_sidechain_filter_present(self):
        result = self._run_dry(use_sidechain=True)
        self.assertIn("sidechaincompress", result["filter_complex"])
        self.assertIn("detection=peak", result["filter_complex"])

    def test_dry_run_static_filter_no_sidechain(self):
        result = self._run_dry(use_sidechain=False)
        self.assertNotIn("sidechaincompress", result["filter_complex"])

    def test_dry_run_custom_threshold_in_filter(self):
        result = self._run_dry(use_sidechain=True, sc_threshold=0.05)
        self.assertIn("threshold=0.05", result["filter_complex"])

    def test_dry_run_custom_ratio_in_filter(self):
        result = self._run_dry(use_sidechain=True, sc_ratio=16.0)
        self.assertIn("ratio=16.0", result["filter_complex"])

    def test_dry_run_custom_attack_in_filter(self):
        result = self._run_dry(use_sidechain=True, sc_attack_ms=50)
        self.assertIn("attack=50", result["filter_complex"])

    def test_dry_run_custom_release_in_filter(self):
        result = self._run_dry(use_sidechain=True, sc_release_ms=2000)
        self.assertIn("release=2000", result["filter_complex"])

    def test_dry_run_result_includes_track_metadata(self):
        result = self._run_dry()
        self.assertIn("title", result)
        self.assertIn("score", result)
        self.assertIn("id", result)

    def test_dry_run_use_sidechain_flag_stored(self):
        result_sc = self._run_dry(use_sidechain=True)
        result_st = self._run_dry(use_sidechain=False)
        self.assertTrue(result_sc["use_sidechain"])
        self.assertFalse(result_st["use_sidechain"])


# ─── mix_music() subprocess execution ────────────────────────────────────────

class TestMixMusicExecution(unittest.TestCase):

    def _run_with_mock_proc(self, returncode=0, stderr="", **kwargs):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_music = f.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_input = f.name

        track = {**MOCK_TRACK, "local_path": tmp_music}
        mock_proc = MagicMock()
        mock_proc.returncode = returncode
        mock_proc.stderr = stderr

        with patch("adapters.ffmpeg_mix.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[track]):
                with patch("adapters.ffmpeg_mix.subprocess.run", return_value=mock_proc) as mock_run:
                    if returncode != 0:
                        with self.assertRaises(RuntimeError):
                            mix_music(tmp_input, "/tmp/test_exec_out.mp4", **kwargs)
                        result = None
                    else:
                        result = mix_music(tmp_input, "/tmp/test_exec_out.mp4", **kwargs)
                    call_args = mock_run.call_args

        Path(tmp_music).unlink(missing_ok=True)
        Path(tmp_input).unlink(missing_ok=True)
        return result, call_args

    def test_ffmpeg_called_on_success(self):
        _, call_args = self._run_with_mock_proc()
        self.assertIsNotNone(call_args)
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "ffmpeg")

    def test_ffmpeg_command_includes_sidechain_filter(self):
        _, call_args = self._run_with_mock_proc(use_sidechain=True)
        cmd = call_args[0][0]
        fc_index = cmd.index("-filter_complex")
        filter_str = cmd[fc_index + 1]
        self.assertIn("sidechaincompress", filter_str)

    def test_ffmpeg_command_no_sidechain_in_static_mode(self):
        _, call_args = self._run_with_mock_proc(use_sidechain=False)
        cmd = call_args[0][0]
        fc_index = cmd.index("-filter_complex")
        filter_str = cmd[fc_index + 1]
        self.assertNotIn("sidechaincompress", filter_str)

    def test_ffmpeg_failure_raises_runtime_error(self):
        self._run_with_mock_proc(returncode=1, stderr="some ffmpeg error")

    def test_successful_result_has_output_path(self):
        result, _ = self._run_with_mock_proc()
        self.assertIn("output_path", result)
        self.assertTrue(result["output_path"].endswith(".mp4"))

    def test_successful_result_has_use_sidechain(self):
        result, _ = self._run_with_mock_proc(use_sidechain=True)
        self.assertTrue(result["use_sidechain"])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
