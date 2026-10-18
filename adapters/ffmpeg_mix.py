#!/usr/bin/env python3
"""
music-selector — FFmpeg adapter
================================
Overlay the best-matching background music onto a video file,
with real sidechain compression so music ducks cleanly under a speaker's voice.

CLI:
    python adapters/ffmpeg_mix.py input.mp4 output.mp4 --mood energetic --duration 30
    python adapters/ffmpeg_mix.py input.mp4 output.mp4 --platform tiktok --volume 0.12
    python adapters/ffmpeg_mix.py input.mp4 output.mp4 --transcript "AI automation tips"
    python adapters/ffmpeg_mix.py input.mp4 output.mp4 --no-sidechain   # static mix only
    python adapters/ffmpeg_mix.py input.mp4 output.mp4 --dry-run        # print FFmpeg cmd only

Import:
    from adapters.ffmpeg_mix import mix_music, build_filter_complex
    mix_music("input.mp4", "output.mp4", mood="energetic", duration=30)

How sidechain ducking works:
    The speaker's voice audio is split into two streams:
      [voice_out]  → passes through to the final mix as-is
      [voice_sc]   → used as the "key" signal to trigger compression on the music
    When voice_sc exceeds the threshold, sidechaincompress reduces the music volume
    dynamically. When the speaker pauses, music fades back up over `release_ms`.

    This is real dynamic compression — not a static volume reduction.

Requirements:
    ffmpeg must be on PATH  (brew install ffmpeg)
    sidechaincompress requires FFmpeg built with --enable-libavfilter (standard in most builds)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add parent dir so suggest.py is importable from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suggest import suggest_music  # noqa: E402

# Sidechain defaults — tuned for speech-over-music
SC_THRESHOLD = 0.02     # voice amplitude that triggers ducking (~-34 dB)
SC_RATIO     = 8.0      # compression ratio: 8:1 is aggressive, clean ducking
SC_ATTACK_MS = 100      # ms before music starts ducking after voice detected
SC_RELEASE_MS = 1000    # ms for music to fade back up after voice stops

AUDIO_EXTENSIONS = {".mp3", ".aac", ".wav", ".flac", ".m4a", ".ogg", ".opus"}


def build_filter_complex(
    volume: float,
    use_sidechain: bool,
    sc_threshold: float,
    sc_ratio: float,
    sc_attack_ms: int,
    sc_release_ms: int,
) -> str:
    """
    Build the FFmpeg -filter_complex string.

    Sidechain mode (default):
        Voice is split — one copy goes to output, the other keys the compressor.
        Music is compressed dynamically: loud voice → quieter music.
        When voice pauses, music smoothly rises back over release_ms.

    Static mode (--no-sidechain):
        Simple amix with fixed music volume. No dynamic response to voice.
        Use this if the video has no spoken audio.

    Args:
        volume:        Music volume scalar (0.0–1.0)
        use_sidechain: True = real sidechain ducking, False = static mix
        sc_threshold:  Voice amplitude that triggers ducking (0.0–1.0)
        sc_ratio:      Compression ratio — higher = more aggressive duck
        sc_attack_ms:  Time in ms before ducking starts
        sc_release_ms: Time in ms for music to restore after voice stops

    Returns:
        filter_complex string ready for ffmpeg -filter_complex
    """
    if use_sidechain:
        return (
            # Split voice: [voice_out] to final mix, [voice_sc] as compressor key
            "[0:a]aformat=fltp,asplit=2[voice_out][voice_sc];"
            # Prep music at target volume
            f"[1:a]aformat=fltp,volume={volume}[music_in];"
            # Sidechain compress: music ducked by voice
            # [signal][sidechain]sidechaincompress
            # detection=peak: triggers on instantaneous amplitude peaks (voice transients),
            # not RMS average power — critical for accurate speech detection
            f"[music_in][voice_sc]sidechaincompress="
            f"threshold={sc_threshold}:"
            f"ratio={sc_ratio}:"
            f"detection=peak:"
            f"attack={sc_attack_ms}:"
            f"release={sc_release_ms}"
            "[music_ducked];"
            # Final mix: original voice + sidechain-ducked music
            "[voice_out][music_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        return (
            f"[0:a]volume=1.0[orig];"
            f"[1:a]volume={volume}[music];"
            "[orig][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )


def resolve_music_path(local_path: str) -> Path:
    """Resolve a track's local_path (relative or absolute) to an absolute Path."""
    p = Path(local_path)
    if p.is_absolute():
        return p
    # Relative paths are relative to the library directory (parent of adapters/)
    lib_dir = Path(__file__).resolve().parent.parent
    return lib_dir / p


def mix_music(
    input_video: str,
    output_video: str,
    volume: float = 0.15,
    use_sidechain: bool = True,
    sc_threshold: float = SC_THRESHOLD,
    sc_ratio: float = SC_RATIO,
    sc_attack_ms: int = SC_ATTACK_MS,
    sc_release_ms: int = SC_RELEASE_MS,
    dry_run: bool = False,
    **suggest_kwargs,
) -> dict:
    """
    Select the best music track and mix it into a video with FFmpeg.

    By default, uses sidechain compression so the music automatically ducks
    under the speaker's voice and returns when they stop talking.

    Args:
        input_video:    Path to the source video (any FFmpeg-supported format)
        output_video:   Path for the output file (.mp4 recommended)
        volume:         Background music volume scalar, 0.0–1.0 (default 0.15)
        use_sidechain:  True = real dynamic sidechain ducking (default)
                        False = static volume mix (use for music-only videos)
        sc_threshold:   Voice amplitude that triggers ducking, 0.0–1.0 (default 0.02 ≈ -34 dB)
        sc_ratio:       Compression ratio, e.g. 8.0 = 8:1 (default 8.0)
        sc_attack_ms:   ms before ducking starts after voice detected (default 100)
        sc_release_ms:  ms for music to restore after voice stops (default 1000)
        dry_run:        Print the FFmpeg command without executing it
        **suggest_kwargs: Passed to suggest_music()
                          (mood, energy, duration, platform, content_type, pacing, transcript)

    Returns:
        The selected track dict with extra fields:
          output_path, use_sidechain, filter_complex, dry_run (if applicable)
    """
    if not (0.0 <= volume <= 1.0):
        raise ValueError(f"volume must be 0.0–1.0, got {volume}")
    if sc_ratio < 1.0:
        raise ValueError(f"sc_ratio must be >= 1.0, got {sc_ratio}")
    if sc_threshold <= 0 or sc_threshold >= 1:
        raise ValueError(f"sc_threshold must be in (0.0, 1.0) exclusive, got {sc_threshold}")
    if sc_attack_ms < 0:
        raise ValueError(f"sc_attack_ms must be >= 0, got {sc_attack_ms}")
    if sc_release_ms < 0:
        raise ValueError(f"sc_release_ms must be >= 0, got {sc_release_ms}")
    if not shutil.which("ffmpeg"):
        raise EnvironmentError(
            "ffmpeg not found on PATH. Install it first: brew install ffmpeg"
        )
    input_path = Path(input_video)
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")
    output_path = Path(output_video)
    if not output_path.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {output_path.parent}. Create it first."
        )

    tracks = suggest_music(top_n=1, **suggest_kwargs)
    if not tracks:
        raise ValueError("No matching tracks found in library. Check your library.json filters.")

    track = tracks[0]
    music_path = resolve_music_path(track["local_path"])

    if not music_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {music_path}\n"
            "Add the track file to the tracks/ directory or update local_path in library.json.\n"
            "Run: python suggest.py --scan  to see all unregistered files."
        )

    filter_complex = build_filter_complex(
        volume=volume,
        use_sidechain=use_sidechain,
        sc_threshold=sc_threshold,
        sc_ratio=sc_ratio,
        sc_attack_ms=sc_attack_ms,
        sc_release_ms=sc_release_ms,
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(output_video),
    ]

    mode_label = "sidechain duck" if use_sidechain else "static mix"
    print(f"Selected: [{track['score']:.0%}] {track['title']} — {track['artist']}")
    print(f"Music:    {music_path}")
    print(f"Mode:     {mode_label}  |  volume={volume}  "
          + (f"threshold={sc_threshold}  ratio={sc_ratio}:1  "
             f"attack={sc_attack_ms}ms  release={sc_release_ms}ms"
             if use_sidechain else ""))

    result_meta = {
        **track,
        "output_path": str(output_video),
        "use_sidechain": use_sidechain,
        "filter_complex": filter_complex,
    }

    if dry_run:
        print("\nDry run — FFmpeg command:")
        print(" ".join(cmd))
        return {**result_meta, "dry_run": True}

    print(f"Mixing → {output_video}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{proc.stderr}")

    print("Done.")
    return result_meta


def main():
    parser = argparse.ArgumentParser(
        description="Overlay background music onto a video with voice sidechain ducking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Sidechain ducking (default) — music ducks under speaker's voice:
  python adapters/ffmpeg_mix.py input.mp4 output.mp4 --mood energetic --duration 30
  python adapters/ffmpeg_mix.py input.mp4 output.mp4 --platform tiktok --volume 0.12

  # Tune the sidechain — more sensitive trigger, slower release:
  python adapters/ffmpeg_mix.py input.mp4 out.mp4 --sc-threshold 0.01 --sc-release 1500

  # Static mix (no sidechain) — for music-only or b-roll:
  python adapters/ffmpeg_mix.py input.mp4 output.mp4 --no-sidechain --volume 0.2

  # Transcript-based selection:
  python adapters/ffmpeg_mix.py input.mp4 output.mp4 --transcript "AI tools tutorial"

  # Dry run — see the FFmpeg command without running it:
  python adapters/ffmpeg_mix.py input.mp4 output.mp4 --mood calm --dry-run
""",
    )
    parser.add_argument("input",  help="Input video path")
    parser.add_argument("output", help="Output video path")

    # Music selection
    parser.add_argument("--mood",         help="energetic | calm | inspiring | dramatic | uplifting | happy | focused")
    parser.add_argument("--energy",       type=float, help="0.0 to 1.0")
    parser.add_argument("--duration",     type=float, help="Video duration in seconds")
    parser.add_argument("--platform",     help="instagram | tiktok | youtube | linkedin | twitter")
    parser.add_argument("--content-type", dest="content_type",
                        help="viral_short | reels | tutorial | product_demo | dev_vlog | ...")
    parser.add_argument("--pacing",       help="slow | medium | fast | very_fast")
    parser.add_argument("--transcript",   help="Video transcript (auto-infers mood/energy)")
    parser.add_argument("--trending",     action="store_true", help="Prefer trending tracks")

    # Mix / sidechain options
    parser.add_argument("--volume",        type=float, default=0.15,
                        help="Background music volume 0.0–1.0 (default 0.15)")
    parser.add_argument("--no-sidechain",  action="store_true",
                        help="Use static volume mix instead of sidechain ducking")
    parser.add_argument("--sc-threshold",  type=float, default=SC_THRESHOLD,
                        help=f"Voice amplitude that triggers ducking, 0–1 (default {SC_THRESHOLD})")
    parser.add_argument("--sc-ratio",      type=float, default=SC_RATIO,
                        help=f"Compression ratio (default {SC_RATIO} = 8:1)")
    parser.add_argument("--sc-attack",     type=int, default=SC_ATTACK_MS,
                        help=f"ms before ducking starts (default {SC_ATTACK_MS})")
    parser.add_argument("--sc-release",    type=int, default=SC_RELEASE_MS,
                        help=f"ms for music to restore after voice stops (default {SC_RELEASE_MS})")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Print FFmpeg command, don't run")

    args = parser.parse_args()

    track = mix_music(
        input_video=args.input,
        output_video=args.output,
        volume=args.volume,
        use_sidechain=not args.no_sidechain,
        sc_threshold=args.sc_threshold,
        sc_ratio=args.sc_ratio,
        sc_attack_ms=args.sc_attack,
        sc_release_ms=args.sc_release,
        dry_run=args.dry_run,
        mood=args.mood,
        energy=args.energy,
        duration=args.duration,
        platform=args.platform,
        content_type=args.content_type,
        pacing=args.pacing,
        transcript=args.transcript,
        trending_only=args.trending,
    )
    if not args.dry_run:
        print(f"\nTrack used: {track['id']} (score: {track['score']:.3f})")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, EnvironmentError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
