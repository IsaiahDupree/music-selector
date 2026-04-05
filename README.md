# music-selector

Zero-dependency background music recommendation engine for video content creation.

Plug it into **Remotion**, **FFmpeg**, **Adobe Premiere Pro**, or any Python/Node pipeline.
One command picks the best track from your library using a 5-factor weighted scoring engine.

---

## Features

- **5-factor scoring**: mood (30%) · energy (25%) · duration (20%) · pacing/BPM (15%) · content type (10%)
- **Transcript inference**: paste your video script → auto-detects mood and energy level
- **Platform awareness**: Instagram, TikTok, YouTube, LinkedIn, Twitter
- **Trending boost**: +5% bonus for trending tracks, +3% for platform-specific trending
- **JSON output**: pipe into any tool, script, or API
- **Zero dependencies**: pure Python stdlib, no pip installs required
- **Adapters included**: Remotion (JS/TS), FFmpeg (Python CLI), Premiere Pro (ExtendScript)

---

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/music-selector
cd music-selector

# Copy the template and add your tracks
cp library.template.json library.json
# Edit library.json — add your tracks with relative paths like "tracks/my-song.mp3"
# Drop your audio files into tracks/

# Run
python suggest.py --mood energetic --duration 30 --platform tiktok
python suggest.py --transcript "I built an AI that grows my Instagram automatically"
python suggest.py --list
```

---

## CLI Reference

```bash
python suggest.py [options]

Options:
  --mood          energetic | calm | inspiring | dramatic | uplifting | happy | focused
  --energy        0.0 to 1.0
  --duration      Video duration in seconds
  --platform      instagram | tiktok | youtube | linkedin | twitter
  --content-type  viral_short | reels | tutorial | product_demo | dev_vlog |
                  storytelling | brand | montage | shorts | background
  --pacing        slow | medium | fast | very_fast
  --transcript    Raw video transcript (auto-infers mood + energy)
  --top N         Number of results (default: 5)
  --trending      Only return trending tracks
  --verbose       Show score breakdown per dimension
  --json          Output as JSON (for piping)
  --list          List all tracks in library

Environment:
  MUSIC_INDEX_PATH=/path/to/library.json   # Use a custom library location
```

---

## Python API

```python
import sys
sys.path.insert(0, "/path/to/music-selector")
from suggest import suggest_music

# Basic usage
tracks = suggest_music(mood="energetic", energy=0.8, duration=30)
best = tracks[0]
print(best["title"], best["score"], best["local_path"])

# With transcript
tracks = suggest_music(
    transcript="I built an AI automation that doubled my revenue",
    platform="instagram",
    top_n=3,
)

# Trending only
tracks = suggest_music(platform="tiktok", trending_only=True)
```

---

## Remotion Integration

```js
// In your Remotion composition or calculateMetadata()
const { selectMusicSync, getStaticPath } = require('./path/to/music-selector/adapters/remotion');

const track = selectMusicSync({
  mood: 'energetic',
  duration: 30,
  platform: 'tiktok',
});

// If tracks are in Remotion's public/ directory:
import { staticFile, Audio } from 'remotion';
const src = staticFile(getStaticPath(track, 'public'));
// <Audio src={src} volume={0.15} />
```

**Full composition example:**

```tsx
import { Audio, useVideoConfig } from 'remotion';
import { staticFile } from 'remotion';
const { selectMusicSync, getStaticPath } = require('../../music-selector/adapters/remotion');

export const MyVideo: React.FC<{ mood?: string }> = ({ mood = 'energetic' }) => {
  const { durationInFrames, fps } = useVideoConfig();
  const duration = durationInFrames / fps;

  const track = selectMusicSync({ mood, duration, platform: 'tiktok' });

  return (
    <>
      {track && (
        <Audio
          src={staticFile(getStaticPath(track, 'public'))}
          volume={0.15}
        />
      )}
      {/* ...your other composition elements */}
    </>
  );
};
```

---

## FFmpeg Integration

```bash
# Mix best-matching music into a video
python adapters/ffmpeg_mix.py input.mp4 output.mp4 --mood energetic --duration 30
python adapters/ffmpeg_mix.py input.mp4 output.mp4 --platform tiktok --volume 0.12
python adapters/ffmpeg_mix.py input.mp4 output.mp4 --transcript "AI tools tutorial"

# Dry run — print FFmpeg command without executing
python adapters/ffmpeg_mix.py input.mp4 output.mp4 --mood calm --dry-run
```

```python
from adapters.ffmpeg_mix import mix_music

track = mix_music(
    "input.mp4",
    "output.mp4",
    mood="energetic",
    duration=30,
    volume=0.15,
)
print(f"Used: {track['title']} (score: {track['score']:.0%})")
```

---

## Premiere Pro Integration

1. Open Premiere Pro → **File → Scripts → Run Script...**
2. Select `adapters/premiere.jsx`
3. Edit the two config lines at the top of the file:
   ```js
   var MUSIC_SELECTOR_DIR = "/path/to/music-selector";
   var PYTHON3 = "/usr/bin/python3";  // run `which python3` in Terminal
   ```
4. A dialog will appear — pick mood, platform, duration → music is imported and placed on Audio 2

---

## library.json Schema

```jsonc
{
  "version": "2.0",
  "tracks": [
    {
      "id": "unique-slug",           // used as identifier
      "title": "Track Title",
      "artist": "Artist Name",
      "local_path": "tracks/file.mp3",  // relative to library.json (or absolute)
      "genre": "lofi",               // lofi | electronic | house | hip_hop | cinematic | pop | ambient | motivational | corporate
      "subgenres": ["chillhop"],
      "mood": "calm",                // primary mood
      "moods": ["calm", "focused"],  // all applicable moods
      "energy_level": 0.4,          // 0.0 (silent) to 1.0 (maximum energy)
      "tempo": "slow",               // slow | medium | medium-fast | fast
      "bpm": 85,                     // optional, enables precise pacing scoring
      "duration_sec": 180,           // null = unknown
      "source": "personal_library",  // personal_library | youtube | instagram | suno
      "license": "free_use",         // free_use | cc_attribution | youtube_audio_library | social_platform
      "is_trending": false,
      "platforms_trending": [],      // instagram | tiktok | youtube | ...
      "suitable_for": ["tutorial"],  // content type tags
      "scene_fit": ["repos"],        // scene position tags
      "usage_count": 0
    }
  ]
}
```

**Local path resolution:**
- Relative paths (e.g., `tracks/song.mp3`) are resolved from the directory containing `library.json`
- Use `MUSIC_INDEX_PATH` env var to point to a library anywhere on disk
- Use `MUSIC_TRACKS_ROOT` env var (Remotion adapter) to override the tracks root directory

---

## Adding Your Own Library (private tracks)

For private/personal tracks not committed to git:

```bash
# Option 1: local_path override with MUSIC_TRACKS_ROOT
MUSIC_TRACKS_ROOT=/Volumes/MyDrive/Music MUSIC_INDEX_PATH=library.json python suggest.py --list

# Option 2: library.local.json (gitignored)
cp library.json library.local.json
# Edit library.local.json with absolute paths / remote URLs
MUSIC_INDEX_PATH=library.local.json python suggest.py --mood energetic
```

---

## Running Tests

```bash
python -m pytest tests/ -v
# or
python tests/test_suggest.py
```

---

## License

MIT — the selector engine and adapters are free to use.
Your music files remain yours; they are never committed to this repo.
