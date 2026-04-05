#!/usr/bin/env python3
"""
Music Suggester — Universal Music Recommendation
================================================
Standalone CLI + importable module.
Zero external dependencies. Works from any project.

CLI:
    python suggest.py --mood energetic --energy 0.8 --duration 30
    python suggest.py --transcript "amazing AI automation tips" --platform tiktok
    python suggest.py --platform instagram --content-type viral_short --top 3
    python suggest.py --list

Import:
    import sys; sys.path.insert(0, "/path/to/music-selector")
    from suggest import suggest_music, load_library

    results = suggest_music(mood="energetic", energy=0.8, duration=30)
    for r in results:
        print(r["score"], r["title"], r["local_path"])

Library path override via env:
    MUSIC_INDEX_PATH=/custom/path/library.json python suggest.py --list
"""

import json
import os
import re
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

# Override with MUSIC_INDEX_PATH env var to use a custom library location
LIBRARY_PATH = Path(os.environ.get("MUSIC_INDEX_PATH", Path(__file__).parent / "library.json"))

AUDIO_EXTENSIONS = {".mp3", ".aac", ".wav", ".flac", ".m4a", ".ogg", ".opus"}

VALID_MOODS = {
    "energetic", "calm", "inspiring", "dramatic", "uplifting", "happy", "focused",
}
VALID_PACINGS = {"slow", "medium", "fast", "very_fast"}

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "mood":         0.30,
    "energy":       0.25,
    "duration":     0.20,
    "pacing":       0.15,
    "content_type": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, f"WEIGHTS must sum to 1.0, got {sum(WEIGHTS.values())}"


def load_library() -> Dict[str, Any]:
    if not LIBRARY_PATH.exists():
        raise FileNotFoundError(
            f"Music library.json not found at {LIBRARY_PATH}. "
            "Copy library.template.json → library.json and populate it with your tracks. "
            "Or set MUSIC_INDEX_PATH=/path/to/library.json"
        )
    try:
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except PermissionError:
        raise PermissionError(
            f"No read permission for {LIBRARY_PATH}. "
            "Check file permissions: chmod 644 library.json"
        )
    except OSError as e:
        raise OSError(f"Could not read {LIBRARY_PATH}: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"library.json is malformed: {e}") from e
    if "tracks" not in data:
        raise ValueError("library.json missing 'tracks' key")
    return data


def _score_mood(track: Dict, mood: Optional[str], compat_map: Dict) -> float:
    if not mood:
        return 0.5
    if track.get("mood") == mood:
        return 1.0
    if mood in track.get("moods", []):
        return 0.9
    compatible = compat_map.get(mood, [])
    if track.get("mood") in compatible or any(m in compatible for m in track.get("moods", [])):
        return 0.65
    return 0.2


def _score_energy(track: Dict, energy: Optional[float]) -> float:
    if energy is None:
        return 0.5
    track_energy = track.get("energy_level")
    if track_energy is None:
        return 0.5
    diff = abs(energy - track_energy)
    return max(0.0, 1.0 - diff)


def _score_duration(track: Dict, duration: Optional[float]) -> float:
    if not duration or not track.get("duration_sec"):
        return 0.5
    ratio = track["duration_sec"] / duration
    if 0.8 <= ratio <= 1.5:
        return 1.0
    if 0.5 <= ratio <= 2.5:
        return 0.7
    return 0.3


def _score_pacing(track: Dict, pacing: Optional[str]) -> float:
    if not pacing:
        return 0.5
    bpm = track.get("bpm")
    tempo = track.get("tempo", "")
    pacing_ranges = {
        "slow":      (60, 95),
        "medium":    (90, 135),
        "fast":      (130, 185),
        "very_fast": (180, 999),
    }
    tempo_matches = {
        "slow":        ["slow"],
        "medium":      ["medium", "medium-fast"],
        "fast":        ["fast", "medium-fast"],
        "very_fast":   ["fast"],
    }
    if bpm:
        lo, hi = pacing_ranges.get(pacing, (90, 135))
        if lo <= bpm <= hi:
            return 1.0
        if lo - 25 <= bpm <= hi + 25:
            return 0.65
        return 0.3
    if tempo in tempo_matches.get(pacing, []):
        return 0.8
    return 0.4


def _score_content_type(track: Dict, content_type: Optional[str], ct_map: Dict) -> float:
    if not content_type:
        return 0.5
    if content_type in track.get("suitable_for", []):
        return 1.0
    ct_info = ct_map.get(content_type, {})
    preferred_genres = ct_info.get("preferred_genres", [])
    if track.get("genre") in preferred_genres:
        return 0.75
    return 0.3


def _infer_from_transcript(transcript: str) -> Dict[str, Any]:
    """Heuristic mood/energy inference from transcript text."""
    text = transcript.lower()
    # Use word-set matching to avoid substring false positives
    # e.g. "fun" must not match "function", "win" must not match "window"
    words = set(re.findall(r'[a-z]+', text))

    energetic = ["amazing", "incredible", "exciting", "awesome", "wow", "insane", "fire", "viral", "growth", "results"]
    calm      = ["peaceful", "relaxing", "calm", "gentle", "soft", "slow", "easy", "simple", "basic"]
    happy     = ["happy", "fun", "great", "love", "smile", "celebrate", "success", "win", "best"]
    inspiring = ["inspire", "transform", "journey", "build", "create", "learn", "grow", "achieve", "goal"]
    dramatic  = ["reveal", "shocking", "secret", "truth", "exposed", "never", "mistake", "wrong"]

    counts = {
        "energetic": sum(1 for w in energetic if w in words),
        "calm":      sum(1 for w in calm if w in words),
        "happy":     sum(1 for w in happy if w in words),
        "inspiring": sum(1 for w in inspiring if w in words),
        "dramatic":  sum(1 for w in dramatic if w in words),
    }
    mood = max(counts, key=counts.get)
    if counts[mood] == 0:
        mood = "uplifting"

    energy_boost  = (counts["energetic"] + counts["happy"]) * 0.08
    energy_reduce = counts["calm"] * 0.08
    energy = max(0.2, min(0.95, 0.55 + energy_boost - energy_reduce))

    return {"mood": mood, "energy": round(energy, 2)}


def suggest_music(
    mood: Optional[str] = None,
    energy: Optional[float] = None,
    duration: Optional[float] = None,
    platform: Optional[str] = None,
    content_type: Optional[str] = None,
    pacing: Optional[str] = None,
    transcript: Optional[str] = None,
    top_n: int = 5,
    trending_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Suggest best music tracks for a video.

    Args:
        mood:         Video mood — energetic, calm, inspiring, dramatic, uplifting, happy, focused
        energy:       Energy level 0.0–1.0
        duration:     Video duration in seconds
        platform:     Target platform — instagram, tiktok, youtube, linkedin, twitter
        content_type: Content type — viral_short, reels, tutorial, product_demo, dev_vlog, etc.
        pacing:       Video pacing — slow, medium, fast, very_fast
        transcript:   Raw transcript text (auto-infers mood/energy if mood/energy not set)
        top_n:        Number of results to return
        trending_only: Only return trending tracks

    Returns:
        List of track dicts sorted by score, each with score + score_breakdown added.
    """
    # Input validation
    if energy is not None and not (0.0 <= energy <= 1.0):
        raise ValueError(f"energy must be 0.0–1.0, got {energy}")
    if top_n < 1:
        raise ValueError(f"top_n must be >= 1, got {top_n}")
    if duration is not None and duration <= 0:
        raise ValueError(f"duration must be > 0 seconds, got {duration}")
    if mood is not None and mood not in VALID_MOODS:
        raise ValueError(
            f"Unknown mood '{mood}'. Valid moods: {sorted(VALID_MOODS)}"
        )
    if pacing is not None and pacing not in VALID_PACINGS:
        raise ValueError(
            f"Unknown pacing '{pacing}'. Valid options: {sorted(VALID_PACINGS)}"
        )
    lib = load_library()
    tracks = lib["tracks"]
    ct_map = lib.get("content_type_map", {})
    platform_map = lib.get("platform_map", {})
    compat_map = lib.get("mood_compatibility", {})

    # Auto-infer content_type from platform if not set
    if platform and not content_type:
        preferred = platform_map.get(platform, [])
        content_type = preferred[0] if preferred else None

    # Auto-infer mood/energy from transcript
    if transcript and (mood is None or energy is None):
        inferred = _infer_from_transcript(transcript)
        mood = mood or inferred["mood"]
        energy = energy if energy is not None else inferred["energy"]

    results = []
    for track in tracks:
        if trending_only and not track.get("is_trending"):
            continue

        mood_s    = _score_mood(track, mood, compat_map)
        energy_s  = _score_energy(track, energy)
        dur_s     = _score_duration(track, duration)
        pacing_s  = _score_pacing(track, pacing)
        ct_s      = _score_content_type(track, content_type, ct_map)

        score = (
            mood_s    * WEIGHTS["mood"] +
            energy_s  * WEIGHTS["energy"] +
            dur_s     * WEIGHTS["duration"] +
            pacing_s  * WEIGHTS["pacing"] +
            ct_s      * WEIGHTS["content_type"]
        )

        # Bonus: trending track gets +0.05
        if track.get("is_trending"):
            score = min(1.0, score + 0.05)
        # Bonus: platform-trending match
        if platform and platform in track.get("platforms_trending", []):
            score = min(1.0, score + 0.03)

        result = {
            **track,
            "score": round(score, 3),
            "score_breakdown": {
                "mood":         round(mood_s, 3),
                "energy":       round(energy_s, 3),
                "duration":     round(dur_s, 3),
                "pacing":       round(pacing_s, 3),
                "content_type": round(ct_s, 3),
            },
        }
        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def _print_results(results: List[Dict], verbose: bool = False) -> None:
    if not results:
        print("No tracks found.")
        return
    for i, r in enumerate(results, 1):
        local = r.get("local_path", "no local file")
        exists = Path(local).exists() if local != "no local file" else False
        exists_str = "✓" if exists else "✗"
        score = r.get("score", 0.0)
        title = r.get("title", "Unknown Title")
        artist = r.get("artist", "Unknown Artist")
        genre = r.get("genre", "unknown")
        mood = r.get("mood", "unknown")
        energy = r.get("energy_level", "?")
        print(f"\n{i}. [{score:.0%}] {title} — {artist}")
        print(f"   Genre: {genre}  |  Mood: {mood}  |  Energy: {energy}")
        print(f"   File {exists_str}: {local}")
        if verbose:
            bd = r.get("score_breakdown", {})
            print(f"   Breakdown → mood:{bd.get('mood',0):.2f}  energy:{bd.get('energy',0):.2f}  "
                  f"duration:{bd.get('duration',0):.2f}  pacing:{bd.get('pacing',0):.2f}  "
                  f"content:{bd.get('content_type',0):.2f}")


def scan_unregistered(tracks_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Scan the tracks directory for audio files not registered in library.json.

    When you drop a new audio file into tracks/, call this to find out what
    needs to be added to library.json before the selector can pick it.

    Args:
        tracks_dir: Directory to scan. Defaults to tracks/ next to library.json.

    Returns:
        List of dicts, each with:
          path     — absolute path to the unregistered file
          filename — filename only
          stem     — filename without extension (suggested id)
          suffix   — file extension
    """
    lib = load_library()

    # Collect all local_path values registered in the library
    # Normalise to just the filename for comparison, since paths may be relative
    registered_filenames = set()
    for track in lib["tracks"]:
        lp = track.get("local_path", "")
        if lp:
            registered_filenames.add(Path(lp).name)

    if tracks_dir is None:
        tracks_dir = LIBRARY_PATH.parent / lib.get("tracks_dir", "tracks")

    tracks_dir = Path(tracks_dir)
    if not tracks_dir.exists():
        return []

    unregistered = []
    for f in sorted(tracks_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if f.name == ".gitkeep":
            continue
        if f.name not in registered_filenames:
            unregistered.append({
                "path":     str(f.resolve()),
                "filename": f.name,
                "stem":     f.stem,
                "suffix":   f.suffix.lower(),
            })

    return unregistered


def main():
    parser = argparse.ArgumentParser(
        description="Suggest best music for a video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python suggest.py --mood energetic --energy 0.8 --duration 30
  python suggest.py --platform tiktok --content-type viral_short
  python suggest.py --transcript "I built an AI that grows my Instagram automatically"
  python suggest.py --list
  python suggest.py --mood calm --verbose
""",
    )
    parser.add_argument("--mood",         help="energetic, calm, inspiring, dramatic, uplifting, happy, focused")
    parser.add_argument("--energy",       type=float, help="0.0 to 1.0")
    parser.add_argument("--duration",     type=float, help="Video duration in seconds")
    parser.add_argument("--platform",     help="instagram, tiktok, youtube, linkedin, twitter")
    parser.add_argument("--content-type", dest="content_type",
                        help="viral_short, reels, tutorial, product_demo, dev_vlog, storytelling, brand, montage, shorts, background")
    parser.add_argument("--pacing",       help="slow, medium, fast, very_fast")
    parser.add_argument("--transcript",   help="Video transcript text (auto-infers mood/energy)")
    parser.add_argument("--top",          type=int, default=5, dest="top_n", help="Number of results (default: 5)")
    parser.add_argument("--trending",     action="store_true", help="Only trending tracks")
    parser.add_argument("--verbose",      action="store_true", help="Show score breakdown")
    parser.add_argument("--list",         action="store_true", help="List all tracks in library")
    parser.add_argument("--scan",         action="store_true", help="Scan tracks/ for unregistered audio files")
    parser.add_argument("--json",         action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.scan:
        unregistered = scan_unregistered()
        if args.json:
            print(json.dumps(unregistered, indent=2))
        elif not unregistered:
            print("All audio files in tracks/ are registered in library.json.")
        else:
            print(f"\nUnregistered audio files ({len(unregistered)}) — add these to library.json:\n{'='*60}")
            for u in unregistered:
                print(f"  {u['suffix']:<5}  {u['filename']}")
                print(f"         suggested id: \"{u['stem']}\"")
                print(f"         path: {u['path']}")
        return

    if args.list:
        lib = load_library()
        print(f"\nMusic Library — {len(lib['tracks'])} tracks\n{'='*60}")
        for t in lib["tracks"]:
            local = t.get("local_path", "")
            exists = "✓" if Path(local).exists() else "✗"
            trending = " [TRENDING]" if t.get("is_trending") else ""
            print(f"  {exists} {t['id']:<35} {t['genre']:<12} energy:{t['energy_level']:.1f}{trending}")
        return

    results = suggest_music(
        mood=args.mood,
        energy=args.energy,
        duration=args.duration,
        platform=args.platform,
        content_type=args.content_type,
        pacing=args.pacing,
        transcript=args.transcript,
        top_n=args.top_n,
        trending_only=args.trending,
    )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"\nTop {len(results)} music suggestions:")
        _print_results(results, verbose=args.verbose)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, PermissionError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
