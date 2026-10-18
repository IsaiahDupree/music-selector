"""
Regression tests for the 7 bugs found in the code audit.

Each test is named after the bug it guards against so a future failure
immediately identifies which bug has been reintroduced.

Bugs:
  BUG-1: suggest_music docstring placed after validation — help() returns nothing
  BUG-2: sidechaincompress missing detection=peak — wrong ducking behavior
  BUG-3: selectMusic() fake async — blocks event loop (JS, verified by code inspection)
  BUG-4: getStaticPath() off-by-one path slice — wrong Remotion staticFile() path
  BUG-5: sc_threshold validation message contradicts exclusive bounds
  BUG-6: _infer_from_transcript substring match — "fun" matches "function"
  BUG-7: _print_results references supabase_url — personal field leaked

Run: python3 -m pytest tests/test_bug_regressions.py -v
"""

import inspect
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import suggest
from adapters.ffmpeg_mix import build_filter_complex, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS


# ─── BUG-1: Docstring placement ───────────────────────────────────────────────

class TestBug1DocstringPlacement(unittest.TestCase):
    """suggest_music.__doc__ must not be None.
    Python only assigns __doc__ when the string literal is the FIRST statement."""

    def test_suggest_music_has_docstring(self):
        self.assertIsNotNone(
            suggest.suggest_music.__doc__,
            "suggest_music.__doc__ is None — docstring is placed after code, not as first statement"
        )

    def test_suggest_music_docstring_is_nonempty(self):
        doc = suggest.suggest_music.__doc__ or ""
        self.assertGreater(len(doc.strip()), 0)

    def test_suggest_music_docstring_mentions_mood(self):
        doc = suggest.suggest_music.__doc__ or ""
        self.assertIn("mood", doc.lower(),
                      "Docstring should document the 'mood' parameter")

    def test_suggest_music_docstring_mentions_returns(self):
        doc = suggest.suggest_music.__doc__ or ""
        self.assertIn("return", doc.lower(),
                      "Docstring should document what the function returns")

    def test_docstring_is_first_statement(self):
        """Verify no executable code appears before the docstring in the function body.
        __doc__ being non-None is the definitive proof — Python only sets it when
        the string literal is the first statement.  This test double-checks by confirming
        that 'if energy' (the first validation line) does NOT appear before the docstring
        in the raw source."""
        source = inspect.getsource(suggest.suggest_music)
        doc = suggest.suggest_music.__doc__ or ""
        # The docstring content must appear earlier in the source than the first if-guard
        doc_pos = source.find(doc.strip()[:40])   # first 40 chars of docstring
        if_pos  = source.find("if energy is not None")
        self.assertNotEqual(doc_pos, -1, "Could not locate docstring in source")
        self.assertNotEqual(if_pos,  -1, "Could not locate validation code in source")
        self.assertLess(doc_pos, if_pos,
                        "Docstring must appear BEFORE the validation code in the function body")


# ─── BUG-2: sidechaincompress must use detection=peak ─────────────────────────

class TestBug2SidechainDetectionMode(unittest.TestCase):
    """detection=peak is required for voice transient detection.
    Without it FFmpeg defaults to RMS which responds to sustained noise, not voice."""

    def test_sidechain_filter_has_detection_peak(self):
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertIn("detection=peak", fc,
                      "sidechaincompress must specify detection=peak for voice ducking")

    def test_detection_peak_appears_before_attack(self):
        # detection= must be set before attack/release for correct FFmpeg parsing
        fc = build_filter_complex(0.15, True, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        det_pos = fc.index("detection=peak")
        att_pos = fc.index("attack=")
        self.assertLess(det_pos, att_pos)

    def test_static_mode_does_not_add_detection(self):
        fc = build_filter_complex(0.15, False, SC_THRESHOLD, SC_RATIO, SC_ATTACK_MS, SC_RELEASE_MS)
        self.assertNotIn("detection=", fc)


# ─── BUG-3: selectMusic() must be truly async (JS — inspected via source) ─────

class TestBug3AsyncAdapter(unittest.TestCase):
    """Verify remotion.js uses execFile (async), not execFileSync for selectMusic()."""

    def setUp(self):
        self.remotion_src = (ROOT / "adapters" / "remotion.js").read_text()

    def test_selectMusic_uses_execFile_not_execFileSync(self):
        # Extract the selectMusic function body
        # It must use execFile (callback-based) not execFileSync (blocking)
        # Find selectMusic function definition
        lines = self.remotion_src.split('\n')
        in_select_music = False
        func_lines = []
        brace_depth = 0

        for line in lines:
            if 'function selectMusic(' in line and 'Sync' not in line and 'TopN' not in line:
                in_select_music = True
            if in_select_music:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break

        func_body = '\n'.join(func_lines)
        self.assertIn('execFile(', func_body,
                      "selectMusic() must use async execFile(), not execFileSync()")
        self.assertNotIn('execFileSync(', func_body,
                         "selectMusic() must NOT use execFileSync() — it blocks the event loop")

    def test_selectMusic_returns_promise(self):
        lines = self.remotion_src.split('\n')
        in_select_music = False
        func_lines = []
        brace_depth = 0

        for line in lines:
            if 'function selectMusic(' in line and 'Sync' not in line and 'TopN' not in line:
                in_select_music = True
            if in_select_music:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break

        func_body = '\n'.join(func_lines)
        self.assertIn('new Promise(', func_body,
                      "selectMusic() must return a new Promise for true async behavior")

    def test_selectMusicSync_still_uses_execFileSync(self):
        # selectMusicSync() is intentionally blocking — should still use execFileSync
        lines = self.remotion_src.split('\n')
        in_func = False
        func_lines = []
        brace_depth = 0

        for line in lines:
            if 'function selectMusicSync(' in line:
                in_func = True
            if in_func:
                func_lines.append(line)
                brace_depth += line.count('{') - line.count('}')
                if brace_depth == 0 and func_lines:
                    break

        func_body = '\n'.join(func_lines)
        self.assertIn('execFileSync(', func_body,
                      "selectMusicSync() should use execFileSync() — it's intentionally blocking")


# ─── BUG-4: getStaticPath() off-by-one ───────────────────────────────────────

class TestBug4GetStaticPath(unittest.TestCase):
    """getStaticPath() must use path.relative(), not manual slice."""

    def setUp(self):
        self.remotion_src = (ROOT / "adapters" / "remotion.js").read_text()

    def test_getStaticPath_uses_path_relative(self):
        # Extract the getStaticPath function
        lines = self.remotion_src.split('\n')
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

        func_body = '\n'.join(func_lines)
        self.assertIn('path.relative(', func_body,
                      "getStaticPath() must use path.relative() to avoid off-by-one slice bugs")

    def test_getStaticPath_does_not_use_manual_slice(self):
        lines = self.remotion_src.split('\n')
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

        func_body = '\n'.join(func_lines)
        # The old bug: abs.slice(pubAbs.length + 1) — manual arithmetic prone to off-by-one
        self.assertNotIn('.slice(pubAbs.length + 1)', func_body,
                         "getStaticPath() must not use .slice(pubAbs.length + 1) — use path.relative()")

    def test_error_messages_include_library_path(self):
        # BUG-3/6 also: error messages must include the library path for debuggability
        self.assertIn('_libPath()', self.remotion_src,
                      "Error messages must include the library path via _libPath()")


# ─── BUG-5: sc_threshold error message matches exclusive bounds ───────────────

class TestBug5ThresholdValidationMessage(unittest.TestCase):
    """Error message must say (0.0, 1.0) exclusive, matching what the code actually enforces."""

    def _get_error(self, threshold):
        try:
            from adapters.ffmpeg_mix import mix_music
            with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
                mix_music("in.mp4", "out.mp4", sc_threshold=threshold)
        except ValueError as e:
            return str(e)
        return None

    def test_threshold_zero_raises_with_exclusive_message(self):
        msg = self._get_error(0.0)
        self.assertIsNotNone(msg)
        # Message must not say "0 and 1" (implies inclusive) — must say exclusive
        self.assertIn("exclusive", msg.lower(),
                      f"Error message should clarify bounds are exclusive, got: {msg}")

    def test_threshold_one_raises_with_exclusive_message(self):
        msg = self._get_error(1.0)
        self.assertIsNotNone(msg)
        self.assertIn("exclusive", msg.lower())

    def test_valid_threshold_does_not_raise_threshold_error(self):
        # 0.02 is a valid threshold — must not raise a threshold-related ValueError
        # (other ValueErrors like "No matching tracks" are expected and acceptable)
        from adapters.ffmpeg_mix import mix_music
        with patch("adapters.ffmpeg_mix.suggest_music", return_value=[]):
            try:
                mix_music("in.mp4", "out.mp4", sc_threshold=0.02)
            except ValueError as e:
                msg = str(e)
                self.assertNotIn("sc_threshold", msg,
                                 f"Valid threshold 0.02 triggered threshold validation: {msg}")
            except (FileNotFoundError, RuntimeError):
                pass  # expected — no real tracks/video


# ─── BUG-6: Transcript word-boundary matching ─────────────────────────────────

class TestBug6TranscriptWordBoundary(unittest.TestCase):
    """_infer_from_transcript must match whole words, not substrings."""

    def test_fun_does_not_match_function(self):
        # Old bug: "fun" in "function" → True, inflating happy score
        result = suggest._infer_from_transcript("this is a function that builds software")
        # "function" should NOT trigger "fun" keyword
        # "build" SHOULD trigger "inspiring"
        # So mood should be inspiring or energetic/dramatic, NOT happy
        self.assertNotEqual(result["mood"], "happy",
                            "'function' should not match keyword 'fun'")

    def test_win_does_not_match_window(self):
        result = suggest._infer_from_transcript("open the window and look outside")
        # "window" must not trigger "win" keyword
        # No strong mood signals → should fall to "uplifting" default
        self.assertNotEqual(result["mood"], "happy",
                            "'window' should not match keyword 'win'")

    def test_grow_does_not_match_growth(self):
        # "growth" is an energetic keyword; "grow" is an inspiring keyword
        # They are different words — the word set approach should handle this:
        # "growth" → words = {"growth"}, "growth" in inspiring → No (keyword is "grow")
        # "growth" → words = {"growth"}, "growth" in energetic → Yes (keyword is "growth")
        result = suggest._infer_from_transcript("I saw tremendous growth this quarter")
        self.assertEqual(result["mood"], "energetic",
                         "'growth' should match energetic keyword 'growth', not inspiring 'grow'")

    def test_actual_fun_word_still_matches(self):
        result = suggest._infer_from_transcript("this is so fun and happy")
        self.assertEqual(result["mood"], "happy",
                         "The actual word 'fun' should still trigger happy mood")

    def test_actual_win_word_still_matches(self):
        result = suggest._infer_from_transcript("we win and celebrate and smile")
        self.assertEqual(result["mood"], "happy",
                         "The actual word 'win' should still trigger happy mood")

    def test_empty_string_no_crash(self):
        result = suggest._infer_from_transcript("")
        self.assertIn("mood", result)
        self.assertIn("energy", result)

    def test_punctuation_does_not_prevent_matching(self):
        # "fun!" should still match "fun"
        result = suggest._infer_from_transcript("this is so fun! happy times!")
        self.assertEqual(result["mood"], "happy")


# ─── BUG-7: No supabase_url in _print_results output ─────────────────────────

class TestBug7NoSupabaseUrl(unittest.TestCase):
    """_print_results must not reference supabase_url — personal field."""

    def test_print_results_source_has_no_supabase_url(self):
        source = inspect.getsource(suggest._print_results)
        self.assertNotIn("supabase_url", source,
                         "_print_results must not reference supabase_url (personal/private field)")

    def test_suggest_py_source_has_no_supabase_url_references(self):
        source_path = ROOT / "suggest.py"
        source = source_path.read_text()
        self.assertNotIn("supabase_url", source,
                         "suggest.py must not contain any supabase_url references")

    def test_library_json_has_no_supabase_urls(self):
        lib_src = (ROOT / "library.json").read_text()
        self.assertNotIn("supabase.co", lib_src,
                         "library.json must not contain supabase.co URLs")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
